/* BARA-BLOCK GitHub Pages: browser bridge for bundled data, not a Python backend. */
(()=>{'use strict';
if(!/\.github\.io$/i.test(location.hostname) && new URLSearchParams(location.search).get('static')!=='1')return;
const net=window.fetch.bind(window),root=new URL('.',document.baseURI),sites=window.BARA_SITE_CATALOG?.sites||[],memo=new Map(),r=Math.PI/180;
const resolve=p=>new URL(p,root).href,site=id=>sites.find(s=>s.id===id);
function py(v,k=''){if(Array.isArray(v))return '['+v.map(x=>py(x)).join(',')+']';
 if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(a=>JSON.stringify(a)+':'+py(v[a],a)).join(',')+'}';
 if(typeof v==='number'&&Number.isInteger(v)&&['lat','lon','w','s','e','n'].includes(k))return v.toFixed(1);
 return JSON.stringify(v);}
async function sha(kind,payload){const bytes=new TextEncoder().encode(kind+'|'+py(payload)),digest=new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
 return Array.from(digest.slice(0,12),x=>x.toString(16).padStart(2,'0')).join('');}
const round=x=>Math.round((x+Number.EPSILON)*100000)/100000;
const pos=s=>({site:s.id,lat:round(s.lat),lon:round(s.lon)});
const bbox=s=>{const dy=7.5/111.195,dx=7.5/(111.195*Math.max(.2,Math.cos(s.lat*r)));return {w:s.lon-dx,s:s.lat-dy,e:s.lon+dx,n:s.lat+dy};};
async function disk(kind,data,extension='json'){const key=await sha(kind,data),url=resolve('data/tersimpan/'+kind+'/'+key+'.'+extension);
 if(memo.has(url))return memo.get(url);
 const job=net(url).then(q=>q.ok?(extension==='json'?q.json():url):null).catch(()=>null);memo.set(url,job);return job;}
async function read(s,kind,layer){const p=pos(s),b=bbox(s);
 if(kind==='osm')return disk(kind,{...p,radius_km:7.5,schema:23});
 if(kind==='foundation'||kind==='peat_masks')return disk(kind,{...p,v:23});
 if(kind==='peat_shapes')return disk(kind,{layer,...Object.fromEntries(Object.entries(b).map(([k,v])=>[k,round(v)]))});
 if(kind==='peat_raster')return disk(kind,{layer,bbox:Object.fromEntries(Object.entries(b).map(([k,v])=>[k,round(v)])),v:24},'png');
 return null;}
function validOSM(doc,s){if(!Array.isArray(doc?.elements))return {elements:[]};
 const b=bbox(s);return {...doc,elements:doc.elements.filter(e=>{if(!e)return false;
 const g=(e.geometry||[]).filter(p=>p&&Number.isFinite(p.lon)&&Number.isFinite(p.lat));
 if(e.type==='way'&&g.length<2)return false;
 if(g.length)return g.some(p=>p.lon>=b.w-.04&&p.lon<=b.e+.04&&p.lat>=b.s-.04&&p.lat<=b.n+.04);
 return e.type==='node'&&e.lon>=b.w-.04&&e.lon<=b.e+.04&&e.lat>=b.s-.04&&e.lat<=b.n+.04;})};}
const result=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{'Content-Type':'application/json; charset=utf-8'}});
function localCandidates(payload,saved){const s=site(payload.site),proposals=[],canals=[],rivers=[];
 if(!s)return saved||{status:'needs_canals',metrics:{},candidates:[],selected:[]};
 const dist=(a,b)=>Math.hypot((a.lon-b.lon)*111195*Math.cos(s.lat*r),(a.lat-b.lat)*111195);
 for(const e of payload.osm?.elements||[]){const type=e.tags?.waterway||e.tags?.water,g=(e.geometry||[]).filter(p=>p&&Number.isFinite(p.lon)&&Number.isFinite(p.lat));
 if(e.type!=='way'||g.length<2)continue;if(['canal','ditch','drain'].includes(type))canals.push({e,g,type});else if(['river','stream','tidal_channel'].includes(type))rivers.push({e,g,type});}
 for(const l of canals){let offset=150,passed=0;
 for(let i=1;i<l.g.length&&proposals.length<120;i++){const a=l.g[i-1],b=l.g[i],len=dist(a,b);if(!len)continue;
 while(passed+len>=offset&&proposals.length<120){const t=(offset-passed)/len,p={lon:a.lon+t*(b.lon-a.lon),lat:a.lat+t*(b.lat-a.lat)};
 if(dist(p,s)<10500&&!proposals.some(q=>dist(q,p)<220))proposals.push({lon:+p.lon.toFixed(7),lat:+p.lat.toFixed(7),name:l.e.tags?.name||l.type,line_id:'way:'+l.e.id,type:l.type,coverage_ha:null});offset+=450;}passed+=len;}}
 const length=lines=>lines.reduce((sum,l)=>sum+l.g.slice(1).reduce((n,p,i)=>n+dist(p,l.g[i]),0),0);
 const metrics={...(saved?.metrics||{}),osm_available:!!payload.osm,canal_count:canals.length,river_count:rivers.length,canal_km:+(length(canals)/1000).toFixed(3),river_km:+(length(rivers)/1000).toFixed(3)};
 return {status:proposals.length?'canals_only':'needs_canals',metrics,candidates:proposals,selected:proposals.slice(0,12),method:'browser-canal-screening; no computed peat buffer'};}
