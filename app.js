(()=>{'use strict';
const $=id=>document.getElementById(id),RAD=Math.PI/180,PI=Math.PI;
const clip=(v,a,b)=>Math.max(a,Math.min(b,v));
const D=(a,b,c,d)=>{const dy=(b-d)*111195,dx=(a-c)*111195*Math.cos((b+d)/2*RAD);return Math.hypot(dx,dy)};
const STATIC_PAGES=Boolean(window.BARA_STATIC_API?.enabled);
const S={osmRaw:null,peatRaw:null,foundation:null,foundationReady:false,foundationToken:0,rankedBlockPlaces:[],fireRankStatus:null,customCanals:[],drawPoints:[],site:null,lat:-5.53,lon:138.15,z:11.5,mode:'inspect',tiles:new Map(),tileLoads:0, sar:null,sarToken:0,env:null,envToken:0,envPollTimer:null,manualWind:false,manualDirection:false,networkUpdated:null,autoRefresh:null,w:800,h:520,dpr:1,canals:[],rivers:[],structures:[],searchId:0,searchStatus:'idle',scanBounds:null,baseLayer:'terrain',peatRasters:{},showSoil:true,blockPlaces:[],manual:[],shownBlocks:[],gis:{khg:null,feg:null},gisShapes:[],gisLoading:false,showKHG:true,showFEG:true,water:65,weather:'dry',wind:18,direction:90,teams:0,arrival:8,blocks:3,horizon:48,ignition:null,fire:null,baseFire:null,hour:0,playing:false,interval:null,drag:null};
window.BARA25={state:S,scan:()=>scanWaterways(true),sim:()=>simulate(true),rank:()=>simulate(true),play:()=>play()};window.BARA29=window.BARA25;window.BARA24=window.BARA25;
const papua=[
['PAP-01','Papua','South Papua','Agats · Asmat',-5.53,138.15],['PAP-02','Papua','South Papua','Merauke Lowlands',-8.48,140.38],['PAP-03','Papua','South Papua','Mappi Lowlands',-6.14,139.36],['PAP-04','Papua','Papua','Sarmi Coastal Peat',-1.87,138.75],['PAP-05','Papua','Papua','Mamberamo Floodplain',-2.55,138.15],['PAP-06','Papua','Central Papua','Mimika Lowlands',-4.54,136.89],['PAP-07','Papua','Papua','Waropen Coast',-2.37,136.51],['PAP-08','Papua','South Papua','Boven Digoel',-5.77,140.42]];
const sites=(window.BARA_SITE_CATALOG?.sites||[]).length?window.BARA_SITE_CATALOG.sites:[...(BARA_SEED.cells||[]).map(c=>({id:c.cell_id||c.id,island:c.island,province:c.province,name:c.landscape,lat:c.latitude,lon:c.longitude})),...papua.map(x=>({id:x[0],island:x[1],province:x[2],name:x[3],lat:x[4],lon:x[5]}))];
const baseC=$('baseCanvas'),ovC=$('overlayCanvas'),baseCtx=baseC.getContext('2d'),ovCtx=ovC.getContext('2d');
const project=(lon,lat,z)=>{const n=256*2**z,s=Math.sin(clip(lat,-85,85)*RAD);return [(lon+180)/360*n,(.5-Math.log((1+s)/(1-s))/(4*PI))*n]};
const unproject=(x,y,z)=>{const n=256*2**z;return [x/n*360-180,Math.atan(Math.sinh(PI*(1-2*y/n)))/RAD]};
function VP(){const [x,y]=project(S.lon,S.lat,S.z);return {w:S.w,h:S.h,z:S.z,left:x-S.w/2,top:y-S.h/2}};
function xy(lon,lat,v=VP()){const [x,y]=project(lon,lat,v.z);return [x-v.left,y-v.top]};
function lnglat(x,y,v=VP()){return unproject(v.left+x,v.top+y,v.z)};
function bbox(){const v=VP(),a=lnglat(0,v.h,v),b=lnglat(v.w,0,v);return {w:clip(Math.min(a[0],b[0]),94,144),s:clip(Math.min(a[1],b[1]),-12,7),e:clip(Math.max(a[0],b[0]),94,144),n:clip(Math.max(a[1],b[1]),-12,7)};}
function msg(t){$('mapMessage').textContent=t}
function resize(){const r=$('mapStage').getBoundingClientRect();const oldW=S.w,oldH=S.h;S.w=Math.max(320,r.width);S.h=Math.max(230,r.height);S.dpr=Math.min(window.devicePixelRatio||1,2);for(const c of [baseC,ovC]){c.width=Math.round(S.w*S.dpr);c.height=Math.round(S.h*S.dpr);c.getContext('2d').setTransform(S.dpr,0,0,S.dpr,0,0)}drawBase();drawOverlay();updateScale();}
const MAP_SOURCES={
 street:{url:(z,x,y)=>`https://tile.openstreetmap.org/${z}/${x}/${y}.png`,credit:'© OpenStreetMap contributors',maxZoom:19},
 satellite:{url:(z,x,y)=>`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`,credit:'Tiles © Esri · Maxar · Earthstar Geographics',maxZoom:19},
 terrain:{url:(z,x,y)=>`https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/${z}/${y}/${x}`,credit:'Tiles © Esri · © OpenStreetMap',maxZoom:19}
};
function tileUrl(z,x,y){return MAP_SOURCES[S.baseLayer].url(z,x,y)}
function getTile(url){let tile=S.tiles.get(url);if(tile)return tile;tile={img:new Image(),ok:false,failed:false};S.tiles.set(url,tile);tile.img.onload=()=>{tile.ok=true;tile.failed=false;drawBase()};tile.img.onerror=()=>{tile.failed=true;drawBase()};tile.img.src=url;if(S.tiles.size>155){for(const key of S.tiles.keys()){S.tiles.delete(key);if(S.tiles.size<=125)break}}return tile;}
function drawGeoFallback(ctx,v){
 ctx.save();
 const mid=lnglat(S.w/2,S.h/2,v),lonSpan=Math.abs(lnglat(S.w,0,v)[0]-lnglat(0,0,v)[0]);
 const grid=lonSpan>.55?.2:lonSpan>.25?.1:lonSpan>.12?.05:lonSpan>.06?.02:.01;
 const b=bbox();
 ctx.lineWidth=.65;ctx.strokeStyle='#78c5c521';ctx.setLineDash([4,7]);
 for(let lat=Math.ceil(b.s/grid)*grid;lat<b.n;lat+=grid){const y=xy(S.lon,lat,v)[1];ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(S.w,y);ctx.stroke();ctx.fillStyle='#89baaf70';ctx.font='9px DM Sans';ctx.fillText(Math.abs(lat).toFixed(2)+'°'+(lat<0?'S':'N'),8,y-5);}
 for(let lon=Math.ceil(b.w/grid)*grid;lon<b.e;lon+=grid){const x=xy(lon,S.lat,v)[0];ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,S.h);ctx.stroke();ctx.fillStyle='#89baaf70';ctx.font='9px DM Sans';ctx.fillText(lon.toFixed(2)+'°E',x+4,S.h-45);}
 ctx.setLineDash([]);
 ctx.lineWidth=.75;ctx.strokeStyle='#77bfac35';ctx.fillStyle='#1d4141';const coast=BARA_SEED.coastlines?.features||[];
 for(const f of coast){const g=f.geometry,polys=g?.type==='Polygon'?[g.coordinates]:g?.type==='MultiPolygon'?g.coordinates:[];for(const p of polys){const ring=p[0]||[];if(ring.length<3)continue;ctx.beginPath();let a=0;for(let i=0;i<ring.length;i+=Math.max(1,Math.floor(ring.length/700))){const [x,y]=xy(ring[i][0],ring[i][1],v);if(a++)ctx.lineTo(x,y);else ctx.moveTo(x,y)}ctx.closePath();ctx.fill();ctx.stroke()}}
 const mpp=Math.cos(S.lat*RAD)*40075016.6856/(256*2**S.z);const c=xy(S.site?.lon??S.lon,S.site?.lat??S.lat,v);
 ctx.setLineDash([5,6]);ctx.strokeStyle='#7ae2c133';ctx.lineWidth=1;
 for(const r of [1000,3000,5000,10000,20000]){const pix=r/mpp;if(pix<35||pix>Math.max(S.w,S.h)*.8)continue;ctx.beginPath();ctx.arc(c[0],c[1],pix,0,2*PI);ctx.stroke();ctx.fillStyle='#89dfc190';ctx.font='10px DM Sans';ctx.fillText((r/1000)+' km',c[0]+pix+6,c[1]-3)}
 ctx.setLineDash([]);ctx.restore();}
function drawBase(){
 if(!S.w)return;
 const v=VP(),ctx=baseCtx;
 ctx.clearRect(0,0,S.w,S.h);ctx.fillStyle='#18363d';ctx.fillRect(0,0,S.w,S.h);
 // Draw local outline first, then overlay live viewport-only basemap tiles.
 drawGeoFallback(ctx,v);
 const zi=Math.min(Math.floor(v.z),MAP_SOURCES[S.baseLayer].maxZoom),fac=2**(v.z-zi),sz=256*fac,max=2**zi;
 const x0=Math.floor(v.left/sz),y0=Math.floor(v.top/sz),x1=Math.ceil((v.left+S.w)/sz),y1=Math.ceil((v.top+S.h)/sz);
 let any=false;
 for(let y=y0;y<=y1;y++){
  if(y<0||y>=max)continue;
  for(let x=x0;x<=x1;x++){
   const xx=((x%max)+max)%max,t=getTile(tileUrl(zi,xx,y));
   if(t.ok){ctx.drawImage(t.img,x*sz-v.left,y*sz-v.top,sz+.6,sz+.6);any=true;}
  }
 }
 $('mapCredit').textContent=MAP_SOURCES[S.baseLayer].credit + ' · BIG';
}
function polyInside(p,geom){if(!geom)return false;const polys=geom.type==='Polygon'?[geom.coordinates]:geom.type==='MultiPolygon'?geom.coordinates:[];for(const poly of polys){const ring=poly[0];let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if(((a[1]>p[1])!==(b[1]>p[1]))&&(p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]))inside=!inside;}if(inside)return true;}return false;}
function drawPoly(g,ctx,v){const polys=g?.type==='Polygon'?[g.coordinates]:g?.type==='MultiPolygon'?g.coordinates:[];for(const poly of polys){if(!poly[0]?.length)continue;ctx.beginPath();let p=0;for(const ring of poly){for(let i=0;i<ring.length;i+=Math.max(1,Math.floor(ring.length/1300))){const pt=xy(ring[i][0],ring[i][1],v);if(!p++)ctx.moveTo(...pt);else ctx.lineTo(...pt);}ctx.closePath()}ctx.fill();ctx.stroke();}}
function drawOverlay(){const ctx=ovCtx,v=VP();ctx.clearRect(0,0,S.w,S.h);ctx.save();
 // Fallback BIG raster overlays preserve peat ecosystem boundaries when polygon requests fail.
 for(const layer of ['khg','feg']){const item=S.peatRasters?.[layer];if(!item?.img?.complete||!item.img.naturalWidth)continue;if(layer==='khg'&&!S.showKHG||layer==='feg'&&!S.showFEG)continue;const a=xy(item.bounds.w,item.bounds.n,v),b=xy(item.bounds.e,item.bounds.s,v);ctx.globalAlpha=.5;ctx.drawImage(item.img,a[0],a[1],b[0]-a[0],b[1]-a[1]);ctx.globalAlpha=1;}
 for(const layer of S.gisShapes){if(layer.type==='khg'&&!S.showKHG||layer.type==='feg'&&!S.showFEG||layer.type==='soil'&&!S.showSoil)continue;
 ctx.fillStyle=layer.type==='soil'?'#beee7045':layer.type==='khg'?'#2ac8da10':'#b4eb4520';
 ctx.strokeStyle=layer.type==='soil'?'#d3ff8e':layer.type==='khg'?'#3cd5e4':'#b1e65a';ctx.lineWidth=layer.type==='soil'?2.6:1.6;drawPoly(layer.geometry,ctx,v);
 }ctx.restore();
 const drawLine=(f,col,width,dash=[])=>{const pts=f.points;if(!pts?.length)return;ctx.save();ctx.strokeStyle=col;ctx.lineWidth=width;ctx.lineJoin='round';ctx.lineCap='round';ctx.setLineDash(dash);ctx.beginPath();pts.forEach((p,i)=>{const s=xy(p[0],p[1],v);if(i)ctx.lineTo(...s);else ctx.moveTo(...s)});ctx.stroke();ctx.restore()};
 for(const l of S.rivers){drawLine(l,'#17344d',6.0);drawLine(l,'#75a6ff',3.3)}
 for(const l of S.canals){drawLine(l,'#173c46',6.2);drawLine(l,'#5ce0df',3.8)}
 for(const l of S.customCanals){drawLine(l,'#132922',7);drawLine(l,'#ffe59a',3.6)}
 if(S.drawPoints?.length){drawLine({points:S.drawPoints},'#ffdf83',3,[5,5]);for(const p of S.drawPoints){let [x,y]=xy(...p,v);ctx.beginPath();ctx.arc(x,y,5,0,2*PI);ctx.fillStyle='#ffdf83';ctx.fill()}}
 drawFire(ctx,v);
 for(const f of S.structures){let [x,y]=xy(f.lon,f.lat,v);if(x<-15||x>S.w+15||y<-15||y>S.h+15)continue;ctx.save();ctx.beginPath();ctx.arc(x,y,6.2,0,PI*2);ctx.fillStyle=f.hasBlockTag?'#f6e5b4':'#f7cc77';ctx.fill();ctx.lineWidth=2;ctx.strokeStyle='#2e3530';ctx.stroke();ctx.restore();}
 const usedLabels=[];
 for(const p of S.shownBlocks){
  const [x,y]=xy(p.lon,p.lat,v);
  if(x<-22||x>S.w+22||y<-22||y>S.h+22)continue;
  const choices=[[0,0],[0,-25],[0,25],[25,0],[-25,0],[25,-25],[-25,-25],[25,25],[-25,25],[0,-50],[0,50]];
  const preferred=choices.find(([dx,dy])=>usedLabels.every(([ux,uy])=>Math.hypot(x+dx-ux,y+dy-uy)>=24)&&x+dx>12&&x+dx<S.w-12&&y+dy>12&&y+dy<S.h-12)||[0,0];
  const [lx,ly]=[x+preferred[0],y+preferred[1]];usedLabels.push([lx,ly]);
  ctx.save();
  if(preferred[0]||preferred[1]){
   ctx.strokeStyle='#b8f1c0';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(lx,ly);ctx.stroke();
   ctx.fillStyle='#c5f4cc';ctx.beginPath();ctx.arc(x,y,3,0,PI*2);ctx.fill();
  }
  ctx.beginPath();ctx.arc(lx,ly,10,0,PI*2);
  ctx.fillStyle=p.isOptimized?'#a7efb8':'#ffdc92';ctx.fill();
  ctx.lineWidth=2.5;ctx.strokeStyle='#124632';ctx.stroke();
  ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle='#183d30';ctx.font='bold 10px DM Sans';
  ctx.fillText(p.displayRank??'M',lx,ly);ctx.restore();
 }
 if(S.ignition){const [x,y]=xy(S.ignition.lon,S.ignition.lat,v);ctx.save();ctx.strokeStyle='#ffdaa4';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,13,0,PI*2);ctx.stroke();ctx.fillStyle='#ffb873';ctx.beginPath();ctx.arc(x,y,4,0,PI*2);ctx.fill();ctx.restore();}}
