/* GitHub Pages compatibility layer for BARA-BLOCK 25.2.
 * Serves pre-existing OSM/BIG/SMAP/foundation files directly from the public
 * repository. It does not claim to provide a live Python/API backend.
 */
(()=>{'use strict';
if(!/\.github\.io$/i.test(location.hostname) && !new URLSearchParams(location.search).has('static'))return;
const realFetch=window.fetch.bind(window);
const base=new URL('.',document.baseURI),resource=p=>new URL(p,base).href;
const cache=new Map(),siteData=new Map(),refreshing=new Map();
const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
async function file(path){if(!path)return null;if(!cache.has(path))cache.set(path,realFetch(resource(path)).then(async r=>r.ok?r.json():null).catch(()=>null));return cache.get(path);}
async function asset(path){try{const r=await realFetch(resource(path),{method:'HEAD'});return r.ok?path:null}catch{return null}}
function stable(o){if(Array.isArray(o))return '['+o.map(stable).join(',')+']';if(o&&typeof o==='object')return '{'+Object.keys(o).sort().map(k=>JSON.stringify(k)+':'+stable(o[k])).join(',')+'}';return JSON.stringify(o);}
async function digest(kind,obj){
 const data=new TextEncoder().encode(kind+'|'+stable(obj));
 const hash=await crypto.subtle.digest('SHA-256',data);
 return [...new Uint8Array(hash)].map(x=>x.toString(16).padStart(2,'0')).join('').slice(0,24);
}
async function cached(kind,obj,ext='json'){
 const path='data/tersimpan/'+kind+'/'+await digest(kind,obj)+'.'+ext;
 return ext==='json'?file(path):asset(path);
}
function point(id){return(window.BARA_SITE_CATALOG?.sites||[]).find(s=>s.id===id)}
function bounds(site){const dy=7.5/111.195,dx=7.5/(111.195*Math.max(.2,Math.cos(site.lat*Math.PI/180)));return {w:site.lon-dx,s:site.lat-dy,e:site.lon+dx,n:site.lat+dy}}
async function osm(site){return cached('osm',{site:site.id,lat:site.lat,lon:site.lon,radius_km:7.5,schema:23})}
async function foundation(site){return cached('foundation',{site:site.id,lat:site.lat,lon:site.lon,v:23})}
async function peatMask(site){return cached('peat_masks',{site:site.id,lat:site.lat,lon:site.lon,v:23})}
async function peatLayer(site,layer){const b=bounds(site),values={layer};for(const k of ['w','s','e','n'])values[k]=+b[k].toFixed(5);return cached('peat_shapes',values)}
async function rasterPath(id,layer){const s=point(id);if(!s)return null;const b=bounds(s),v={};for(const k of ['w','s','e','n'])v[k]=+b[k].toFixed(5);return cached('peat_raster',{layer:+layer,bbox:v,v:24},'png')}
function metres(a,b){return Math.hypot((a.lat-b.lat)*111195,(a.lon-b.lon)*111195*Math.cos((a.lat+b.lat)*Math.PI/360))}
function candidateFallback(site,doc,saved){
 const canals=[],rivers=[],points=[];
 for(const e of doc?.elements||[]){
  const k=e.tags?.waterway||e.tags?.water||'';
  const g=(e.geometry||[]).filter(p=>Number.isFinite(p.lat)&&Number.isFinite(p.lon));
  if(e.type!=='way'||g.length<2)continue;
  if(['canal','drain','ditch'].includes(k))canals.push(g);
  else if(['river','stream','tidal_channel'].includes(k))rivers.push(g);
 }
 const lengthKm=arr=>arr.reduce((sum,g)=>sum+g.slice(1).reduce((v,p,i)=>v+metres(p,g[i]),0),0)/1000;
 for(const g of canals){
  let travelled=0,next=150;
  for(let i=1;i<g.length&&points.length<120;i++){
   const a=g[i-1],b=g[i],len=metres(a,b);
   if(len<=0)continue;
   while(travelled+len>=next&&points.length<120){
    const t=(next-travelled)/len,p={lon:+(a.lon+t*(b.lon-a.lon)).toFixed(7),lat:+(a.lat+t*(b.lat-a.lat)).toFixed(7)};
    if(!points.some(x=>metres(p,x)<220))points.push({...p,coverage_ha:null,rank:null});
    next+=450;
   }travelled+=len;
  }
 }
 return {site:site.id,status:points.length?'canals_only':'needs_canals',
  metrics:{...(saved?.metrics||{}),osm_available:!!doc,canal_count:canals.length,river_count:rivers.length,
   canal_km:+lengthKm(canals).toFixed(3),river_km:+lengthKm(rivers).toFixed(3)},
  candidates:points,selected:points.slice(0,12),version:23,
  method:'Browser-only mapped canal screening; peat coverage requires geospatial backend'};
}
const liveJobs=new Map();
function fetchLive(site){
 if(liveJobs.get(site.id)?.running)return true;
 const now=Date.now();if(now-(liveJobs.get(site.id)?.at||0)<30000)return false;
 const job={running:true,at:now};liveJobs.set(site.id,job);
 const b=bounds(site),bb=[b.s,b.w,b.n,b.e].map(x=>x.toFixed(5)).join(',');
 const query='[out:json][timeout:25];(way["waterway"~"^(canal|ditch|drain|river|stream|tidal_channel)$"]('+bb+');way["water"="canal"]('+bb+');nwr["waterway"~"^(weir|dam|sluice_gate|lock_gate)$"]('+bb+'););out geom;';
 const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),12000);
 realFetch('https://overpass.private.coffee/api/interpreter',{method:'POST',body:'data='+encodeURIComponent(query),
  headers:{'Content-Type':'application/x-www-form-urlencoded'},signal:ctrl.signal})
  .then(r=>r.ok?r.json():Promise.reject(Error('Provider unavailable')))
  .then(d=>{if(Array.isArray(d.elements)&&d.elements.length){siteData.set(site.id,{...d,provider:'OpenStreetMap live',source_updated:Date.now()/1000});
   try{localStorage.setItem('bara25-osm-'+site.id,JSON.stringify(d))}catch{}}})
  .catch(()=>{}).finally(()=>{clearTimeout(timer);job.running=false});
 return true;
}
function inPoly(lon,lat,geom){
 const polys=geom?.type==='Polygon'?[geom.coordinates]:geom?.type==='MultiPolygon'?geom.coordinates:[];
 for(const poly of polys){const ring=poly[0]||[];let hit=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){let a=ring[i],b=ring[j];if((a[1]>lat)!==(b[1]>lat)&&lon<(b[0]-a[0])*(lat-a[1])/(b[1]-a[1])+a[0])hit=!hit;}if(hit)return true;
 }return false;
}
async function handle(url,init={}){
 const route=url.pathname.split('/').at(-1),id=url.searchParams.get('site');
 const s=point(id);
 if(route==='version')return reply({app:'BARA-BLOCK',version:'25.2-pages',public_read_only:true,static_pages:true});
 if(route==='sites')return reply(await file('sites.json'));
 if(route==='edits')return (init.method||'GET').toUpperCase()==='POST'?reply({message:'Read-only Pages demo'},403):reply({canals:[],blocks:[]});
 if(route==='environment'||route==='era5'||route==='era5-land'){
  const data=await file('data/derived/smap_sites.json'),sm=data?.sites?.find(x=>x.site===id)||null;
  const weather=await file('data/derived/era5_sites.json'),era=weather?.sites?.find(x=>x.site===id)||null;
  return reply({site:id,smap:sm,era5:era,era5_status:era?'saved':'unavailable',smap_source:{source:data?.source,datetime:data?.datetime_utc},era5_source:era?{source:era.source,datetime:era.datetime_utc}:null});
 }
 if(route==='foundation'&&(init.method||'GET').toUpperCase()==='POST'){
  const req=JSON.parse(init.body||'{}'),current=point(req.site);if(!current)return reply({message:'Unknown site'},404);
  const saved=await foundation(current);
  const extra=(req.osm?.elements||[]).some(e=>Number(e.id)>=9000000);
  if(saved&&!extra&&!siteData.has(current.id))return reply({...saved,cached:true,static_pages:true});
  return reply(candidateFallback(current,req.osm,saved));
 }
 if(!s)return reply({message:'Unknown site'},404);
 if(route==='waterways'){
  const saved=await osm(s),live=siteData.get(id);
  let local=null;try{local=JSON.parse(localStorage.getItem('bara25-osm-'+id)||'null')}catch{}
  const best=live?.elements?.length?live:local?.elements?.length?local:saved;
  if(url.searchParams.get('refresh')==='1'||!best?.elements?.length)fetchLive(s);
  return reply({...best,elements:best?.elements||[],provider:best?.provider||'OSM saved',cached:!live,refreshing:liveJobs.get(id)?.running||false,
   status:best?.elements?.length?'saved':'unavailable'});
 }
 if(route==='peat-mask')return reply((await peatMask(s))||{type:'FeatureCollection',features:[],status:'missing'});
 if(route==='peat-shapes'){
  const layer=Number(url.searchParams.get('layer')),data=await peatLayer(s,layer);
  return reply({...data,features:data?.features||[],type:'FeatureCollection',layer,cached:!!data,refreshing:false});
 }
 if(route==='peat'){
  const layer=Number(url.searchParams.get('layer')),data=await peatLayer(s,layer);
  const lon=Number(url.searchParams.get('lon')),lat=Number(url.searchParams.get('lat'));
  return reply({features:(data?.features||[]).filter(f=>inPoly(lon,lat,f.geometry)).slice(0,3).map(f=>({attributes:f.properties||{}}))});
 }
 if(route==='structured'){
  const snap=await foundation(s);return snap?reply({site:s,foundation:snap,source:'Saved GitHub Pages geospatial snapshot'}):reply({message:'No saved foundation'},404);
 }
 if(route==='import-geojson')return reply({message:'Use browser-side import on GitHub Pages'},403);
 return reply({message:'Python backend required'},404);
}
window.BARA_STATIC_API={enabled:true,resource,rasterPath,foundation:async id=>point(id)?foundation(point(id)):null};
window.fetch=(input,init)=>{const url=new URL(typeof input==='string'?input:input.url,location.href);
 if(url.origin===location.origin&&url.pathname.startsWith('/api/'))return handle(url,init).catch(e=>{console.warn('BARA static bridge:',e);return reply({message:String(e)},503)});
 return realFetch(input,init);
};
})();