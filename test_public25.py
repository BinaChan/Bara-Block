"""BARA-BLOCK 25: fast regression for published UI, fire-aware ranking and API safety."""
import json,threading,os,tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from hydro_foundation import optimize
import server,persistent_cache

ROOT=Path(__file__).resolve().parent
lon,lat=138.15,-5.53
peat={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'landform':'Gambut'},'geometry':{'type':'Polygon','coordinates':[[[138.112,-5.558],[138.188,-5.558],[138.188,-5.502],[138.112,-5.502],[138.112,-5.558]]]}}]}
def way(i,coords,name):return {'type':'way','id':i,'tags':{'waterway':'canal','name':name},'geometry':[{'lon':x,'lat':y} for x,y in coords]}
osm={'elements':[
 way(111,[[138.125,-5.547],[138.175,-5.547]],'South canal'),
 way(112,[[138.125,-5.531],[138.175,-5.531]],'Central canal'),
 way(113,[[138.125,-5.512],[138.175,-5.512]],'North canal'),
 way(114,[[138.13,-5.552],[138.13,-5.508]],'West drain'),
 way(115,[[138.172,-5.552],[138.172,-5.508]],'East drain'),
 {'type':'way','id':120,'tags':{'waterway':'river'},'geometry':[{'lon':138.181,'lat':-5.55},{'lon':138.181,'lat':-5.51}]},
 {'type':'node','id':130,'lat':-5.53,'lon':138.15,'tags':{'waterway':'sluice_gate'}}
]}
foundation=optimize(lon,lat,osm,peat)
assert foundation['status']=='ready',foundation['status']
assert len(foundation['candidates'])>10,len(foundation['candidates'])

