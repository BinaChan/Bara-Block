"""Tests the original BARA 25 project's integration without claiming remote API access."""
import json,time,threading, tempfile
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer
import pytest
import server,persistent_cache,era5_open_meteo


def test_osm_cache_then_live_sync(monkeypatch, tmp_path):
    monkeypatch.setattr(persistent_cache,'BASE',tmp_path)
    site=server.site_entries()[0]; site_id=site['id'];lat,lon=site['lat'],site['lon']
    key=persistent_cache.key_for('osm',{'site':site_id,'lat':round(lat,5),'lon':round(lon,5),'radius_km':7.5,'schema':23})
    initial={'elements':[{'type':'way','id':11,'tags':{'waterway':'canal'},'geometry':[{'lon':lon,'lat':lat},{'lon':lon+.01,'lat':lat}]}], 'provider':'OSM saved', 'source_updated':time.time()}
    persistent_cache.write('osm',key,initial)
    updates=[]
    def updated(b,k):
        updates.append(k)
        fresh={**initial,'elements':initial['elements']+[{'type':'node','id':12,'lat':lat,'lon':lon,'tags':{'waterway':'sluice_gate'}}], 'source_updated':time.time()}
        persistent_cache.write('osm',k,fresh)
        return fresh
    monkeypatch.setattr(server,'_fetch_osm',updated)
    server.OSM_REFRESH_STATE.clear()
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler); t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    qs=urlencode({'site':site_id,'lat':lat,'lon':lon})
    try:
        doc=json.load(urlopen(base+'/api/waterways?'+qs))
        assert doc['cached'] and len(doc['elements'])==1 and not updates
        doc=json.load(urlopen(base+'/api/waterways?'+qs+'&refresh=1'))
        assert len(doc['elements'])==1 and doc['refreshing']
        for _ in range(50):
            if len(persistent_cache.read('osm',key)['elements'])==2:break
            time.sleep(.03)
        doc=json.load(urlopen(base+'/api/waterways?'+qs))
        assert len(doc['elements'])==2 and doc['elements'][1]['tags']['waterway']=='sluice_gate'
        assert updates==[key]
    finally:
        srv.shutdown();srv.server_close();t.join(timeout=2)


def test_era5_download_cache_and_environment_endpoint(monkeypatch,tmp_path):
    monkeypatch.setattr(persistent_cache,'BASE',tmp_path)
    server.ERA5_STATE.clear()
    calls=[]
    def fake_get_many(sites,when):
        calls.append((sites[0]['id'],when))
        return [{'site':sites[0]['id'],'source':'ERA5-Land via Open-Meteo historical archive API',
                 'datetime_utc':when+'T02:00:00Z','temp_c':30.7,'rh_pct':64,
                 'wind_kmh':19,'wind_toward_deg':135,'precipitation_1h_mm':1.2,
                 'soil_water_l1_m3m3':.35}]
    monkeypatch.setattr(era5_open_meteo,'get_many',fake_get_many)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    try:
        result=json.load(urlopen(base+'/api/environment?site=PAP-01'))
        assert result['era5_status'] in ('fetching','saved')
        for _ in range(70):
            result=json.load(urlopen(base+'/api/environment?site=PAP-01'))
            if result['era5_status']=='saved':break
            time.sleep(.03)
        assert result['era5']['temp_c']==30.7
        assert result['era5']['wind_toward_deg']==135
        assert len(calls)==1
        row=next(s for s in server.site_entries() if s['id']=='PAP-01')
        assert persistent_cache.read('era5_open_meteo',era5_open_meteo.cache_key(row,server.ERA5_DATE))['temp_c']==30.7
        resp=urlopen(base+'/assets/bara-logo.webp')
        assert resp.status==200 and resp.headers['Content-Type'] in ('image/webp','application/octet-stream')
        assert len(resp.read())>10000
    finally:
        srv.shutdown();srv.server_close();t.join(timeout=2)
