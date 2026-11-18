"""Offline regression: all local GIS imports, basemap code, and integrated foundation."""
from __future__ import annotations
import json,threading,tempfile
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer
import persistent_cache
from server import Handler

def test_imported_layers_and_integration():
    original=persistent_cache.BASE
    with tempfile.TemporaryDirectory() as folder:
        persistent_cache.BASE=Path(folder)
        srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{srv.server_address[1]}'
        def req(path,body=None):
            url=base+path
            r=Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/geo+json'} if body is not None else {})
            with urlopen(r,timeout=8) as response:return json.load(response)
        center=[138.15,-5.53]
        polygon={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'User soil area'},
          'geometry':{'type':'Polygon','coordinates':[[[138.132,-5.543],[138.17,-5.543],[138.17,-5.517],[138.132,-5.517],[138.132,-5.543]]]}}]}
        line={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'Imported canal'},'geometry':{'type':'LineString','coordinates':[[138.137,-5.53],[138.166,-5.53]]}}]}
        river={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'Imported river'},'geometry':{'type':'LineString','coordinates':[[138.145,-5.54],[138.145,-5.52]]}}]}
        struct={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'Water control'},'geometry':{'type':'Point','coordinates':[138.16,-5.53]}}]}
        try:
            for layer,doc in [('6',polygon),('37',polygon),('48',polygon),('canal',line),('river',river),('structures',struct)]:
                result=req(f'/api/import-geojson?site=PAP-01&layer={layer}',doc)
                assert result['saved'] and result['count']==1
            water=req('/api/waterways?site=PAP-01&lat=-5.53&lon=138.15')
            assert len(water['elements'])==3
            b=urlencode({'site':'PAP-01','layer':6,'w':138.08,'e':138.22,'s':-5.6,'n':-5.46})
            peat=req('/api/peat-shapes?'+b)
            assert peat['source']=='Local GeoJSON import' and peat['features'][0]['properties']['landform'].startswith('Gambut')
            full=req('/api/foundation',{'site':'PAP-01','lat':-5.53,'lon':138.15,'osm':water,'peat':peat,'force':True})
            assert full['status']=='ready'
            assert full['metrics']['canal_km']>0 and full['metrics']['river_km']>0 and full['metrics']['peat_ha']>0
            assert full['metrics']['structure_count']==1
            assert len(full['selected'])>0
            print('Offline API integrated:',full['metrics']['peat_ha'],'ha peat',full['metrics']['canal_km'],'km canals',len(full['selected']),'block candidates')
        finally:
            srv.shutdown();srv.server_close();thread.join(timeout=2)
            persistent_cache.BASE=original

if __name__=='__main__':test_imported_layers_and_integration()