def test_public_browser():
 errors=[]
 with tempfile.TemporaryDirectory() as temp:
  original=persistent_cache.BASE
  persistent_cache.BASE=Path(temp)
  srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
  base=f'http://127.0.0.1:{srv.server_address[1]}'
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    for view,dimensions in [('desktop',{'width':1440,'height':900}),('mobile',{'width':390,'height':844})]:
     context=browser.new_context(viewport=dimensions,device_scale_factor=1)
     html=(ROOT/'index.html').read_text()
     html=html.replace('<link rel="stylesheet" href="app.css">','<style>'+(ROOT/'app.css').read_text()+'</style>')
     html=__import__('re').sub(r'<script[^>]*></script>','',html)
     mock="""window.fetch=async function(url,opt){const uri=String(url);let doc={},status=200;
if(uri.startsWith('/api/waterways'))doc=OSM_DATA;
else if(uri.startsWith('/api/peat-shapes'))doc=uri.includes('layer=6')?PEAT_DATA:{type:'FeatureCollection',features:[]};
else if(uri.startsWith('/api/foundation'))doc=FOUNDATION_DATA;
else if(uri.startsWith('/api/environment'))doc={smap:null,era5:null,aligned:false};
else if(uri.startsWith('/api/edits'))doc={canals:[],blocks:[]};
else if(uri.startsWith('/api/version'))doc={version:'25.0',public_read_only:false};
else{status=404;doc={message:'Unavailable'}}
return new Response(JSON.stringify(doc),{status,headers:{'Content-Type':'application/json'}})};"""
     mock='const OSM_DATA='+json.dumps(osm)+';const PEAT_DATA='+json.dumps(peat)+';const FOUNDATION_DATA='+json.dumps(foundation)+';'+mock
     if view=='mobile':mock=mock.replace('public_read_only:false','public_read_only:true')
     js=(ROOT/'app.js').read_text().replace("['http:','https:'].includes(location.protocol)",'true').replace("location.protocol==='http:'",'true')
     scripts=[mock]+[(ROOT/f).read_text() for f in ('seed.js','sites_catalog.js')]+[js]
     html=html.replace('</body>',''.join('<script>'+src+'</script>' for src in scripts)+'</body>')
     page=context.new_page();page.on('pageerror',lambda exc:errors.append(str(exc)))
     context.route('**/*',lambda route:route.abort())
     page.set_content(html,wait_until='domcontentloaded',timeout=12000)
     page.wait_for_function('BARA25.state.foundationReady && BARA25.state.fireRankStatus === "fire"',timeout=30000)
     assert page.locator('#analysisBtn').count()==0
     assert page.locator('.legendRow span').count()==6
     assert page.locator('#structureNum').inner_text()=='1'
     assert page.locator('#siteArea').inner_text().find('km²')>=0
     assert page.locator('.blockItem').count()>0
     first=page.evaluate('BARA25.state.rankedBlockPlaces[0].line_id')
     page.evaluate('BARA25.state.ignition={lon:138.149,lat:-5.547};BARA25.sim()')
     page.wait_for_timeout(1350)
     south=page.evaluate('BARA25.state.rankedBlockPlaces[0].line_id')
     page.evaluate('BARA25.state.ignition={lon:138.149,lat:-5.512};BARA25.sim()')
     page.wait_for_timeout(1350)
     north=page.evaluate('BARA25.state.rankedBlockPlaces[0].line_id')
     assert south!=north,('ranking must update with moved fire',first,south,north)
     assert page.evaluate('BARA25.state.shownBlocks.filter(p=>p.isOptimized).map(p=>p.displayRank).join(",")')=='1,2,3'
     page.locator('#waterInput').fill('90')
     page.wait_for_timeout(700)
     page.locator('[data-base="satellite"]').click()
     assert page.evaluate('BARA25.state.baseLayer')=='satellite'
     page.locator('[data-base="terrain"]').click()
     assert page.evaluate('BARA25.state.baseLayer')=='terrain'
     page.locator('[data-base="street"]').click()
     assert page.evaluate('BARA25.state.baseLayer')=='street'
     page.locator('#playBtn').click()
     page.wait_for_timeout(150)
     assert page.evaluate('BARA25.state.playing') is True
     page.locator('#playBtn').click()
     assert page.evaluate('BARA25.state.playing') is False
     if view=='mobile':
      page.wait_for_function('BARA25.state.publicReadOnly === true',timeout=3000)
      page.locator('#importKind').select_option('canal')
      extra={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':'Local import'},'geometry':{'type':'LineString','coordinates':[[138.142,-5.526],[138.146,-5.528]]}}]}
      page.locator('#importFile').set_input_files({'name':'canal.geojson','mimeType':'application/geo+json','buffer':json.dumps(extra).encode()})
      page.wait_for_function('BARA25.state.canals.length === 6',timeout=3000)
      assert page.locator('#importBtn').is_visible()
     page.screenshot(path=str(ROOT/f'preview_{view}.png'),full_page=False,timeout=15000)
     print(view,'rank',first,'south',south,'north',north,'waterways',page.locator('#canalNum').inner_text(),flush=True)
     page.close()
    browser.close()
  finally:
   srv.shutdown();srv.server_close();thread.join(timeout=2)
   persistent_cache.BASE=original
 assert not errors,errors

def test_public_api_read_only():
 from urllib.request import urlopen,Request
 from urllib.error import HTTPError
 old=persistent_cache.BASE;original=server.PUBLIC_READ_ONLY
 with tempfile.TemporaryDirectory() as temp:
  persistent_cache.BASE=Path(temp);server.PUBLIC_READ_ONLY=True
  srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
  base=f'http://127.0.0.1:{srv.server_address[1]}'
  try:
   assert json.load(urlopen(base+'/api/version'))['public_read_only']
   assert json.load(urlopen(base+'/api/edits?site=PAP-01'))=={'canals':[],'blocks':[]}
   req=Request(base+'/api/import-geojson?site=PAP-01&layer=6',data=b'{}',method='POST')
   try:urlopen(req);assert False,'write should be blocked'
   except HTTPError as e:assert e.code==403
   for path in ['/server.py','/data/tersimpan/example.json','/sites.json']:
    try:urlopen(base+path);assert False,'static private file exposed '+path
    except HTTPError as e:assert e.code==404
  finally:
   srv.shutdown();srv.server_close();thread.join(timeout=2)
   persistent_cache.BASE=old;server.PUBLIC_READ_ONLY=original