async function api(url,init={}){const name=url.pathname.split('/').at(-1),id=url.searchParams.get('site'),s=site(id);
 try{
 if(name==='version')return result({version:'25.2-github-pages',public_read_only:true,static_pages:true});
 if(name==='edits')return (init.method||'GET').toUpperCase()==='POST'?result({message:'Local browser storage only'},403):result({canals:[],blocks:[]});
 if(name==='foundation'){const body=JSON.parse(init.body||'{}'),target=site(body.site);if(!target)return result({message:'Unknown site'},404);
 const saved=await read(target,'foundation'),custom=(body.osm?.elements||[]).some(e=>Number(e.id)>=9000000);
 return result(custom?localCandidates(body,saved):saved||localCandidates(body,null));}
 if(!s)return result({message:'Unknown site'},404);
 if(name==='waterways'){const doc=validOSM(await read(s,'osm'),s);
 // The existing browser code fetches Overpass directly after a failed API call.
 if(url.searchParams.has('refresh')||!doc.elements.length)return result({message:'Try direct Overpass'},503);
 return result({...doc,cached:true,saved:true,refreshing:false});}
 if(name==='peat-mask')return result(await read(s,'peat_masks')||{type:'FeatureCollection',features:[]});
 if(name==='peat-shapes'){const d=await read(s,'peat_shapes',+url.searchParams.get('layer'));
 return result({...d||{type:'FeatureCollection',features:[]},cached:!!d,refreshing:false});}
 if(name==='peat')return result({features:[]});
 if(name==='environment'||name==='era5'||name==='era5-land'){const q=await net(resolve('data/derived/smap_sites.json')),d=q.ok?await q.json():{};
 return result({site:id,smap:(d.sites||[]).find(x=>x.site===id)||null,era5:null,era5_status:'unavailable',smap_source:{source:d.source,datetime:d.datetime_utc},mode:'historical cached data'});}
 if(name==='structured')return result({site:s,foundation:await read(s,'foundation')});
 if(name==='import-geojson')return result({message:'Browser-only import'},403);
 return result({message:'Requires a Python backend'},404);
 }catch(e){console.warn('BARA static source',name,e);return result({message:'Static source unavailable'},503)}}
window.BARA_STATIC_API={enabled:true,resource:resolve,rasterPath:async(id,layer)=>{const s=site(id);return s?read(s,'peat_raster',layer):null;}};
window.fetch=(input,init)=>{const u=new URL(typeof input==='string'?input:input.url,location.href);return u.origin===location.origin&&u.pathname.startsWith('/api/')?api(u,init):net(input,init);};
})();