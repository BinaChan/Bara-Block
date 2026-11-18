"""Regression for uncached, nonblocking OSM/BIG hydration and strict peat filtering."""
import json,time,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import server,persistent_cache
from peat_selection import is_peat_feature
from hydro_foundation import optimize


def test_uncached_live_without_blocking(monkeypatch,tmp_path):
    monkeypatch.setattr(persistent_cache,'BASE',tmp_path)
    server.OSM_REFRESH_STATE.clear();server.PEAT_JOBS.clear()
    s=next(x for x in server.site_entries() if x['id']=='SUM-01')
    network={'elements':[{'type':'way','id':7777,'tags':{'waterway':'canal'},
        'geometry':[{'lon':s['lon']-.025,'lat':s['lat']},{'lon':s['lon']+.025,'lat':s['lat']}]}], 'source_updated':time.time()}
    peat={'type':'FeatureCollection','source':'BIG','features':[{'type':'Feature',
        'properties':{'landform':'Gambut'}, 'geometry':{'type':'Polygon','coordinates':[[
        [s['lon']-.018,s['lat']-.016],[s['lon']+.018,s['lat']-.016],
        [s['lon']+.018,s['lat']+.016],[s['lon']-.018,s['lat']+.016],
        [s['lon']-.018,s['lat']-.016]]]}}]}
    event=threading.Event()
    def fetch_osm(b,key):
        event.wait(timeout=3)
        persistent_cache.write('osm',key,network)
        return network
    def fetch_peat(layer,b,key):
        event.wait(timeout=3)
        p=peat if layer==6 else {'type':'FeatureCollection','features':[],'source':'BIG'}
        persistent_cache.write('peat_shapes',key,p)
        return p
    monkeypatch.setattr(server,'_fetch_osm',fetch_osm)
    monkeypatch.setattr(server,'_retrieve_peat',fetch_peat)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    q=urlencode({'site':s['id'],'lat':s['lat'],'lon':s['lon']})
    p=urlencode({'site':s['id'],'layer':6,'w':s['lon']-.07,'s':s['lat']-.07,'e':s['lon']+.07,'n':s['lat']+.07})
    try:
        t=time.monotonic()
        w=json.load(urlopen(base+'/api/waterways?'+q,timeout=2))
        assert time.monotonic()-t<1.5
        assert w['elements']==[] and w['refreshing']
        t=time.monotonic()
        layer=json.load(urlopen(base+'/api/peat-shapes?'+p,timeout=2))
        assert time.monotonic()-t<1.5
        assert layer['features']==[] and layer['refreshing']
        fast=json.load(urlopen(Request(base+'/api/foundation',data=json.dumps({
             'site':s['id'],'lat':s['lat'],'lon':s['lon'], 'osm':None,'peat':None,
             'force':True}).encode(),headers={'Content-Type':'application/json'}),timeout=2))
        assert fast['metrics']['site_area_km2']==225
        event.set()
        for i in range(60):
            w=json.load(urlopen(base+'/api/waterways?'+q))
            layer=json.load(urlopen(base+'/api/peat-shapes?'+p))
            if w['elements'] and layer['features']:break
            time.sleep(.03)
        assert len(w['elements'])==1
        assert len(layer['features'])==1
        proposal=optimize(s['lon'],s['lat'],w,None)
        assert proposal['status']=='canals_only' and proposal['candidates']
        assert proposal['candidates'][0]['coverage_ha'] is None
        full=optimize(s['lon'],s['lat'],w,layer)
        assert full['status']=='ready' and full['metrics']['peat_ha']>0 and full['candidates']
    finally:
        event.set();srv.shutdown();srv.server_close();thread.join(timeout=3)


def test_peat_soil_overrides_eco():
    feat=lambda soil,eco: {'properties':{'tnh_gambut':soil,'feg_peat':eco},'geometry':{'type':'Polygon','coordinates':[]}}
    assert not is_peat_feature(feat('Non Gambut (Mineral)','Fungsi Budidaya (Gambut < 3 m)'),48)
    assert is_peat_feature(feat('Tanah Gambut',''),48)
    assert is_peat_feature(feat(None,'Gambut'),48)
