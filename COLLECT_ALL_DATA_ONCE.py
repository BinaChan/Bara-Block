#!/usr/bin/env python3
"""One-time, restart-safe download of mapped OSM waterways + BIG peat polygons for 29 sites.

Only real upstream responses are saved. Existing successful results are never re-downloaded.
Polite sequential requests; no fire history or radar bulk downloads.
"""
from __future__ import annotations
import argparse,json,math,time
from pathlib import Path
from urllib.parse import urlencode,urlparse
from persistent_cache import key_for,read as disk_read,write as disk_write
from server import OVERPASS,BIG,upstream,waterways_query
from peat_selection import select_peat_mask
from hydro_foundation import optimize

ROOT=Path(__file__).resolve().parent

def site_bbox(site):
    lon,lat=site['lon'],site['lat']
    km=7.5
    dx=km/(111.195*max(.15,math.cos(math.radians(lat))))
    dy=km/111.195
    return {'w':max(94,lon-dx),'e':min(144,lon+dx),'s':max(-12,lat-dy),'n':min(7,lat+dy)}

def collect_osm(site,delay=5):
    lat,lon=site['lat'],site['lon'];name=site['id'];radius_km=7.5
    key=key_for('osm',{'site':name,'lat':round(lat,5),'lon':round(lon,5),'radius_km':radius_km,'schema':23})
    old=disk_read('osm',key)
    if old and isinstance(old.get('elements'),list):return ('cached',len(old['elements']))
    b=site_bbox(site);query=waterways_query(b)
    errors=[]
    for host in OVERPASS:
        try:
            body,_=upstream(host,urlencode({'data':query}).encode(),timeout=20,limit=25_000_000)
            obj=json.loads(body)
            if not isinstance(obj.get('elements'),list) or obj.get('remark'):raise ValueError(str(obj.get('remark','No OSM ways')))
            obj['provider']=urlparse(host).hostname;obj['source_updated']=time.time()
            disk_write('osm',key,obj)
            time.sleep(delay)
            return ('saved',len(obj['elements']))
        except Exception as ex:errors.append(str(ex)[:70])
    raise RuntimeError('; '.join(errors))

def collect_peat(site,layer,delay=1):
    b=site_bbox(site)
    key=key_for('peat_shapes',{'layer':layer,'w':round(b['w'],5),'s':round(b['s'],5),'e':round(b['e'],5),'n':round(b['n'],5)})
    old=disk_read('peat_shapes',key)
    if old is not None and isinstance(old.get('features'),list):return 'cached',len(old['features'])
    params={'f':'geojson','where':'1=1',
         'geometry':json.dumps({'xmin':b['w'],'ymin':b['s'],'xmax':b['e'],'ymax':b['n'],'spatialReference':{'wkid':4326}}),
         'geometryType':'esriGeometryEnvelope','inSR':'4326','outSR':'4326',
         'spatialRel':'esriSpatialRelIntersects','outFields':{6:'landform',37:'kode_khg',48:'kode_khg,feg_50k,tnh_gambut,feg_peat'}[layer],
         'returnGeometry':'true','geometryPrecision':'5','maxAllowableOffset':'0.0005',
         'resultRecordCount':'200'}
    all_features=[]
    for offset in range(0,1600,200):
        params['resultOffset']=str(offset)
        body,_=upstream(f'{BIG}/{layer}/query?'+urlencode(params),timeout=24,limit=14_000_000)
        doc=json.loads(body)
        if doc.get('error'):raise ValueError('BIG: '+str(doc['error'])[:120])
        if doc.get('type')!='FeatureCollection' or not isinstance(doc.get('features'),list):
            raise ValueError('BIG returned non-GeoJSON response')
        all_features.extend(doc['features'])
        if len(doc['features'])<200 and not doc.get('exceededTransferLimit'):break
        time.sleep(delay)
    else:raise ValueError('Too many peat polygons; source not fully paged')
    output={'type':'FeatureCollection','features':all_features,'source':'BIG','layer':layer}
    disk_write('peat_shapes',key,output)
    time.sleep(delay)
    return ('saved',len(all_features))

def main():
    ap=argparse.ArgumentParser(description='One-time cache for all site waterway and peat layers')
    ap.add_argument('--max-sites',type=int,default=29)
    ap.add_argument('--site',action='append',help='Collect a specific site ID; repeat if needed')
    args=ap.parse_args()
    sites=json.loads((ROOT/'sites.json').read_text())['sites']
    if args.site:sites=[s for s in sites if s['id'] in args.site]
    summary={}
    for idx,site in enumerate(sites[:args.max_sites],1):
        print(f'[{idx}/{min(len(sites),args.max_sites)}] {site["id"]}',flush=True)
        out={}
        for name,fn in [('osm',lambda:collect_osm(site)),('peat_soil',lambda:collect_peat(site,6)),('peat_area',lambda:collect_peat(site,48)),('peat_system',lambda:collect_peat(site,37))]:
            try:
                status,count=fn();out[name]={'status':status,'features':count}
            except Exception as exc:out[name]={'status':'unavailable','reason':str(exc)[:180]}
            print('  ',name,out[name],flush=True)
        b=site_bbox(site)
        def get_peat_layer(layer):
            key=key_for('peat_shapes',{'layer':layer,'w':round(b['w'],5),'s':round(b['s'],5),'e':round(b['e'],5),'n':round(b['n'],5)})
            return disk_read('peat_shapes',key)
        peat=select_peat_mask(get_peat_layer(6),get_peat_layer(48))
        if peat['features']:
            disk_write('peat_masks',key_for('peat_masks',{'site':site['id'],'lat':round(site['lat'],5),'lon':round(site['lon'],5),'v':23}),peat)
        osmkey=key_for('osm',{'site':site['id'],'lat':round(site['lat'],5),'lon':round(site['lon'],5),'radius_km':7.5,'schema':23})
        osm=disk_read('osm',osmkey)
        if osm and peat['features']:
            fkey=key_for('foundation',{'site':site['id'],'lat':round(site['lat'],5),'lon':round(site['lon'],5),'v':23})
            disk_write('foundation',fkey,{**optimize(site['lon'],site['lat'],osm,peat,limit=12),'site':site['id'],'version':23})
            out['foundation']={'status':'saved','peat_polygons':len(peat['features'])}
        else:out['foundation']={'status':'incomplete','peat_polygons':len(peat['features'])}
        summary[site['id']]=out
        disk_write('collection',key_for('collection',{'manifest':'all_sites_v23'}),summary)
    from export_structured import export
    export()
    print('Collection saved to data/tersimpan/; structured exports updated.',flush=True)

if __name__=='__main__':main()