function drawFire(ctx,v){const f=S.fire;if(!f?.frames)return;const frame=f.frames[Math.min(f.frames.length-1,S.hour)],geo=f.geo,w=f.nx,h=f.ny;const size=clip(geo.step/(Math.cos(S.lat*RAD)*40075016.6856/(256*2**S.z)),1.7,90);const cells=frame.cells;ctx.save();ctx.globalAlpha=.80;const stepX=geo.step/(111195*Math.cos(geo.lat*RAD)),stepY=geo.step/111195;for(let j=0;j<h;j++)for(let i=0;i<w;i++){const cell=cells[j*w+i];if(!cell)continue;const lon=geo.lon+(i-w/2)*stepX,lat=geo.lat+(j-h/2)*stepY,[x,y]=xy(lon,lat,v);if(x<0||x>S.w||y<0||y>S.h)continue;ctx.fillStyle=cell===1?'#ffaf4b':cell===2?'#ad3a35':'#c36b52';ctx.fillRect(x-size*.48,y-size*.48,size*.96+1,size*.96+1);}ctx.restore();}
function updateScale(){const metersPerPixel=Math.cos(S.lat*RAD)*40075016.6856/(256*2**S.z),ideal=100*metersPerPixel;const ladder=[1,2,5].flatMap(a=>Array.from({length:9},(_,i)=>a*10**i));const value=ladder.filter(n=>n<=ideal).at(-1)||1;const width=value/metersPerPixel;$('scaleLine').style.width=Math.round(width)+'px';$('scaleText').textContent=`${+(value/1000).toFixed(2)} km`;$('mapCoords').textContent=`${Math.abs(S.lat).toFixed(3)}° ${S.lat<0?'S':'N'} · ${Math.abs(S.lon).toFixed(3)}° E`}
function pan(dx,dy){const v=VP(),[lon,lat]=unproject(v.left+S.w/2-dx,v.top+S.h/2-dy,S.z);S.lon=lon;S.lat=clip(lat,-83,83);drawBase();drawOverlay();updateScale()}
function zoom(delta,px=S.w/2,py=S.h/2){const v=VP(),pivot=lnglat(px,py,v);S.z=clip(S.z+delta,5.1,16.5);const p=project(...pivot,S.z),[x,y]=unproject(p[0]+S.w/2-px,p[1]+S.h/2-py,S.z);S.lon=x;S.lat=y;drawBase();drawOverlay();updateScale();scheduleGeo();scheduleScan();}
function nearestLine(lon,lat){let best=null,dist=Infinity;for(const line of [...S.customCanals,...S.canals,...S.rivers]){const p=line.points||[];for(let j=1;j<p.length;j++){const a=p[j-1],b=p[j],ax=a[0]*Math.cos(lat*RAD),bx=b[0]*Math.cos(lat*RAD),px=lon*Math.cos(lat*RAD);let t=clip(((px-ax)*(bx-ax)+(lat-a[1])*(b[1]-a[1]))/(Math.pow(bx-ax,2)+Math.pow(b[1]-a[1],2)||1),0,1);const q=[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])],d=D(lon,lat,...q);if(d<dist){dist=d;best={line,lon:q[0],lat:q[1],dist:d}}}}return best;}
function siteSelect(site,fly=true){
 pause();clearTimeout(osmRefreshTimer);S.site=site;const siteKey=site.id==='CUSTOM'?`CUSTOM-${site.lat.toFixed(4)}-${site.lon.toFixed(4)}`:site.id;
 S.siteKey=siteKey.replace(/[^A-Za-z0-9_-]/g,'_');if($('placeSelect'))$('placeSelect').value=site.id;S.editSeq=(S.editSeq||0)+1;
 if(fly){S.lat=site.lat;S.lon=site.lon;S.z=12.35}
 S.ignition={lat:site.lat+.004,lon:site.lon-.004};
 S.canals=[];S.rivers=[];S.structures=[];S.customCanals=[];S.drawPoints=[];

 S.blockPlaces=[];S.rankedBlockPlaces=[];S.fireRankStatus=null;S.browserImports={};S.manual=[];S.shownBlocks=[];S.lastScanKey=null;
 $('burnMetric').textContent=$('endMetric').textContent=$('benefitMetric').textContent='—';S.osmRaw=null;S.peatRaw=null;S.foundation=null;S.foundationReady=false;S.foundationToken++;S.fire=null;S.baseFire=null; 
 S.gisShapes=[];S.peatRasters={};S.gis={khg:null,feg:null};S.env=null;S.peatLayerDocs={};S.foundationRequestId=(S.foundationRequestId||0)+1;clearTimeout(S.envPollTimer);S.envPollTimer=null;S.manualWind=false;S.manualDirection=false;S.envToken++;$('smapValue').textContent='Loading';$('era5Value').textContent='Loading';$('exportSite').href=STATIC_PAGES?'#':'/api/structured?site='+encodeURIComponent(S.siteKey);
 $('mapTitle').textContent=site.name;$('mapSubtitle').textContent=`${site.province} · ${site.island} · 15 × 15 km AOI`;updateSiteMetrics(site.coverage);
 $('canalNum').textContent=$('riverNum').textContent=$('structureNum').textContent='—';
 $('scanState').textContent='Loading';$('scanExplain').textContent='';
 $('drawBar').hidden=true;renderBlocks();updateScale();drawBase();drawOverlay();simulate(true);
 restoreWaterways();const editTask=loadEdits();loadEnvironment(site,S.envToken);initializeSite(site,S.foundationToken,editTask);
}
function selectLocationOptions(){let sel=$('placeSelect');sel.innerHTML='';for(const island of ['Sumatra','Kalimantan','Papua']){let group=document.createElement('optgroup');group.label=island;for(const s of sites.filter(x=>x.island===island)){const opt=document.createElement('option');opt.value=s.id;opt.textContent=`${s.name} · ${s.province}`;group.appendChild(opt)}sel.appendChild(group)}sel.value='PAP-01';}
function setMode(mode){
 S.mode=mode;document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
 if(mode!=='canal'){$('drawBar').hidden=true;S.drawPoints=[];drawOverlay()}
 else{$('drawBar').hidden=false;updateDrawCount()}
 msg(({inspect:'Tap a waterway',ignite:'Place ignition on map',block:'Tap a canal to add a block',canal:'Tap points to draw a canal',erase:'Tap an edit to erase'})[mode]||'Ready');
}
function handleMapClick(px,py){
 const [lon,lat]=lnglat(px,py);
 if(lon<94||lon>144||lat< -12||lat>7){msg('Select a point in Indonesia');return}
 const mpp=Math.cos(lat*RAD)*40075016.6856/(256*2**S.z);
 if(S.mode==='ignite'){S.ignition={lon,lat};S.hour=0;drawOverlay();simulate(true);msg('Fire point set. Press Play');return}
 if(S.mode==='canal'){S.drawPoints.push([lon,lat]);updateDrawCount();drawOverlay();msg('Add points, then Save');return}
 const near=nearestLine(lon,lat);
 if(S.mode==='erase'){
   let bi=-1,best=Infinity;
   S.manual.forEach((q,i)=>{let d=D(lon,lat,q.lon,q.lat);if(d<best){best=d;bi=i}});
   if(bi>=0 && best<Math.max(85,mpp*15)){
      S.manual.splice(bi,1);S.blocks=Math.min(S.blocks,S.manual.length+S.blockPlaces.length);
      $('blocksInput').value=S.blocks;$('blocksValue').textContent=S.blocks;
      setBlocks();simulate(true);saveEdits();msg('Block removed');return;
   }
   if(near?.line?.kind==='custom' && near.dist<Math.max(80,mpp*12)){
      S.customCanals=S.customCanals.filter(c=>c!==near.line);
      loadFoundation(true);saveEdits();msg('Canal removed');return;
   }
   msg('Select a saved edit');return;
 }
 if(S.mode==='block'){
   if(!near||near.dist>Math.max(mpp*18,110)||near.line.kind==='river'){
      msg('Tap an artificial canal');return;
   }
   S.manual.push({lon:near.lon,lat:near.lat,kind:'custom-block',name:near.line.name||'Drawn block'});
   S.blocks=Math.min(12,Math.max(S.blocks,S.manual.length));$('blocksInput').value=S.blocks;$('blocksValue').textContent=S.blocks;
   setBlocks();simulate(true);saveEdits();msg('Block saved');return;
 }
 if(near&&near.dist<mpp*12){msg(`${near.line.kind==='river'?'River':'Canal'}: ${near.line.name||'Unnamed'} · ${Math.round(near.dist)} m away.`);return}
 const custom={id:'CUSTOM',island:'Map point',province:'Custom site',name:`Point ${lat.toFixed(3)}, ${lon.toFixed(3)}`,lat,lon};
 S.lat=lat;S.lon=lon;siteSelect(custom,false);msg('Loading site');
}
function scanBounds(){let b=bbox();return b;}
function validBBox(b){return b.w<b.e&&b.s<b.n&&(b.e-b.w)<=.66&&(b.n-b.s)<=.55;}
function prettyServerError(e){return String(e.message||e).slice(0,160)}
async function postOverpass(query,signal){let last='';for(const host of ['https://overpass.private.coffee/api/interpreter','https://overpass-api.de/api/interpreter','https://overpass.maprva.org/api/interpreter']){if(signal?.aborted)throw Error('Canceled');const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),11500);if(signal)signal.addEventListener('abort',()=>ctrl.abort(),{once:true});try{const r=await fetch(host,{method:'POST',body:'data='+encodeURIComponent(query),headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},signal:ctrl.signal});if(!r.ok)throw Error(`HTTP ${r.status}`);let d=await r.json();if(!Array.isArray(d.elements))throw Error(d.remark||'Unexpected response');d.provider=new URL(host).hostname;return d}catch(e){last=prettyServerError(e)}finally{clearTimeout(timer)}}throw Error(last||'OSM providers unavailable')}
function overpassQuery(b){let bb=[b.s,b.w,b.n,b.e].map(x=>+x.toFixed(5)).join(',');return `[out:json][timeout:28];(way["waterway"~"^(canal|ditch|drain|river|stream|tidal_channel)$"](${bb});way["water"="canal"](${bb});nwr["waterway"~"^(weir|dam|sluice_gate|lock_gate)$"](${bb});nwr["man_made"~"^(dam|weir)$"](${bb});nwr["sekat_kanal"](${bb});nwr["canal_block"](${bb}););out geom;`}
// Cached geometry is shown instantly. Server refreshes OSM after its TTL; sync forces a live check.
function waterwaysKey(){return 'bara25-osm-'+S.siteKey;}
function acceptWaterways(doc,tag){
 if(!Array.isArray(doc?.elements))throw Error('Invalid OSM geometry');
 if(!doc.elements.length && S.osmRaw?.elements?.length)return false;
 const result=parseOSM(doc);
 S.osmRaw=doc;S.canals=result.canals;S.rivers=result.rivers;S.structures=result.structures;S.scanBounds=S.site;
 $('canalNum').textContent=result.canals.length.toLocaleString('en-US');
 $('riverNum').textContent=result.rivers.length.toLocaleString('en-US');
 $('structureNum').textContent=result.structures.length.toLocaleString('en-US');
 $('scanState').textContent=tag||'OSM';
 $('scanExplain').textContent=`${result.canals.length} canals/drains · ${result.rivers.length} rivers · ${result.structures.length} structures`;
 try{if(doc.elements.length)localStorage.setItem(waterwaysKey(),JSON.stringify(doc));}catch(e){}
 drawOverlay();return true;
}
function restoreWaterways(){
 try{const saved=JSON.parse(localStorage.getItem(waterwaysKey())||'null');if(saved?.elements?.length){acceptWaterways(saved,'Cached');return true;}}
 catch(e){}return false;
}
let osmRefreshTimer=null;
function scheduleScan(){/* Keep fixed site footprint; server performs expiry-controlled live updates. */}
async function scanWaterways(force=false,attempt=0){
 const site=S.site;if(!site)return;
 const token=++S.searchId;
 if(S.scanController)S.scanController.abort();
 const ctrl=new AbortController();S.scanController=ctrl;
 const had=restoreWaterways() || Boolean(S.osmRaw?.elements?.length);
 $('scanBtn').disabled=true;$('scanState').textContent=had?'Cached · Syncing':'Loading OSM';
 try{
  const params=new URLSearchParams({lon:site.lon,lat:site.lat,site:S.siteKey});if(force)params.set('refresh','1');
  let doc=null;
  if(['http:','https:'].includes(location.protocol)){
   try{const res=await fetch('/api/waterways?'+params,{signal:ctrl.signal});if(!res.ok)throw Error('OSM HTTP '+res.status);doc=await res.json();if(!Array.isArray(doc.elements))throw Error('Invalid OSM result');}
   catch(error){if(ctrl.signal.aborted)throw error;}
  }
  if(!doc){const km=7.5,dy=km/111.195,dx=km/(111.195*Math.max(.2,Math.cos(site.lat*RAD)));
   doc=await postOverpass(overpassQuery({s:site.lat-dy,n:site.lat+dy,w:site.lon-dx,e:site.lon+dx}),ctrl.signal);
  }
  if(token!==S.searchId)return;
  const updated=acceptWaterways(doc,doc.refreshing?(doc.elements.length?'Cached · Updating':'Loading OSM'):doc.cached?'Cached':'Mapped');
  if(!doc.elements.length && !had)$('scanState').textContent='No OSM features';
  if(updated && doc.elements.length)queueFoundation(true);
  // Once per opening, check asynchronously for new geometry written by the server.
  if(doc.refreshing){clearTimeout(osmRefreshTimer);const currentKey=S.siteKey;
   const pauseMs=doc.elements.length?7000:Math.min(6500,1700+attempt*950);
   if(attempt<24)osmRefreshTimer=setTimeout(()=>{if(S.siteKey===currentKey && !S.scanController)scanWaterways(false,attempt+1)},pauseMs);
  }
 }catch(error){if(token!==S.searchId||ctrl.signal.aborted)return;
  $('scanState').textContent=S.osmRaw?.elements?.length?'Cached':'OSM unavailable';
  $('scanExplain').textContent=S.osmRaw?.elements?.length?'Saved map retained':'Network unavailable';
 }finally{if(token===S.searchId){$('scanBtn').disabled=false;S.scanController=null;}}
}
function parseOSM(doc){const canals=[],rivers=[],structures=[],ids=new Set();for(const e of doc.elements||[]){let key=e.type+':'+e.id;if(ids.has(key))continue;ids.add(key);const t=e.tags||{},kind=t.waterway||t.water||'',points=(e.geometry||[]).filter(p=>p&&Number.isFinite(p.lat)&&Number.isFinite(p.lon)&&(!S.site||Math.abs(p.lat-S.site.lat)<.12&&Math.abs(p.lon-S.site.lon)<.14)).map(p=>[p.lon,p.lat]);if(e.type==='way'&&points.length>=2){let line={id:key,points,name:t.name||'',tags:t,kind:/^(canal|drain|ditch)$/.test(kind)||t.water==='canal'?'canal':'river'};if(line.kind==='canal')canals.push(line);else if(/^(river|stream|tidal_channel)$/.test(kind))rivers.push(line)}const isStruct=Boolean(t.structure||t.sekat_kanal||t.canal_block||/^(weir|dam|sluice_gate|lock_gate|floodgate)$/.test(t.waterway||'')||/^(weir|dam|pumping_station)$/.test(t.man_made||'')||(t.tunnel==='culvert'||t.culvert==='yes'||t.pump==='yes')||/^(dam|sluice_gate)$/.test(t.barrier||''));if(isStruct){const p=e.type==='node'?e:e.center||e.geometry?.[Math.floor((e.geometry?.length||1)/2)];if(p?.lon!=null&&p?.lat!=null&&(!S.site||Math.abs(p.lat-S.site.lat)<.12&&Math.abs(p.lon-S.site.lon)<.14))structures.push({id:key,lon:p.lon,lat:p.lat,hasBlockTag:!!(t.sekat_kanal||t.canal_block),kind:t.waterway||t.man_made||'tagged water structure',name:t.name||''})}}return {canals,rivers,structures}}
function recommendBlocks(){
 if(!S.blockPlaces.length){msg('Map or draw canals for block locations');return;}
 simulate(true);
 msg('Block priorities follow the fire');
}
function setBlocks(){
 const count=Math.max(0,S.blocks),chosen=[...S.manual];
 const proposals=S.fireRankStatus==='no-fire'?[]:S.fireRankStatus==='fire'?S.rankedBlockPlaces:S.blockPlaces;
 for(const p of proposals){
  if(chosen.length>=count)break;
  if(chosen.some(q=>D(p.lon,p.lat,q.lon,q.lat)<400))continue;
  chosen.push({...p,isOptimized:true});
 }
 // Manual edits retain M markers; numbers are reserved for fire-ranked proposals.
 let num=0;S.shownBlocks=chosen.slice(0,count).map(p=>({...p,displayRank:p.isOptimized?++num:null}));
 drawOverlay();
}
function renderBlocks(){
 const el=$('blockList'),ranked=S.fireRankStatus==='no-fire'?[]:S.fireRankStatus==='fire'?S.rankedBlockPlaces:S.blockPlaces;
 el.innerHTML='';
 if(!ranked.length){el.innerHTML='<p class="empty">'+(S.fireRankStatus==='no-fire'?'Place fire on mapped peat':'No canal block sites')+'</p>';return;}
 for(let i=0;i<Math.min(8,ranked.length);i++){
  const p=ranked[i],b=document.createElement('button');b.className='blockItem';
  const x=document.createElement('b');x.textContent=i+1;
  const t=document.createElement('span');t.textContent=p.name||'Canal';
  const sm=document.createElement('small');
  const distance=p.fire_distance_m;
  sm.textContent=(Number.isFinite(distance)?`${distance<1000?Math.round(distance)+' m':(distance/1000).toFixed(1)+' km'} to fire · `:'')+(p.coverage_ha==null?'Peat loading':`${p.coverage_ha} ha peat`);
  t.appendChild(sm);b.append(x,t);
  b.onclick=()=>{S.lon=p.lon;S.lat=p.lat;S.z=Math.max(S.z,13.4);drawBase();drawOverlay();updateScale();msg(`Block ${i+1}`)};
  el.appendChild(b);
 }
}
function fitNetwork(){const pts=[...S.canals,...S.customCanals,...S.rivers].flatMap(x=>x.points);for(const s of S.structures)pts.push([s.lon,s.lat]);if(!pts.length){msg('No waterways');return;}let west=Infinity,east=-Infinity,south=Infinity,north=-Infinity;for(const [lon,lat]of pts){west=Math.min(west,lon);east=Math.max(east,lon);south=Math.min(south,lat);north=Math.max(north,lat)}S.lon=(west+east)/2;S.lat=(south+north)/2;for(let z=16;z>=5;z-=.2){let a=project(west,north,z),b=project(east,south,z);if(b[0]-a[0]<S.w*.82&&b[1]-a[1]<S.h*.78){S.z=z;break;}}drawBase();drawOverlay();updateScale();scheduleGeo();scheduleScan();msg('Network fitted');}
async function fetchRemote(url){const ctrl=new AbortController(),t=setTimeout(()=>ctrl.abort(),32000);try{const r=await fetch(url,{signal:ctrl.signal});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();if(d.error)throw Error(d.error.message||'GIS error');return d}finally{clearTimeout(t)}}
async function fetchGeo(){const point=S.site,token=(S.geoToken||0)+1;S.geoToken=token;S.gisLoading=true;$('gisState').textContent='Loading peat…';const qs=async(layer)=>{const q=new URLSearchParams({layer,lon:point.lon,lat:point.lat});return fetchRemote(`/api/peat?${q}`)};const local=['http:','https:'].includes(location.protocol);if(!local){$('gisState').textContent='Local server required';S.gisLoading=false;return;}let vals=await Promise.allSettled([qs(37),qs(48)]);if(token!==S.geoToken)return;S.gis={khg:vals[0].status==='fulfilled'?vals[0].value:null,feg:vals[1].status==='fulfilled'?vals[1].value:null};let k=S.gis.khg?.features?.[0]?.attributes||{},f=S.gis.feg?.features?.[0]?.attributes||{};let khg=k.kode_khg||k.KODE_KHG, fn=f.feg_50k||f.FEG_50K;S.gisLoading=false;$('gisState').textContent=`KHG: ${khg||'Unavailable'} · Ekosistem: ${fn||'Unavailable'}`;scheduleGeo();}
let geoTimer,peatPollTimer,foundationTimer;
function scheduleGeo(){drawOverlay()}
function queueFoundation(force=false){
 if(!S.site)return;
 clearTimeout(foundationTimer);
 const token=S.foundationToken;
 foundationTimer=setTimeout(()=>{if(token===S.foundationToken)loadFoundation(force,token)},180);
}
function loadPeatRaster(type,layer,b,token){
 if(S.peatRasters[type])return;
 const img=new Image(),url='/api/peat-raster?'+new URLSearchParams({layer,w:b.w,s:b.s,e:b.e,n:b.n,site:S.siteKey});
 S.peatRasters[type]={img,bounds:b};
 img.onload=()=>{if(token===S.foundationToken)drawOverlay()};
 img.onerror=()=>{if(token===S.foundationToken)delete S.peatRasters[type]};
 if(STATIC_PAGES){
  const siteKey=S.siteKey;
  window.BARA_STATIC_API.rasterPath(siteKey,layer).then(path=>{
   if(token!==S.foundationToken||siteKey!==S.siteKey)return;
   if(path)img.src=path;else delete S.peatRasters[type];
  }).catch(()=>{if(token===S.foundationToken)delete S.peatRasters[type]});
 }else img.src=url;
}
function strictPeatFeature(f,layer){
 if(!f?.geometry)return false;
 const p=f.properties||{},tag=v=>/gambut|peat/i.test(String(v||''))&&!/non[ -]?gambut|bukan gambut|tidak gambut|no peat|nonpeat|mineral/i.test(String(v||''));
 if(layer===6)return tag(p.landform??p.LANDFORM);
 const soil=p.tnh_gambut??p.TNH_GAMBUT;
 if(soil!=null&&String(soil).trim())return tag(soil);
 return tag(p.feg_peat??p.FEG_PEAT);
}
function applyPeatSources(){
 const layers=S.peatLayerDocs||{},soil=(layers[6]?.features||[]).filter(f=>strictPeatFeature(f,6));
 const eco=(layers[48]?.features||[]).filter(f=>strictPeatFeature(f,48));
 const khg=layers[37]?.features||[],feg=layers[48]?.features||[];
 let poly=soil.length?soil:eco;
 if(S.browserImports?.['6']?.features?.length)poly=S.browserImports['6'].features;
 // Preserve the previously saved valid mask until its source is replaced by real geometry.
 if(poly.length){
  const kind=soil.length?'soil':'feg';
  S.peatRaw={type:'FeatureCollection',features:poly,source:soil.length?'BIG peat soil':layers[48]?.source||'Mapped peat'};
 }
 S.gisShapes=[...khg.filter(f=>f.geometry).map(f=>({type:'khg',geometry:f.geometry})),
  ...feg.filter(f=>f.geometry).map(f=>({type:'feg',geometry:f.geometry})),
  ...soil.map(f=>({type:'soil',geometry:f.geometry}))];
 // Draw the measured peat mask separately even when ecosystem polygons are missing.
 if(!soil.length&&S.peatRaw?.features?.length){
  S.gisShapes.push(...S.peatRaw.features.map(f=>({type:'soil',geometry:f.geometry})));
 }
 if(S.browserImports)applyBrowserImports();
 $('gisState').textContent=`Peat ${S.peatRaw?.features?.length||0} · Ecosystem ${feg.length} · System ${khg.length}`;
 drawOverlay();
}
async function loadSavedPeatMask(token){
 const site=S.site;
 try{
  const params=new URLSearchParams({site:S.siteKey,lon:site.lon,lat:site.lat});
  const r=await fetch('/api/peat-mask?'+params);
  if(!r.ok)return;
  const d=await r.json();if(token!==S.foundationToken)return;
  if(!d.features?.length)return;
  const features=d.features.filter(f=>strictPeatFeature(f,6)||strictPeatFeature(f,48));
  if(!features.length)return;
  S.peatRaw={type:'FeatureCollection',features,source:d.source||'Saved peat mask'};
  S.gisShapes.push(...features.map(f=>({type:'soil',geometry:f.geometry})));
  $('gisState').textContent=`Peat ${features.length} · Saved`;
  drawOverlay();queueFoundation(true);
 }catch(e){}
}
async function requestPeatLayer(layer,b,token,attempt=0){
 if(token!==S.foundationToken)return;
 try{
  const q=new URLSearchParams({layer,w:b.w,s:b.s,e:b.e,n:b.n,site:S.siteKey});
  const d=await fetchRemote('/api/peat-shapes?'+q);
  if(token!==S.foundationToken)return;
  if(Array.isArray(d.features)){
   const previous=S.peatLayerDocs[layer];
   if(d.features.length || !previous){
    S.peatLayerDocs[layer]=d;
    if(d.features.length){
      applyPeatSources();
      if(layer===6||layer===48)queueFoundation(true);
    }
   }
  }
  if(d.refreshing&&attempt<20){
   const delay=Math.min(5500,1200+attempt*500);
   setTimeout(()=>{if(token===S.foundationToken)requestPeatLayer(layer,b,token,attempt+1)},delay);
  }
 }catch(e){/* Keep cached polygons or raster overlay visible. */}
}
async function fetchGeoShapes(){
 if(!['http:','https:'].includes(location.protocol))return false;
 const site=S.site,token=S.foundationToken;
 const dy=7.5/111.195,dx=7.5/(111.195*Math.max(.2,Math.cos(site.lat*RAD)));
 const b={w:site.lon-dx,e:site.lon+dx,s:site.lat-dy,n:site.lat+dy};
 S.peatLayerDocs={};
 // The cached soil mask and raster overlays start before the BIG polygon requests.
 const saved=loadSavedPeatMask(token);
 for(const [type,layer] of [['khg',37],['feg',48]])loadPeatRaster(type,layer,b,token);
 await Promise.allSettled([saved,...[6,48,37].map(layer=>requestPeatLayer(layer,b,token))]);
 return !!S.peatRaw?.features?.length;
}
function updateSiteMetrics(m){if(!m)return;
 const set=(k,v)=>{const e=$(k);if(e)e.textContent=v??'—'};
 set('siteArea',m.site_area_km2!=null?`${Number(m.site_area_km2).toFixed(1)} km² · ${(m.site_area_ha||0).toLocaleString('en-US')} ha`:'—');
 set('siteSize',m.site_width_km!=null?`${Number(m.site_width_km).toFixed(1)} × ${Number(m.site_height_km).toFixed(1)} km`:'—');
 set('studyArea',S.site?.study_area_km2!=null?`${Number(S.site.study_area_km2).toFixed(1)} km²`:'—');
 set('sitePerimeter',m.site_perimeter_km!=null?`${Number(m.site_perimeter_km).toFixed(1)} km`:'—');
 set('peatArea',m.peat_ha!=null?`${Number(m.peat_ha).toLocaleString('en-US')} ha`:'—');
 set('canalKm',m.osm_available&&m.canal_km!=null?`${Number(m.canal_km).toFixed(1)} km`:'—');
 set('riverKm',m.osm_available&&m.river_km!=null?`${Number(m.river_km).toFixed(1)} km`:'—');
}
async function loadEnvironment(site,token,attempt=0){
 if(!S.site||token!==S.envToken)return;
 try{
  // Server retrieves ERA5-Land automatically, then saves the successful site result.
  const params=new URLSearchParams({site:S.siteKey});
  const response=await fetch('/api/environment?'+params);
  const doc=await response.json();
  if(!response.ok)throw Error(doc.message||'Weather unavailable');
  if(token!==S.envToken)return;
  S.env=doc;
  const sm=doc.smap,era=doc.era5;
  const wet=sm?.surface_wetness_fraction;
  $('smapValue').textContent=wet==null?'—':`${(wet*100).toFixed(0)}% wet · 2024-01-01`;
  if(era?.temp_c!=null){
   $('era5Value').textContent=`${Number(era.temp_c).toFixed(1)}°C · RH ${era.rh_pct??'—'}% · 2024`;
   if(!S.manualWind&&era.wind_kmh!=null){S.wind=clip(Math.round(era.wind_kmh),0,40);$('windInput').value=S.wind;$('windValue').textContent=S.wind+' km/h';}
   if(!S.manualDirection&&era.wind_toward_deg!=null){S.direction=(Math.round(era.wind_toward_deg/45)*45)%360;$('dirInput').value=S.direction;$('dirValue').textContent=['North ↑','NE ↗','East →','SE ↘','South ↓','SW ↙','West ←','NW ↖'][S.direction/45];}
   simulate(false);
  }else if(doc.era5_status==='fetching'&&attempt<45){
   $('era5Value').textContent='Fetching ERA5-Land…';
   clearTimeout(S.envPollTimer);
   S.envPollTimer=setTimeout(()=>loadEnvironment(site,token,attempt+1),1300);
  }else{
   $('era5Value').textContent='Scenario weather';
  }
 }catch(error){
  if(token===S.envToken){$('smapValue').textContent='—';$('era5Value').textContent='Scenario weather';}
 }
}
async function initializeSite(site,token,editTask){
 $('foundationStatus').textContent='Mapping';
 restoreBrowserImports();
 // Any source can improve the result; no external data source blocks another.
 queueFoundation(false);
 scanWaterways();
 fetchGeoShapes();
 Promise.resolve(editTask).then(()=>{if(token===S.foundationToken)queueFoundation(true)});
}
function browserImportKey(){return `bara25-layers-${S.siteKey}`;}
function saveBrowserImports(){
 try{localStorage.setItem(browserImportKey(),JSON.stringify(S.browserImports));return true;}
 catch(e){return false;}
}
function restoreBrowserImports(){
 try{const value=JSON.parse(localStorage.getItem(browserImportKey())||'{}');
  if(value && typeof value==='object' && !Array.isArray(value))S.browserImports=value;
 }catch(e){}
 applyBrowserImports();
}
function validateBrowserGeoJSON(doc,layer){
 const features=doc?.features;
 if(doc?.type!=='FeatureCollection'||!Array.isArray(features)||features.length>1200)
  throw Error('Use a GeoJSON FeatureCollection (max 1,200 features)');
 const validCoord=coord=>Array.isArray(coord)&&coord.length>=2&&Number.isFinite(+coord[0])&&Number.isFinite(+coord[1])&&+coord[0]>=94&&+coord[0]<=144&&+coord[1]>=-12&&+coord[1]<=7;
 function walk(coords,depth=0){
  if(depth>5||!Array.isArray(coords)||coords.length>100000)return false;
  if(typeof coords[0]==='number')return validCoord(coords);
  return coords.every(c=>walk(c,depth+1));
 }
 for(const f of features){
  const g=f?.geometry||{},kind=g.type;
  if(['6','37','48'].includes(layer)?!['Polygon','MultiPolygon'].includes(kind):layer==='structures'?kind!=='Point':!['LineString','MultiLineString'].includes(kind))throw Error('Wrong geometry type');
  if(!walk(g.coordinates))throw Error('Coordinates must be in Indonesia');
 }
 return features;
}
function applyBrowserImports(){
 const imports=S.browserImports||{};
 if(!Object.keys(imports).length)return;
 for(const [layer,type] of [['6','soil'],['48','feg'],['37','khg']]){
  const doc=imports[layer];if(!doc?.features?.length)continue;
  S.gisShapes=S.gisShapes.filter(f=>f.type!==type);
  S.gisShapes.push(...doc.features.map(f=>({type,geometry:f.geometry})));
  if(layer==='6')S.peatRaw={type:'FeatureCollection',features:doc.features,source:'Browser GeoJSON'};
 }
 const elements=(S.osmRaw?.elements||[]).filter(e=>!(e.tags||{}).bara_browser_import);
 let id=970000000;
 for(const [layer,kind] of [['canal','canal'],['river','river'],['structures','structure']]){
  const doc=imports[layer];if(!doc?.features?.length)continue;
  for(const f of doc.features){
   const g=f.geometry,name=String(f.properties?.name||'').slice(0,100);
   const tags={bara_browser_import:'yes',name,waterway:kind==='structure'?'sluice_gate':kind};
   if(kind==='structure'){elements.push({type:'node',id:id++,lon:g.coordinates[0],lat:g.coordinates[1],tags});continue;}
   const lines=g.type==='LineString'?[g.coordinates]:g.coordinates;
   for(const line of lines){if(line.length<2)continue;elements.push({type:'way',id:id++,geometry:line.map(x=>({lon:x[0],lat:x[1]})),tags});}
  }
 }
 if(elements.length){
  S.osmRaw={elements,provider:'OSM / browser import'};
  const parsed=parseOSM(S.osmRaw);
  S.canals=parsed.canals;S.rivers=parsed.rivers;S.structures=parsed.structures;
  $('canalNum').textContent=S.canals.length.toLocaleString('en-US');
  $('riverNum').textContent=S.rivers.length.toLocaleString('en-US');
  $('structureNum').textContent=S.structures.length.toLocaleString('en-US');
 }
 drawOverlay();
}
function foundationOSM(){
 const elements=[...(S.osmRaw?.elements||[])];
 S.customCanals.forEach((line,i)=>elements.push({type:'way',id:9000000+i,tags:{waterway:'canal',name:line.name||'Custom canal'},geometry:line.points.map(p=>({lon:p[0],lat:p[1]}))}));
 return elements.length?{elements,provider:S.osmRaw?.provider||'Drawn canals'}:null;
}
async function loadFoundation(force=false, token=S.foundationToken){
 if(!S.site)return;
 const local=['http:','https:'].includes(location.protocol);
 if(!local){$('foundationStatus').textContent='Open with local server';return;}
 const requestId=S.foundationRequestId=(S.foundationRequestId||0)+1;
 const siteKey=S.siteKey;
 $('foundationStatus').textContent=S.foundation?'Updating':'Calculating';
 try{
  const r=await fetch('/api/foundation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site:siteKey,lon:S.site.lon,lat:S.site.lat,force,osm:foundationOSM(),peat:S.peatRaw})});
  const d=await r.json();if(!r.ok)throw Error(d.message||'Calculation unavailable');
  if(token!==S.foundationToken||siteKey!==S.siteKey||requestId!==S.foundationRequestId)return;
  S.foundation=d;S.foundationReady=d.status==='ready';updateSiteMetrics(d.metrics);
  if(STATIC_PAGES){
   if(S.siteReportBlob)URL.revokeObjectURL(S.siteReportBlob);
   S.siteReportBlob=URL.createObjectURL(new Blob([JSON.stringify({site:S.site,foundation:d,environment:S.env},null,2)],{type:'application/json'}));
   $('exportSite').href=S.siteReportBlob;$('exportSite').download=siteKey+'-report.json';
  }
  S.blockPlaces=d.candidates?.length?d.candidates:(d.selected||[]);
  S.rankedBlockPlaces=[];S.fireRankStatus=null;setBlocks();renderBlocks();drawOverlay();simulate(false);
  $('foundationStatus').textContent=d.status==='ready'?'Mapped':d.status==='canals_only'?'Canals mapped':d.status==='needs_canals'?'Waiting for canals':'Waiting for peat';
  $('scanExplain').textContent=d.metrics?.osm_available?`${d.metrics.canal_count} canals · ${d.metrics.river_count} rivers`:'Loading waterways';
 }catch(e){if(token===S.foundationToken&&requestId===S.foundationRequestId)$('foundationStatus').textContent=S.foundation?'Mapped':'Calculation unavailable';}
}
// Deterministic fire scenario:
// Deterministic fire scenario: sparse spread with a viewport-adaptive grid.
function updateDrawCount(){
 $('drawCount').textContent=`${S.drawPoints.length} points`;
 $('finishCanal').disabled=S.drawPoints.length<2;
}
function addCanal(){
 if(S.drawPoints.length<2){msg('Draw at least 2 points');return}
 S.customCanals.push({id:'BUAT-'+Date.now(),kind:'custom',points:S.drawPoints.slice(),name:'Drawn canal',tags:{waterway:'canal'}});
 S.drawPoints=[];updateDrawCount();loadFoundation(true);saveEdits();drawOverlay();msg('Canal saved');
}
function localEditsKey(){return 'bara22-edits-'+S.siteKey}
async function loadEdits(){
 const site=S.siteKey,seq=S.editSeq;let doc=null;
 try{if(location.protocol==='http:'){
  const r=await fetch('/api/edits?'+new URLSearchParams({site}));if(r.ok)doc=await r.json();
 }}catch(e){}
 if(!doc||(!doc.canals?.length&&!doc.blocks?.length)){
   try{doc=JSON.parse(localStorage.getItem(localEditsKey())||'null')}catch(e){}
 }
 if(S.siteKey!==site||S.editSeq!==seq)return;
 S.customCanals=(doc?.canals||[]).filter(c=>Array.isArray(c.points)&&c.points.length>=2).map(c=>({...c,kind:'custom',tags:{waterway:'canal'}}));
 S.manual=(doc?.blocks||[]).filter(p=>Number.isFinite(+p.lon)&&Number.isFinite(+p.lat));
 S.blocks=clip(Math.max(S.blocks,S.manual.length),0,12);
 $('blocksInput').value=S.blocks;$('blocksValue').textContent=S.blocks;
 setBlocks();renderBlocks();drawOverlay();simulate(true);
}
async function saveEdits(){
 if(!S.site)return;
 try{
  const site=S.siteKey;S.editSeq=(S.editSeq||0)+1;
  const doc={canals:S.customCanals.map(c=>({id:c.id,name:c.name,points:c.points})),
             blocks:S.manual.map(b=>({lon:b.lon,lat:b.lat,kind:b.kind,name:b.name}))};
  const contents=JSON.stringify(doc);
  try{localStorage.setItem('bara22-edits-'+site,contents)}catch(e){}
  try{
   const r=await fetch('/api/edits?'+new URLSearchParams({site}),{method:'POST',headers:{'Content-Type':'application/json'},body:contents});
   /* Browser storage retains edits when server writes are disabled. */
  }catch(e){/* Local browser copy is kept. */}
 }catch(e){console.warn('Failed to save edits:',e)}
}
function noise(a,b,c){let n=Math.imul(a+1,374761393)^Math.imul(b+11,668265263)^Math.imul(c+53,2246822519);n=Math.imul(n^(n>>>13),1274126177);return ((n^(n>>>16))>>>0)/4294967296;}
function modelGrid(){const nx=80,ny=80,step=187.5;return {lon:S.site.lon,lat:S.site.lat,nx,ny,step};}
// Cache the peat rasterized fuel mask once per site/source instead of
// running point-in-polygon for every hour and block scenario.
function getPeatFuelMask(g){
 const src=S.peatRaw;
 if(!src?.features?.length)return null;
 const old=S.peatGridCache;
 if(old?.source===src&&old.lon===g.lon&&old.lat===g.lat)return old.mask;
 const mask=new Uint8Array(g.nx*g.ny);
 const lonStep=g.step/(111195*Math.cos(g.lat*RAD)),latStep=g.step/111195;
 for(const f of src.features){
  const geom=f.geometry;if(!geom)continue;
  const polys=geom.type==='Polygon'?[geom.coordinates]:geom.type==='MultiPolygon'?geom.coordinates:[];
  for(const poly of polys){
   const ring=poly[0];if(!ring?.length)continue;
   let west=Infinity,east=-Infinity,south=Infinity,north=-Infinity;
   for(const pt of ring){west=Math.min(west,pt[0]);east=Math.max(east,pt[0]);south=Math.min(south,pt[1]);north=Math.max(north,pt[1]);}
   const x0=clip(Math.floor((west-g.lon)/lonStep+g.nx/2)-1,0,g.nx-1);
   const x1=clip(Math.ceil((east-g.lon)/lonStep+g.nx/2)+1,0,g.nx-1);
   const y0=clip(Math.floor((south-g.lat)/latStep+g.ny/2)-1,0,g.ny-1);
   const y1=clip(Math.ceil((north-g.lat)/latStep+g.ny/2)+1,0,g.ny-1);
   for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){
    const id=y*g.nx+x;if(mask[id])continue;
    if(polyInside([g.lon+(x-g.nx/2)*lonStep,g.lat+(y-g.ny/2)*latStep],{type:'Polygon',coordinates:poly}))mask[id]=1;
   }
  }
 }
 S.peatGridCache={source:src,lon:g.lon,lat:g.lat,mask};
 return mask;
}
function fireRun(blocks){const g=modelGrid(),{nx,ny,step}=g,n=nx*ny,weatherFactor={wet:.54,normal:.85,dry:1.19,extreme:1.48}[S.weather],fuel=new Uint8Array(n),mask=new Uint8Array(n),age=new Uint8Array(n),cells=new Uint8Array(n),lonStep=step/(111195*Math.cos(g.lat*RAD)),latStep=step/111195,geoPolygon=(S.peatRaw?.features||[]).map(x=>x.geometry),peatFuel=getPeatFuelMask(g);let avail=0;for(let y=0;y<ny;y++)for(let x=0;x<nx;x++){const id=y*nx+x,peatHere=!!peatFuel?.[id];mask[id]=1;fuel[id]=Math.round((80+noise(x,y,0)*70)*(peatHere?1.12:.90));avail+=mask[id]};let firePoint=S.ignition||{lon:S.site.lon,lat:S.site.lat},ix=clip(Math.round((firePoint.lon-g.lon)/lonStep+nx/2),0,nx-1),iy=clip(Math.round((firePoint.lat-g.lat)/latStep+ny/2),0,ny-1);if(!avail)return {frames:[],area:0,stop:null,geo:g,nx,ny,step,masked:true};const start=iy*nx+ix;cells[start]=1;let active=[start],frames=[],stop=null,maxHours=S.horizon;const wetnessByBlock=new Float32Array(n);for(const block of blocks){let bx=(block.lon-g.lon)/lonStep+nx/2,by=(block.lat-g.lat)/latStep+ny/2,reach=500/step,range=Math.ceil(2.6*reach);for(let y=Math.max(0,Math.floor(by-range));y<Math.min(ny,by+range+1);y++)for(let x=Math.max(0,Math.floor(bx-range));x<Math.min(nx,bx+range+1);x++){const d2=((x-bx)**2+(y-by)**2)/(2*reach*reach);wetnessByBlock[y*nx+x]+=Math.exp(-d2)*.31}}
 // Canal membuka drainase lokal; sungai menambah kelembapan di tepi alurnya.
 // Kedua lapisan memengaruhi api, bukan hanya digambar di peta.
 const hydro=new Float32Array(n);
 const paintWater=(lines,weight,reachM,limit)=>{
  const reach=Math.max(.6,reachM/step),size=Math.ceil(2.4*reach);
  for(const line of lines.slice(0,limit)){
   const pts=line.points||[];
   for(let seg=1;seg<pts.length;seg++){
    const a=pts[seg-1],b=pts[seg],len=D(...a,...b);
    const samples=clip(Math.ceil(len/Math.max(100,step*1.5)),1,70);
    for(let k=0;k<=samples;k++){
     const t=k/samples,lon=a[0]+t*(b[0]-a[0]),lat=a[1]+t*(b[1]-a[1]);
     const bx=(lon-g.lon)/lonStep+nx/2,by=(lat-g.lat)/latStep+ny/2;
     if(bx< -size||bx>nx+size||by< -size||by>ny+size)continue;
     for(let y=Math.max(0,Math.floor(by-size));y<Math.min(ny,by+size+1);y++)
      for(let x=Math.max(0,Math.floor(bx-size));x<Math.min(nx,bx+size+1);x++){
       const dist=((x-bx)**2+(y-by)**2)/(2*reach*reach);
       const delta=Math.exp(-dist)*Math.abs(weight),idx=y*nx+x;
       if(weight>0)hydro[idx]=Math.max(hydro[idx],delta);
       else hydro[idx]=Math.min(hydro[idx],-delta);
      }
    }
   }
  }
 };
 paintWater([...S.canals,...S.customCanals],.18,230,300);
 paintWater(S.rivers,-.25,320,150);
 const theta=(90-S.direction)*RAD,wx=Math.cos(theta),wy=Math.sin(theta);const smapWet=(S.env?.smap?.surface_wetness_fraction),humidity=S.env?.era5?.rh_pct;const moistureFactor=smapWet!=null?clip(1.2-.55*smapWet,.56,1.2):1;const rhFactor=humidity!=null?clip(1.3-.65*humidity/100,.65,1.3):1;const met=S.env?.era5||null;const metFactor=met?clip(1+((met.temp_c??26)-26)*.012-(met.precipitation_1h_mm??0)*.035-((met.soil_water_l1_m3m3??.3)-.3)*.35,.55,1.40):1;for(let hour=0;hour<=maxHours;hour++){frames.push({cells:cells.slice(),active:active.length,burned:cells.reduce((s,c)=>s+(c>0),0)});if(!active.length){stop=hour;break;}if(hour===maxHours)break;let next=active.slice(),toIgnite=[];for(const id of active){let x=id%nx,y=Math.floor(id/nx),burnAge=++age[id],wblock=wetnessByBlock[id];for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]){let xx=x+dx,yy=y+dy;if(xx<0||yy<0||xx>=nx||yy>=ny)continue;let k=yy*nx+xx;if(!mask[k]||cells[k])continue;let dir=(dx*wx+dy*wy)/(Math.hypot(dx,dy)),wind=clip(1+S.wind/40*1.5*dir,.16,2.5),wet=clip((S.water/110*.80)+weatherFactor*.24+hydro[k]-wetnessByBlock[k],.04,1.5);let chance=clip((dx*dy?.17:.23)*wind*wet*(fuel[k]/120)*moistureFactor*rhFactor*metFactor,.008,.78);if(noise(hour,id,k)<chance){cells[k]=1;toIgnite.push(k)}}if(burnAge>=(S.weather==='wet'?3:S.weather==='extreme'?7:5)){cells[id]=2}}next=next.filter(k=>cells[k]===1);next.push(...toIgnite);if(S.teams&&hour+1>=S.arrival&&next.length){let nRemove=Math.min(next.length,S.teams*(S.weather==='extreme'?1:2));next.sort((a,b)=>{const da=(a%nx-ix)**2+(Math.floor(a/nx)-iy)**2,db=(b%nx-ix)**2+(Math.floor(b/nx)-iy)**2;return da-db});for(let i=0;i<nRemove;i++)cells[next[i]]=3;next=next.slice(nRemove)}active=next}let last=frames.at(-1);return {frames,area:(last?.burned||0)*step*step/10000,stop,geo:g,nx,ny,step,masked:!!geoPolygon.length};}
