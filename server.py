#!/usr/bin/env python3
"""BARA-BLOCK: integrated peat hydrology and fire map.
No APIs for archived fire data; OSM features always come from Overpass, never invented.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from pathlib import Path
import json, math, os, threading, time, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
from persistent_cache import key_for, read as disk_read, write as disk_write
from hydro_foundation import inventory, optimize, site_frame
from peat_selection import select_peat_mask

ROOT=Path(__file__).resolve().parent
PUBLIC_READ_ONLY=os.getenv('BARA_PUBLIC_READ_ONLY','0')=='1'
OVERPASS=(
    'https://overpass.private.coffee/api/interpreter',
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.maprva.org/api/interpreter',
)
BIG='https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/SUMBER_DAYA_ALAM_DAN_LINGKUNGAN/MapServer'
CACHE={}
LOCK=threading.Lock()

# ERA5-Land 2024-01-01 matches the included SMAP snapshot; retrieved per site on demand.
ERA5_DATE='2024-01-01'
ERA5_STATE={}
ERA5_LOCK=threading.Lock()
ERA5_LIMIT=threading.BoundedSemaphore(2)

def site_entries():
    return json.loads((ROOT/'sites.json').read_text(encoding='utf8'))['sites']

def era5_cached(site):
    from era5_open_meteo import cache_key
    row=next((x for x in site_entries() if x['id']==site),None)
    return disk_read('era5_open_meteo',cache_key(row,ERA5_DATE)) if row else None

def _download_era5(site):
    try:
        from era5_open_meteo import get_many,cache_key
        row=next((x for x in site_entries() if x['id']==site),None)
        if row is None:raise ValueError('Unknown site')
        with ERA5_LIMIT:weather=get_many([row],ERA5_DATE)[0]
        if weather.get('temp_c') is None:raise ValueError('ERA5-Land response lacks temperature')
        disk_write('era5_open_meteo',cache_key(row,ERA5_DATE),weather)
        with ERA5_LOCK:ERA5_STATE[site]=('saved',time.time())
    except Exception as exc:
        with ERA5_LOCK:ERA5_STATE[site]=('unavailable',time.time())

def start_era5(site):
    if not any(x['id']==site for x in site_entries()):return 'unavailable'
    with ERA5_LOCK:
        status,when=ERA5_STATE.get(site,('new',0))
        if status=='fetching' or status=='saved':return status
        if status=='unavailable' and time.time()-when<600:return status
        ERA5_STATE[site]=('fetching',time.time())
    threading.Thread(target=_download_era5,args=(site,),name='era5-'+site,daemon=True).start()
    return 'fetching'

# OSM: stale-while-revalidate, with a 30-minute TTL and one fetch per site.
OSM_TTL=1800
OSM_REFRESH_LOCK=threading.RLock()
OSM_REFRESH_STATE={}

OSM_PROVIDER_LIMIT=threading.BoundedSemaphore(2)
def _fetch_osm(b,key):
    query=waterways_query(b)
    encoded=urlencode({'data':query}).encode()
    def fetch(host):
        raw,_=upstream(host,encoded,timeout=9,limit=25_000_000)
        obj=json.loads(raw)
        if not isinstance(obj.get('elements'),list) or obj.get('remark'):
            raise ValueError('Invalid OSM response')
        obj['provider']=urlparse(host).hostname
        return obj
    obj=None
    # Race two independent Overpass endpoints, avoiding serial 4x waiting.
    with OSM_PROVIDER_LIMIT:
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='osm-provider') as pool:
            tasks=[pool.submit(fetch,host) for host in OVERPASS[:2]]
            for task in as_completed(tasks):
                try:obj=task.result();break
                except Exception:continue
        if obj is None:
            for host in OVERPASS[2:]:
                try:obj=fetch(host);break
                except Exception:continue
        if obj is None:
            try:obj=fallback_osm_native(b)
            except Exception:return disk_read('osm',key)
    obj['source_updated']=time.time()
    current=disk_read('osm',key)
    if obj.get('elements') or not (current and current.get('elements')):
        disk_write('osm',key,obj)
        return obj
    return current

def _run_osm_refresh(b,key):
    state='unavailable'
    try:
        doc=_fetch_osm(b,key)
        state=('saved' if doc.get('elements') else 'empty') if doc is not None else 'unavailable'
    finally:
        with OSM_REFRESH_LOCK:OSM_REFRESH_STATE[key]=(state,time.time())

def refresh_osm_async(b,key,force=False):
    with OSM_REFRESH_LOCK:
        status,when=OSM_REFRESH_STATE.get(key,('new',0))
        if status=='fetching' or time.time()-when<(20 if force else 180):return status=='fetching'
        OSM_REFRESH_STATE[key]=('fetching',time.time())
    threading.Thread(target=_run_osm_refresh,args=(b,key),daemon=True).start()
    return True

# BIG is independent of the OSM job. Uncached landscapes return immediately
# and are hydrated from a bounded background fetch (not a blocking web request).
PEAT_WORK_LOCK=threading.RLock()
PEAT_JOBS={}
PEAT_LIMIT=threading.BoundedSemaphore(2)
PEAT_EMPTY_TTL=12*3600

def _retrieve_peat(layer,b,cachekey):
    all_features=[]
    for offset in range(0,1600,200):
        params={'f':'geojson','where':'1=1',
            'geometry':json.dumps({'xmin':b['w'],'ymin':b['s'],'xmax':b['e'],'ymax':b['n'],
                                   'spatialReference':{'wkid':4326}}),
            'geometryType':'esriGeometryEnvelope','inSR':'4326','outSR':'4326',
            'spatialRel':'esriSpatialRelIntersects',
            'outFields':{6:'landform',37:'kode_khg',48:'kode_khg,feg_50k,tnh_gambut,feg_peat'}[layer],
            'returnGeometry':'true','geometryPrecision':'5','maxAllowableOffset':'0.0005',
            'resultRecordCount':'200','resultOffset':str(offset)}
        body,_=upstream(f'{BIG}/{layer}/query?'+urlencode(params),timeout=13,limit=12_000_000)
        data=json.loads(body)
        if data.get('error'):raise ValueError(str(data['error'])[:160])
        chunk=data.get('features')
        if not isinstance(chunk,list):raise ValueError('BIG returned no GeoJSON features array')
        all_features.extend(chunk)
        # ArcGIS transfer-limit flag is the authoritative pagination indicator.
        if not data.get('exceededTransferLimit') and len(chunk)<200:break
    else:raise ValueError('BIG response exceeds paging limit')
    doc={'type':'FeatureCollection','features':all_features,'source':'BIG','layer':layer,'source_updated':time.time()}
    disk_write('peat_shapes',cachekey,doc)
    return doc

def _run_peat(layer,b,cachekey):
    status='unavailable'
    try:
        with PEAT_LIMIT:
            doc=_retrieve_peat(layer,b,cachekey)
            status='saved' if doc.get('features') else 'empty'
    except Exception:pass
    finally:
        with PEAT_WORK_LOCK:PEAT_JOBS[cachekey]=(status,time.time())

def refresh_peat_async(layer,b,cachekey,force=False):
    with PEAT_WORK_LOCK:
        status,when=PEAT_JOBS.get(cachekey,('new',0))
        if status=='fetching':return True
        if when and time.time()-when<(30 if force else 180):return False
        PEAT_JOBS[cachekey]=('fetching',time.time())
    threading.Thread(target=_run_peat,args=(layer,b,cachekey),daemon=True).start()
    return True

def waterways_query(b):
    bounds=','.join(f'{x:.5f}' for x in (b['s'],b['w'],b['n'],b['e']))
    return ('[out:json][timeout:28];('
        f'way["waterway"~"^(canal|ditch|drain|river|stream|tidal_channel)$"]({bounds});'
        f'way["water"="canal"]({bounds});'
        f'nwr["waterway"~"^(weir|dam|sluice_gate|lock_gate)$"]({bounds});'
        f'nwr["man_made"~"^(weir|dam|pumping_station)$"]({bounds});'
        f'nwr["barrier"~"^(dam|sluice_gate)$"]({bounds});'
        f'way["tunnel"="culvert"]["waterway"]({bounds});'
        f'nwr["waterway"="floodgate"]({bounds});'
        f'nwr["barrier"="dam"]({bounds});'
        f'nwr["sekat_kanal"]({bounds});'
        f'nwr["canal_block"]({bounds});'
        f'nwr["culvert"="yes"]({bounds});'
        f'nwr["pump"="yes"]({bounds});'
        ');out geom;')

def upstream(url, data=None, timeout=18, limit=22_000_000, accepts='application/json'):
    headers={'User-Agent':'BARA-BLOCK/29 (waterways and peat map)', 'Accept':accepts}
    if data is not None: headers['Content-Type']='application/x-www-form-urlencoded; charset=utf-8'
    req=Request(url,data=data,headers=headers,method='POST' if data is not None else 'GET')
    with urlopen(req,timeout=timeout) as resp:
        content=resp.read(limit+1);ctype=resp.headers.get('Content-Type','')
    if len(content)>limit: raise ValueError('Provider response larger than the permitted download; zoom closer.')
    return content,ctype

def fallback_osm_native(b):
    """Read OSM 0.6 map API when Overpass is inaccessible; small viewport only.
    Native API usage should be infrequent, single-user, and never for bulk crawling.
    """
    if (b['e']-b['w'])*(b['n']-b['s'])>0.02:
        raise ValueError('Native OpenStreetMap fallback needs a smaller view; zoom in.')
    bbox=','.join(f'{b[k]:.5f}' for k in ('w','s','e','n'))
    url='https://api.openstreetmap.org/api/0.6/map?'+urlencode({'bbox':bbox})
    raw, _=upstream(url,timeout=11,limit=16_000_000,accepts='application/xml')
    root=ET.fromstring(raw)
    nodes={}
    features=[]
    for node in root.findall('node'):
        try:
            nid=node.attrib['id']; lat=float(node.attrib['lat']); lon=float(node.attrib['lon'])
        except (KeyError,ValueError):continue
        nodes[nid]=(lon,lat)
        tags={t.attrib['k']:t.attrib.get('v','') for t in node.findall('tag') if 'k' in t.attrib}
        if any(k in tags for k in ('sekat_kanal','canal_block')) or tags.get('waterway') in ('dam','weir','sluice_gate','lock_gate','floodgate') or tags.get('man_made') in ('dam','weir','pumping_station') or tags.get('tunnel')=='culvert' or tags.get('culvert')=='yes' or tags.get('pump')=='yes' or tags.get('barrier') in ('dam','sluice_gate'):
            features.append({'type':'node','id':int(nid),'lon':lon,'lat':lat,'tags':tags})
    for way in root.findall('way'):
        tags={t.attrib['k']:t.attrib.get('v','') for t in way.findall('tag') if 'k' in t.attrib}
        kind=tags.get('waterway','')
        water=kind in ('canal','ditch','drain','river','stream','tidal_channel') or tags.get('water')=='canal'
        structure=any(k in tags for k in ('sekat_kanal','canal_block')) or kind in ('dam','weir','sluice_gate','lock_gate','floodgate') or tags.get('man_made') in ('dam','weir','pumping_station') or tags.get('tunnel')=='culvert' or tags.get('culvert')=='yes' or tags.get('pump')=='yes'
        if not water and not structure:continue
        geom=[{'lon':nodes[n.attrib['ref']][0],'lat':nodes[n.attrib['ref']][1]} for n in way.findall('nd') if n.attrib.get('ref') in nodes]
        if len(geom)<1:continue
        features.append({'type':'way','id':int(way.attrib.get('id','0')),'tags':tags,'geometry':geom})
    return {'elements':features,'provider':'api.openstreetmap.org (fallback)','note':'Small-viewport native OSM API fallback'}

def cache_get(key):
    with LOCK:
        v=CACHE.get(key)
        return v[1] if v and time.time()-v[0]<300 else None

def cache_put(key,value):
    with LOCK:
        if len(CACHE)>48:CACHE.clear()
        CACHE[key]=(time.time(),value)

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self,path):
        clean=urlparse(path).path
        if clean in ('','/','/index.html'):return str(ROOT/'index.html')
        name=Path(clean.lstrip('/'))
        allowed={'app.js','app.css','seed.js','sites_catalog.js','assets/bara-logo.webp',
                 'data/derived/structured_sites.csv','data/derived/structured_sites.json',
                 'data/derived/smap_sites.csv','data/derived/smap_sites.json'}
        if name.as_posix() not in allowed:return str(ROOT/'__invalid__')
        return str(ROOT/name)
    def log_message(self,format,*args):
        if self.path.startswith('/api/'):return
        super().log_message(format,*args)
    def end_headers(self):
        if urlparse(self.path).path in ('/','/index.html','/app.js','/app.css','/seed.js'):
            self.send_header('Cache-Control','no-store, max-age=0')
            self.send_header('Pragma','no-cache')
        super().end_headers()
    def reply(self,status,obj):
        raw=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode('utf8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/version':return self.reply(200,{'app':'BARA-BLOCK','version':'25.2','osm_geometry':'Overpass/OpenStreetMap','historical_fire':False,'fire_simulation':True,'public_read_only':PUBLIC_READ_ONLY})
        if path=='/api/edits':return self.load_edits()
        if path=='/api/sites':return self.site_catalog()
        if path=='/api/waterways':return self.waterways()
        if path=='/api/environment':return self.environment()
        if path=='/api/structured':return self.structured()
        if path=='/api/peat':return self.peat_point()
        if path=='/api/peat-shapes':return self.peat_shapes()
        if path=='/api/peat-mask':return self.peat_mask()
        if path=='/api/peat-raster':return self.peat_raster()
        if path in ('/api/era5','/api/era5-land'):return self.environment()
        return super().do_GET()
    def do_POST(self):
        if urlparse(self.path).path == '/api/edits':return self.reply(403,{'message':'Read only'}) if PUBLIC_READ_ONLY else self.save_edits()
        if urlparse(self.path).path == '/api/import-geojson':return self.reply(403,{'message':'Read only'}) if PUBLIC_READ_ONLY else self.import_geojson()
        if urlparse(self.path).path == '/api/foundation':return self.site_foundation()
        return self.reply(404,{'message':'Unknown endpoint.'})

    def environment_data(self,site,trigger_fetch=False):
        merged={'site':site,'smap':None,'era5':None,'smap_source':None,'era5_source':None}
        for kind,key in [('smap','smap_sites'),('era5','era5_sites')]:
            try:
                doc=json.loads((ROOT/'data'/'derived'/f'{key}.json').read_text(encoding='utf8'))
                row=next((r for r in doc.get('sites',[]) if r['site']==site),None)
                merged[kind]=row
                merged[f'{kind}_source']={'source':doc.get('source'),
                    'datetime':doc.get('datetime_utc') or doc.get('date_utc'),
                    'resolution':doc.get('resolution_km') or doc.get('spatial_resolution')}
            except (FileNotFoundError,ValueError,KeyError,TypeError):pass
        if merged['era5'] is None:
            saved=era5_cached(site)
            if saved:
                merged['era5']=saved
                merged['era5_source']={'source':saved.get('source'),'datetime':saved.get('datetime_utc'),'resolution':'~9 km'}
        if merged['era5'] is not None:merged['era5_status']='saved'
        elif trigger_fetch:merged['era5_status']=start_era5(site)
        else:merged['era5_status']=ERA5_STATE.get(site,('unavailable',0))[0]
        a=(merged['smap_source'] or {}).get('datetime')
        b=(merged['era5_source'] or {}).get('datetime')
        merged['aligned']=bool(merged['smap'] and merged['era5'] and a and b and a[:10]==b[:10])
        return merged

    def environment(self):
        try:site=self.site_id()
        except ValueError as exc:return self.reply(400,{'message':str(exc)})
        return self.reply(200,self.environment_data(site,trigger_fetch=True))

    def structured(self):
        try:
            site=self.site_id()
            sites=json.loads((ROOT/'sites.json').read_text(encoding='utf8'))['sites']
            row=next((s for s in sites if s['id']==site),None)
            if row is None:return self.reply(404,{'message':'Site not found'})
            lat,lon=row['lat'],row['lon']
            km=7.5
            osmkey=key_for('osm',{'site':site,'lat':round(lat,5),'lon':round(lon,5),'radius_km':km,'schema':23})
            raw=disk_read('osm',osmkey)
            foundation=disk_read('foundation',key_for('foundation',{
                'site':site,'lat':round(lat,5),'lon':round(lon,5),'v':23}))
            structure_records=[]
            if raw:
                for e in raw.get('elements',[]):
                    t=e.get('tags') or {}
                    if t.get('sekat_kanal') or t.get('canal_block') or t.get('waterway') in ('dam','weir','sluice_gate','lock_gate','floodgate') or t.get('man_made') in ('dam','weir','pumping_station') or t.get('tunnel')=='culvert' or t.get('barrier') in ('dam','sluice_gate'):
                        loc=e if 'lat' in e and 'lon' in e else (e.get('center') or (e.get('geometry') or [{}])[len(e.get('geometry') or [{}])//2])
                        structure_records.append({'id':f'{e.get("type")}:{e.get("id")}',
                          'type':t.get('waterway') or t.get('man_made') or t.get('barrier') or t.get('tunnel') or 'canal_block',
                          'lon':loc.get('lon'),'lat':loc.get('lat'),'tags':t})
            return self.reply(200,{'site':row,'foundation':foundation,
               'waterways':{'available':raw is not None,'provider':raw.get('provider') if raw else None,
                  'feature_count':len(raw.get('elements',[])) if raw else None,
                  'canals_and_rivers': [e for e in raw.get('elements',[]) if e.get('tags',{}).get('waterway') in ('canal','ditch','drain','river','stream','tidal_channel')] if raw else [],
                  'structures':structure_records if raw else None},
               'environment':self.environment_data(site),
               'manual_edits':disk_read('edits',key_for('edits',{'site':site})) or {'canals':[],'blocks':[]}})
        except Exception as exc:return self.reply(500,{'message':str(exc)[:160]})

    def site_catalog(self):
        try:
            doc=json.loads((ROOT/'sites.json').read_text(encoding='utf8'))
            return self.reply(200,doc)
        except Exception as exc:return self.reply(500,{'message':str(exc)[:120]})

    def site_foundation(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not (1<=length<=8_000_000):raise ValueError('Invalid foundation payload size')
            obj=json.loads(self.rfile.read(length))
            site=str(obj.get('site',''))
            if not (1<=len(site)<=45 and all(c.isascii() and (c.isalnum() or c in '-_') for c in site)):
                raise ValueError('Invalid site identifier')
            lat=float(obj['lat']);lon=float(obj['lon'])
            osm=obj.get('osm');peat=obj.get('peat')
            if osm is not None and (not isinstance(osm,dict) or len(osm.get('elements',[]))>12000):
                raise ValueError('Invalid OSM inventory')
            if peat is not None and (not isinstance(peat,dict) or len(peat.get('features',[]))>1500):
                raise ValueError('Invalid peat geometry')
            key=key_for('foundation',{'site':site,'lat':round(lat,5),'lon':round(lon,5),'v':23})
            stored=None if PUBLIC_READ_ONLY else disk_read('foundation',key)
            # Return saved complete foundation; partial layers are merged on follow-up.
            if stored and not obj.get('force') and ((not osm or stored['metrics']['osm_available']) and
                           (not peat or stored['metrics']['peat_available'])):
                return self.reply(200,{**stored,'cached':True})
            doc=optimize(lon,lat,osm,peat,limit=12)
            doc['site']=site;doc['version']=23
            if not PUBLIC_READ_ONLY and peat is not None and peat.get('features'):
                disk_write('peat_masks',key_for('peat_masks',{'site':site,'lat':round(lat,5),'lon':round(lon,5),'v':23}),peat)
            if not PUBLIC_READ_ONLY and (osm is not None or peat is not None):disk_write('foundation',key,doc)
            return self.reply(200,doc)
        except ValueError as exc:return self.reply(400,{'message':str(exc)[:180]})
        except Exception as exc:return self.reply(500,{'message':'Foundation error: '+str(exc)[:180]})


    def bounds(self,qs):
        b={x:float(qs[x][0]) for x in ('w','s','e','n')}
        if not all(math.isfinite(a) for a in b.values()) or not (94<=b['w']<b['e']<=144 and -12<=b['s']<b['n']<=7):raise ValueError('Invalid Indonesian map boundary.')
        if b['e']-b['w']>.68 or b['n']-b['s']>.57:raise ValueError('Zoom in before scanning; only visible landscape scale is supported.')
        return b
    def site_id(self):
        q=parse_qs(urlparse(self.path).query)
        site=q.get('site',[''])[0]
        if not (1<=len(site)<=45 and all(c.isascii() and (c.isalnum() or c in '-_') for c in site)):
            raise ValueError('Select a site.')
        return site
    def edits_key(self):
        return key_for('edits',{'site':self.site_id()})
    def load_edits(self):
        try:
            key=self.edits_key()
            if PUBLIC_READ_ONLY:return self.reply(200,{'canals':[],'blocks':[]})
            return self.reply(200, disk_read('edits',key) or {'canals':[],'blocks':[]})
        except ValueError as e:return self.reply(400,{'message':str(e)})
    def save_edits(self):
        try:
            key=self.edits_key()
            length=int(self.headers.get('Content-Length','0'))
            if not 1<=length<=220000:raise ValueError('Data too large.')
            obj=json.loads(self.rfile.read(length))
            canals=obj.get('canals',[]);blocks=obj.get('blocks',[])
            if not isinstance(canals,list) or len(canals)>120 or not isinstance(blocks,list) or len(blocks)>150:
                raise ValueError('Too many site features.')
            for line in canals:
                coords=line.get('points',[])
                if not isinstance(coords,list) or not 2<=len(coords)<=500:raise ValueError('Invalid canal shape.')
                for xy in coords:
                    if not isinstance(xy,list) or len(xy)!=2 or not (94<=float(xy[0])<=144 and -12<=float(xy[1])<=7):
                        raise ValueError('Canal outside map.')
            for p in blocks:
                if not (94<=float(p['lon'])<=144 and -12<=float(p['lat'])<=7):raise ValueError('Block outside map.')
            doc={'canals':canals,'blocks':blocks}
            disk_write('edits',key,doc)
            return self.reply(200,{'saved':True,'canals':len(canals),'blocks':len(blocks)})
        except Exception as e:return self.reply(400,{'message':str(e)[:180]})
    def waterways(self):
        q=parse_qs(urlparse(self.path).query)
        try:
            lon=float(q['lon'][0]);lat=float(q['lat'][0]);site=self.site_id()
            if not (94<=lon<=144 and -12<=lat<=7):raise ValueError('Site outside Indonesia')
            km=7.5
            dx=km/(111.195*max(.15,math.cos(math.radians(lat))))
            dy=km/111.195
            b={'w':max(94,lon-dx),'e':min(144,lon+dx),'s':max(-12,lat-dy),'n':min(7,lat+dy)}
            key=key_for('osm',{'site':site,'lat':round(lat,5),'lon':round(lon,5),'radius_km':km,'schema':23})
            cached=disk_read('osm',key)
            force=q.get('refresh',['0'])[0]=='1'
            stamp=float(cached.get('source_updated') or 0) if cached else 0
            if cached and cached.get('elements') and not force:
                refreshing=refresh_osm_async(b,key) if time.time()-stamp>=OSM_TTL else False
                return self.reply(200,{**cached,'cached':True,'saved':True,'refreshing':refreshing})
            if cached and cached.get('elements') and force:
                # Show saved data immediately while the live provider updates in background.
                refreshing=refresh_osm_async(b,key,force=True)
                return self.reply(200,{**cached,'cached':True,'saved':True,'refreshing':refreshing})
        except Exception as exc:return self.reply(400,{'message':str(exc)[:180]})
        # Fast response for uncached sites; polling observes the on-disk result.
        refresh_osm_async(b,key,force=force)
        with OSM_REFRESH_LOCK:status=OSM_REFRESH_STATE.get(key,('unavailable',0))[0]
        return self.reply(200,{'elements':[], 'provider':'OpenStreetMap',
            'status':status,'refreshing':status=='fetching','cached':False,
            'source_updated':None})

    def peat_point(self):
        q=parse_qs(urlparse(self.path).query)
        try:
            layer=int(q.get('layer',[''])[0]);lon=float(q.get('lon',[''])[0]);lat=float(q.get('lat',[''])[0]);
            if layer not in (37,48) or not (94<=lon<=144 and -12<=lat<=7):raise ValueError('Invalid peat map query.')
            params={'f':'json','where':'1=1','geometry':json.dumps({'x':lon,'y':lat,'spatialReference':{'wkid':4326}}),'geometryType':'esriGeometryPoint','inSR':'4326','outSR':'4326','spatialRel':'esriSpatialRelIntersects','outFields':'kode_khg,feg_50k','returnGeometry':'false'}
            raw,_=upstream(f'{BIG}/{layer}/query?'+urlencode(params),timeout=13,limit=2_000_000)
            data=json.loads(raw)
            if data.get('error'):raise ValueError(str(data['error'])[:180])
            return self.reply(200,data)
        except ValueError as e:return self.reply(400,{'message':str(e)})
        except Exception as e:return self.reply(502,{'message':'BIG peat attributes unavailable: '+str(e)[:180]})
    def import_geojson(self):
        """Persist imported mapped GIS features under the selected site. No guessed boundaries."""
        try:
            qs=parse_qs(urlparse(self.path).query)
            site=self.site_id();layer=qs.get('layer',[''])[0]
            if layer not in ('6','37','48','canal','river','structures'):raise ValueError('Unsupported layer')
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=10_000_000:raise ValueError('GeoJSON must be below 10 MB')
            fc=json.loads(self.rfile.read(size))
            if not isinstance(fc,dict) or fc.get('type')!='FeatureCollection' or not isinstance(fc.get('features'),list):
                raise ValueError('Upload a GeoJSON FeatureCollection')
            features=fc['features']
            if len(features)>1200:raise ValueError('Maximum 1200 features')
            def coords_ok(obj):
                if not isinstance(obj,(list,tuple)):return False
                if obj and isinstance(obj[0],(int,float)):
                    return len(obj)>=2 and all(math.isfinite(float(v)) for v in obj[:2]) and 94<=float(obj[0])<=144 and -12<=float(obj[1])<=7
                return len(obj)<=100000 and all(coords_ok(item) for item in obj)
            as_osm=[];clean=[]
            polygon=layer in ('6','37','48')
            for i,f in enumerate(features):
                if not isinstance(f,dict):raise ValueError('Invalid GeoJSON feature')
                g=f.get('geometry') or {};kind=g.get('type');coords=g.get('coordinates');props=dict(f.get('properties') or {})
                if not coords_ok(coords):raise ValueError('Invalid or non-Indonesian coordinates')
                if polygon:
                    if kind not in ('Polygon','MultiPolygon'):raise ValueError('Expected polygon geometry')
                    if layer=='6' and not any(k in props for k in ('landform','LANDFORM')):
                        props['landform']='Gambut (imported boundary)'
                    clean.append({'type':'Feature','properties':props,'geometry':g})
                else:
                    if layer=='structures':
                        if kind!='Point':raise ValueError('Expected structure points')
                        as_osm.append({'type':'node','id':8_400_000+i,'lat':coords[1],'lon':coords[0],
                                       'tags':{'structure':'imported','waterway':str(props.get('waterway') or ''),'man_made':str(props.get('man_made') or ''),'name':str(props.get('name') or '')[:120]}})
                    else:
                        paths=[coords] if kind=='LineString' else coords if kind=='MultiLineString' else None
                        if paths is None:raise ValueError('Expected line geometry')
                        for k,points in enumerate(paths):
                            if len(points)<2:continue
                            as_osm.append({'type':'way','id':(8_200_000 if layer=='canal' else 8_300_000)+i*100+k,'geometry':[{'lon':xy[0],'lat':xy[1]} for xy in points],
                                           'tags':{'waterway':layer,'name':str(props.get('name') or '')[:120]}})
            if polygon:
                disk_write('imported_peat',key_for('imported_peat',{'site':site,'layer':int(layer)}),
                           {'type':'FeatureCollection','features':clean,'source':'Local GeoJSON import','layer':int(layer)})
            else:
                loc=next((s for s in json.loads((ROOT/'sites.json').read_text())['sites'] if s['id']==site),None)
                if loc is None:raise ValueError('Unknown site')
                key=key_for('osm',{'site':site,'lat':round(loc['lat'],5),'lon':round(loc['lon'],5),'radius_km':7.5,'schema':23})
                old=disk_read('osm',key) or {'elements':[],'provider':'Local GeoJSON import'}
                base={'canal':8_200_000,'river':8_300_000,'structures':8_400_000}[layer]
                old['elements']=[e for e in old['elements'] if not (isinstance(e.get('id'),int) and base<=e['id']<base+100_000)]+as_osm
                disk_write('osm',key,old)
            return self.reply(200,{'saved':True,'layer':layer,'count':len(clean) if polygon else len(as_osm)})
        except (ValueError,TypeError,KeyError) as exc:return self.reply(400,{'message':str(exc)[:180]})
        except Exception as exc:return self.reply(500,{'message':'Import failed: '+str(exc)[:150]})

    def peat_raster(self):
        """Render BIG ecosystem overlays as a visual fallback, not a peat-soil measurement."""
        try:
            q=parse_qs(urlparse(self.path).query);layer=int(q.get('layer',[''])[0]);b=self.bounds(q)
            if layer not in (37,48):raise ValueError('Raster is only for ecosystem/system maps')
            key=key_for('peat_raster',{'layer':layer,'bbox':{k:round(v,5) for k,v in b.items()},'v':24})
            file=ROOT/'data'/'tersimpan'/'peat_raster'/(key+'.png')
            if file.exists():data=file.read_bytes()
            else:
                params={'f':'image','bbox':','.join(str(b[v]) for v in ('w','s','e','n')),
                        'bboxSR':'4326','imageSR':'4326','size':'640,640','dpi':'96',
                        'format':'png32','transparent':'true','layers':'show:'+str(layer)}
                data,content_type=upstream(BIG+'/export?'+urlencode(params),timeout=17,limit=3_000_000,accepts='image/png')
                if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('BIG did not return a PNG map')
                file.parent.mkdir(parents=True,exist_ok=True)
                tmp=file.with_suffix('.part');tmp.write_bytes(data);os.replace(tmp,file)
            self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Cache-Control','public, max-age=604800');
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        except ValueError as exc:return self.reply(400,{'message':str(exc)[:140]})
        except Exception as exc:return self.reply(502,{'message':'BIG raster unavailable: '+str(exc)[:160]})

    def peat_mask(self):
        try:
            site=self.site_id();q=parse_qs(urlparse(self.path).query)
            lon=float(q['lon'][0]);lat=float(q['lat'][0])
            key=key_for('peat_masks',{'site':site,'lat':round(lat,5),'lon':round(lon,5),'v':23})
            saved=disk_read('peat_masks',key)
            if saved and saved.get('features'):
                return self.reply(200,{**saved,'cached':True,'status':'saved'})
            return self.reply(200,{'type':'FeatureCollection','features':[],'status':'missing'})
        except (KeyError,ValueError) as exc:return self.reply(400,{'message':str(exc)[:160]})

    def peat_shapes(self):
        q=parse_qs(urlparse(self.path).query)
        try:
            layer=int(q.get('layer',[''])[0]);b=self.bounds(q);site=self.site_id()
            if layer not in (6,37,48):raise ValueError('Unknown peat layer')
            imported=disk_read('imported_peat',key_for('imported_peat',{'site':site,'layer':layer}))
            if imported is not None:return self.reply(200,{**imported,'cached':True,'status':'saved'})
            cachekey=key_for('peat_shapes',{'layer':layer,'w':round(b['w'],5),
                's':round(b['s'],5),'e':round(b['e'],5),'n':round(b['n'],5)})
            cached=disk_read('peat_shapes',cachekey)
            if cached is not None:
                # Old zero-feature caches should be periodically checked, not frozen forever.
                age=time.time()-float(cached.get('source_updated') or 0)
                refresh=not cached.get('features') and age>PEAT_EMPTY_TTL
                refreshing=refresh_peat_async(layer,b,cachekey) if refresh else False
                return self.reply(200,{**cached,'cached':True,
                    'status':'saved' if cached.get('features') else 'empty',
                    'refreshing':refreshing})
            refreshing=refresh_peat_async(layer,b,cachekey)
            with PEAT_WORK_LOCK:status=PEAT_JOBS.get(cachekey,('unavailable',0))[0]
            return self.reply(200,{'type':'FeatureCollection','features':[],
                'source':'BIG','layer':layer,'status':status,
                'refreshing':status=='fetching' or refreshing})
        except ValueError as exc:return self.reply(400,{'message':str(exc)[:180]})
        except Exception as exc:return self.reply(502,{'message':'BIG map error: '+str(exc)[:180]})

def serve(port=8768):
    os.chdir(ROOT)
    httpd=ThreadingHTTPServer((os.getenv('BARA_BIND','127.0.0.1'),port),Handler)
    print(f'BARA-BLOCK: port {port} (Ctrl+C to stop)',flush=True)
    httpd.serve_forever()
if __name__=='__main__':serve(int(os.getenv('PORT','8768')))