// Fire-aware block placement: rank candidates on mapped artificial canals by
// spatial overlap with the baseline (no-block) simulated fire footprint.
// Recalculated whenever ignition, wind, moisture or selected site changes.
function rankBlockCandidates(baseline){
 const pool=S.blockPlaces.filter(p=>!S.manual.some(m=>D(p.lon,p.lat,m.lon,m.lat)<400));
 if(!pool.length){S.rankedBlockPlaces=[];S.fireRankStatus='no-canals';return;}
 const grid=baseline?.geo, cells=baseline?.frames?.at(-1)?.cells;
 if(!grid||!cells||baseline.ignitionOutside){S.rankedBlockPlaces=[];S.fireRankStatus='no-fire';return;}
 const burned=[];
 const lonStep=grid.step/(111195*Math.cos(grid.lat*RAD)),latStep=grid.step/111195;
 // Sampling the final footprint is enough to place numbered blocks near the fire.
 for(let y=0;y<baseline.ny;y++)for(let x=0;x<baseline.nx;x++){
  const k=y*baseline.nx+x;
  if(!cells[k])continue;
  burned.push([grid.lon+(x-baseline.nx/2)*lonStep,grid.lat+(y-baseline.ny/2)*latStep]);
 }
 if(!burned.length){S.rankedBlockPlaces=[];S.fireRankStatus='no-fire';return;}
 const searchRadius=800,reach=350;
 const scored=pool.map((candidate,index)=>{
  let score=0,nearest=Infinity;
  for(const pt of burned){
   const dist=D(candidate.lon,candidate.lat,pt[0],pt[1]);
   nearest=Math.min(nearest,dist);
   if(dist<searchRadius)score+=Math.exp(-.5*(dist/reach)**2);
  }
  const origin=S.ignition||{lon:grid.lon,lat:grid.lat};
  const originDist=D(candidate.lon,candidate.lat,origin.lon,origin.lat);
  const local= Math.exp(-.5*(originDist/800)**2);
  return {...candidate,sourceIndex:index,fire_distance_m:nearest,fireExposure:score,
    fireScore:(score*Math.sqrt(Math.max(.1,+candidate.coverage_ha||.1)))/(1+(originDist/1400)**2)+40*local};
 });
 // Greedy ranking with separation: distinct exposed canal sections first.
 const ordered=[],remaining=scored.slice();
 while(remaining.length){
  let bestIndex=0,bestScore=-Infinity;
  for(let i=0;i<remaining.length;i++){
   const p=remaining[i];
   const maxOverlap=ordered.reduce((m,q)=>Math.max(m,Math.exp(-.5*(D(p.lon,p.lat,q.lon,q.lat)/400)**2)),0);
   const diversity=1-.85*maxOverlap;
   const score=(p.fireScore>0?p.fireScore*diversity:0)
        +(p.fireScore>0?0:.00001/(1+p.fire_distance_m))
        +(+p.coverage_ha||0)*.0000001;
   if(score>bestScore){bestIndex=i;bestScore=score;}
  }
  const best=remaining.splice(bestIndex,1)[0];
  ordered.push(best);
  for(let i=remaining.length-1;i>=0;i--){if(D(best.lon,best.lat,remaining[i].lon,remaining[i].lat)<400)remaining.splice(i,1);}
 }
 S.rankedBlockPlaces=ordered.map((p,i)=>({...p,rank:i+1}));
 S.fireRankStatus='fire';
}
let simTimer;
function buildSimulation(reset=true){
 if(reset)pause();
 const baseline=fireRun([]);
 rankBlockCandidates(baseline);
 setBlocks();renderBlocks();
 S.baseFire=S.shownBlocks.length?baseline:null;
 S.fire=S.shownBlocks.length?fireRun(S.shownBlocks):baseline;
 S.hour=reset?0:Math.min(S.hour,Math.max(0,S.fire.frames.length-1));
 updateResults();drawOverlay();
}
function simulate(reset=true){
 if(!S.site)return;
 clearTimeout(simTimer);
 simTimer=setTimeout(()=>{simTimer=null;buildSimulation(reset);},110);
}
function updateResults(){const f=S.fire;if(!f)return;const end=f.frames.at(-1),a= end?.burned*f.step*f.step/10000||0;const b=S.baseFire?S.baseFire.area-a:0;$('burnMetric').textContent=a?`${a.toFixed(1)} ha`:'0 ha';$('endMetric').textContent=f.stop===null?`>${S.horizon}h`:`${f.stop}h`;$('benefitMetric').textContent=S.baseFire?(b>=0?'-':'+')+Math.abs(b).toFixed(1)+' ha':'No blocks';$('hourLabel').textContent=`Hour ${S.hour}`;$('timeSlider').max=Math.max(0,f.frames.length-1);$('timeSlider').value=S.hour;$('horizonText').textContent=`${S.horizon} h`;$('playStatus').textContent=S.env?.era5?'ERA5-Land fire scenario':'Fire scenario';}
function pause(){if(S.interval){clearInterval(S.interval);S.interval=null}S.playing=false;$('playBtn').textContent='▶ Play';}
function play(){if(S.playing){pause();return}if(simTimer){clearTimeout(simTimer);simTimer=null;}if(!S.fire?.frames?.length)buildSimulation(true);if(!S.fire?.frames?.length){msg('Choose a fire point');return}if(S.fire.frames.length===1){msg('Fire contained at ignition');S.hour=0;updateResults();drawOverlay();return}S.playing=true;$('playBtn').textContent='Ⅱ Pause';if(S.hour>=S.fire.frames.length-1)S.hour=0;S.interval=setInterval(()=>{S.hour++;if(S.hour>=S.fire.frames.length-1)pause();updateResults();drawOverlay()},Number($('speedSelect').value));}
function bind(){
 for(const button of document.querySelectorAll('[data-base]'))button.onclick=()=>{
   S.baseLayer=button.dataset.base;S.tiles.clear();document.querySelectorAll('[data-base]').forEach(b=>b.classList.toggle('selected',b===button));drawBase();
 };
 $('soilCheck').onchange=e=>{S.showSoil=e.target.checked;drawOverlay()};
 $('importBtn').onclick=()=>{ $('importFile').click() };
 $('importFile').onchange=async e=>{
   const file=e.target.files?.[0];if(!file)return;
   $('gisState').textContent='Importing…';
   try{
     if(file.size>5_000_000)throw Error('Maximum 5 MB GeoJSON');
     const data=JSON.parse(await file.text()),layer=$('importKind').value;
     const features=validateBrowserGeoJSON(data,layer);
     if(S.publicReadOnly){
       S.browserImports[layer]=data;
       applyBrowserImports();
       const saved=saveBrowserImports();
       await loadFoundation(true);
       msg(`${features.length} features · ${saved?'Saved':'This session'}`);
     }else{
       const url='/api/import-geojson?'+new URLSearchParams({site:S.siteKey,layer});
       const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/geo+json'},body:JSON.stringify(data)});
       const out=await r.json();if(!r.ok)throw Error(out.message||'Import failed');
       if(['6','37','48'].includes(layer)){await fetchGeoShapes();await loadFoundation(true)}
       else {await scanWaterways();await loadFoundation(true)}
       msg(`${out.count} features saved`);
     }
   }catch(error){$('gisState').textContent=error.message||'Import unavailable';msg('GeoJSON import failed')}
   finally{e.target.value=''}
 };
 $('finishCanal').onclick=addCanal;$('cancelCanal').onclick=()=>{S.drawPoints=[];updateDrawCount();drawOverlay();msg('Canal canceled')};for(const b of document.querySelectorAll('[data-mode]'))b.onclick=()=>setMode(b.dataset.mode);$('placeSelect').onchange=e=>{let site=sites.find(s=>s.id===e.target.value);if(site)siteSelect(site)};$('homeBtn').onclick=()=>{if(S.site){S.lat=S.site.lat;S.lon=S.site.lon;S.z=11.6;drawBase();drawOverlay();updateScale()}};$('zoomPlus').onclick=()=>zoom(.7);$('zoomMinus').onclick=()=>zoom(-.7);$('scanBtn').onclick=()=>{if(!S.scanController)scanWaterways(true)};$('fitNetwork').onclick=fitNetwork;$('recommendBtn').onclick=recommendBlocks;$('khgCheck').onchange=e=>{S.showKHG=e.target.checked;drawOverlay()};$('fegCheck').onchange=e=>{S.showFEG=e.target.checked;drawOverlay()};for(const b of document.querySelectorAll('[data-weather]'))b.onclick=()=>{S.weather=b.dataset.weather;document.querySelectorAll('[data-weather]').forEach(x=>x.classList.toggle('selected',x===b));simulate(true)};
 for(const [id,key,label,unit] of [['waterInput','water','waterValue',' cm'],['windInput','wind','windValue',' km/h'],['dirInput','direction','dirValue',''],['teamsInput','teams','teamsValue',''],['arrivalInput','arrival','arrivalValue',' h'],['blocksInput','blocks','blocksValue','']]){$(id).oninput=e=>{S[key]=+e.target.value;if(key==='wind')S.manualWind=true;if(key==='direction')S.manualDirection=true;$(label).textContent=id==='dirInput'?['North ↑','NE ↗','East →','SE ↘','South ↓','SW ↙','West ←','NW ↖'][S.direction/45]:S[key]+unit;if(key==='blocks')setBlocks();simulate(true)}}$('playBtn').onclick=play;$('resetBtn').onclick=()=>{pause();S.hour=0;updateResults();drawOverlay()};$('stepBtn').onclick=()=>{pause();S.hour=Math.min((S.fire?.frames?.length||1)-1,S.hour+1);updateResults();drawOverlay()};$('timeSlider').oninput=e=>{pause();S.hour=+e.target.value;updateResults();drawOverlay()};$('helpBtn').onclick=()=>$('helpModal').classList.add('open');$('helpClose').onclick=$('helpDone').onclick=()=>$('helpModal').classList.remove('open');$('helpModal').onclick=e=>{if(e.target===$('helpModal'))$('helpModal').classList.remove('open')};
 let stage=$('mapStage');stage.addEventListener('pointerdown',e=>{if(e.button!==0||e.target.closest('button,select,input,a'))return;S.drag={x:e.clientX,y:e.clientY,lastX:e.clientX,lastY:e.clientY,moved:false};stage.setPointerCapture(e.pointerId)});stage.addEventListener('pointermove',e=>{if(!S.drag)return;const dx=e.clientX-S.drag.lastX,dy=e.clientY-S.drag.lastY;if(Math.hypot(e.clientX-S.drag.x,e.clientY-S.drag.y)>6)S.drag.moved=true;if(S.drag.moved){stage.classList.add('dragging');pan(dx,dy)}S.drag.lastX=e.clientX;S.drag.lastY=e.clientY});stage.addEventListener('pointerup',e=>{const drag=S.drag;S.drag=null;stage.classList.remove('dragging');if(!drag)return;if(drag.moved){scheduleGeo();scheduleScan();return}const r=stage.getBoundingClientRect();handleMapClick(e.clientX-r.left,e.clientY-r.top)});stage.addEventListener('wheel',e=>{e.preventDefault();const r=stage.getBoundingClientRect();zoom(e.deltaY<0?.4:-.4,e.clientX-r.left,e.clientY-r.top)},{passive:false});stage.addEventListener('dblclick',e=>{e.preventDefault();const r=stage.getBoundingClientRect();zoom(.85,e.clientX-r.left,e.clientY-r.top)});document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('helpModal').classList.remove('open')}if(e.key===' '&&e.target===document.body){e.preventDefault();play()}});new ResizeObserver(resize).observe(stage);}
function start(){selectLocationOptions();bind();resize();setInterval(()=>{if(S.site&&!S.scanController)scanWaterways(false)},10*60*1000);siteSelect(sites.find(x=>x.id===(STATIC_PAGES?'KAL-01':'PAP-01')));setMode('ignite');fetch('/api/version').then(r=>r.json()).then(info=>{S.publicReadOnly=Boolean(info.public_read_only);}).catch(()=>{});}
start();
})();
