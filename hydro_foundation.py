"""Real-metre site footprint, OSM hydrology, and overlap-aware canal-block screening.

Only mapped artificial canals are candidates. Mapped peat is required for optimization.
This is a spatial coverage heuristic, not a terrain/head or groundwater flow solver.
"""
from __future__ import annotations
import math
from shapely.geometry import shape, Point, LineString, box, mapping
from shapely.ops import transform, unary_union
from shapely.prepared import prep
from pyproj import Transformer, Geod

GEOD=Geod(ellps='WGS84')
ARTIFICIAL={'canal','drain','ditch'}
NATURAL={'river','stream','tidal_channel'}

def site_frame(lon, lat, radius_m=7500):
    lon=float(lon);lat=float(lat);r=float(radius_m)
    if not (94<=lon<=144 and -12<=lat<=7 and 500<=r<=12000):
        raise ValueError('Site coordinates or radius outside supported range')
    zone=max(1,min(60,int((lon+180)//6)+1))
    epsg=(32600 if lat>=0 else 32700)+zone
    fwd=Transformer.from_crs(4326,epsg,always_xy=True).transform
    rev=Transformer.from_crs(epsg,4326,always_xy=True).transform
    x,y=fwd(lon,lat);footprint=box(x-r,y-r,x+r,y+r)
    pts=[rev(a,b) for a,b in list(footprint.exterior.coords)]
    perimeter=GEOD.line_length(*zip(*pts))
    return {'fwd':fwd,'rev':rev,'footprint':footprint,'bbox':list(zip(*pts)),
            'site_width_km':2*r/1000,'site_height_km':2*r/1000,
            'site_area_km2':footprint.area/1e6,'site_area_ha':footprint.area/1e4,
            'site_perimeter_km':perimeter/1000,'epsg':epsg,'radius_m':r}

def peat_geometry(features, fwd, footprint):
    polys=[]
    for row in (features or {}).get('features',[]):
        geom=row.get('geometry')
        if not geom:continue
        try:
            shp=shape(geom)
            if shp.geom_type not in ('Polygon','MultiPolygon'):continue
            p=transform(fwd,shp)
            if not p.is_valid:p=p.buffer(0)
            if p.intersects(footprint):polys.append(p.intersection(footprint))
        except Exception:continue
    return unary_union(polys) if polys else None

def osm_features(document, fwd, footprint):
    canals=[];rivers=[];structures=[];seen=set()
    for e in (document or {}).get('elements',[]):
        key=(e.get('type'),e.get('id'))
        if key in seen:continue
        seen.add(key);tags=e.get('tags') or {}
        kind=tags.get('waterway') or tags.get('water') or ''
        if e.get('type')=='way':
            raw=[(p['lon'],p['lat']) for p in e.get('geometry',[]) if 'lon' in p and 'lat' in p]
            if len(raw)>=2 and kind in (ARTIFICIAL|NATURAL):
                try:
                    ln=transform(fwd,LineString(raw)).intersection(footprint)
                    if not ln.is_empty:
                        for part in (ln.geoms if ln.geom_type=='MultiLineString' else [ln]):
                            if part.length<1:continue
                            item={'id':str(key),'geom':part,'name':tags.get('name',''), 'type':kind}
                            (canals if kind in ARTIFICIAL else rivers).append(item)
                except Exception:pass
        structure=bool(tags.get('structure') or tags.get('sekat_kanal') or tags.get('canal_block') or tags.get('waterway') in ('dam','weir','sluice_gate','lock_gate','floodgate') or tags.get('man_made') in ('dam','weir','pumping_station') or tags.get('barrier') in ('dam','sluice_gate') or tags.get('tunnel')=='culvert')
        if structure:
            p=e if 'lat' in e and 'lon' in e else (e.get('center') or (e.get('geometry') or [{}])[len(e.get('geometry') or [{}])//2])
            if 'lat' in p and 'lon' in p:
                try:
                    point=transform(fwd,Point(p['lon'],p['lat']))
                    if footprint.intersects(point):structures.append(point)
                except Exception:pass
    return canals,rivers,structures

def inventory(lon,lat,osm=None,peat=None,radius_m=7500):
    frame=site_frame(lon,lat,radius_m)
    water=osm_features(osm,frame['fwd'],frame['footprint'])
    peatpoly=peat_geometry(peat,frame['fwd'],frame['footprint'])
    c,r,structures=water
    result={k:round(frame[k],3) for k in ('site_width_km','site_height_km','site_area_km2','site_area_ha','site_perimeter_km')}
    result.update({'site_type':'analysis_footprint','canal_km':round(sum(x['geom'].length for x in c)/1000,3),
                   'river_km':round(sum(x['geom'].length for x in r)/1000,3),
                   'canal_count':len(c),'river_count':len(r),'structure_count':len(structures),
                   'peat_ha':round(peatpoly.area/1e4,2) if peatpoly is not None else None,
                   'peat_km2':round(peatpoly.area/1e6,3) if peatpoly is not None else None,
                   'peat_available':peatpoly is not None,'osm_available':osm is not None,
                   'epsg':frame['epsg']})
    return result

def optimize(lon,lat,osm,peat,limit=12,radius_m=7500):
    frame=site_frame(lon,lat,radius_m);foot=frame['footprint']
    canals,rivers,structures=osm_features(osm,frame['fwd'],foot)
    poly=peat_geometry(peat,frame['fwd'],foot)
    stats={k:round(frame[k],3) for k in ('site_width_km','site_height_km','site_area_km2','site_area_ha','site_perimeter_km')}
    stats.update({'site_type':'analysis_footprint',
        'canal_km':round(sum(x['geom'].length for x in canals)/1000,3),
        'river_km':round(sum(x['geom'].length for x in rivers)/1000,3),
        'canal_count':len(canals),'river_count':len(rivers),'structure_count':len(structures),
        'peat_ha':round(poly.area/1e4,2) if poly is not None else None,
        'peat_km2':round(poly.area/1e6,3) if poly is not None else None,
        'peat_available':poly is not None,'osm_available':osm is not None,
        'epsg':frame['epsg']})
    if not canals:
        return {'status':'needs_canals','metrics':stats,'candidates':[],
                'selected':[],'method':'canal-network-screening'}
    # Show real mapped-canal candidates immediately, even while BIG peat polygons load.
    # Peat coverage stays null until a real polygon is available; no fabricated area.
    existing=unary_union(structures) if structures else None
    if poly is None or poly.is_empty:
        proposals=[]
        for item in canals:
            line=item['geom']
            if line.length<70:continue
            for d in range(150,int(line.length),450):
                point=line.interpolate(min(line.length-20,max(20,d)))
                if existing is not None and existing.distance(point)<100:continue
                x,y=frame['rev'](point.x,point.y)
                proposals.append({'lon':round(x,7),'lat':round(y,7),
                    'line_id':item['id'],'type':item['type'],'name':item['name'] or item['type'].capitalize(),
                    'coverage_ha':None,'rank':None})
                if len(proposals)>=120:break
            if len(proposals)>=120:break
        return {'status':'canals_only','metrics':stats,'candidates':proposals,
                'selected':proposals[:max(0,min(12,int(limit)))],
                'method':'mapped-canal-spacing','spacing_m':450}
    # A simplified *screening* geometry speeds up spatial ranking; measured
    # peat area in stats remains derived from the full source polygon.
    screen_poly=poly.simplify(12,preserve_topology=True)
    from shapely.prepared import prep
    prepared=prep(screen_poly)
    # Spacing 200-250 m is a screening interval; engineering spacing requires slope/head data.
    candidates=[];existing=unary_union(structures) if structures else None
    for item in canals:
        line=item['geom']
        if line.length<65:continue
        step=250
        for d in range(0,int(line.length),step):
            if len(candidates)>=260:break
            point=line.interpolate(min(line.length-15,max(15,d+step/2)))
            if existing is not None and existing.distance(point)<100:continue
            footprint=point.buffer(350,quad_segs=6)
            if not prepared.intersects(footprint):continue
            impact=screen_poly.intersection(footprint)
            if impact.is_empty or impact.area<5000:continue
            candidates.append({'point':point,'impact':impact,'line_id':item['id'],'name':item['name'],
                               'type':item['type'],'size':impact.area})
        if len(candidates)>=260:break
    # Pre-screen by total buffered peat coverage, then greedy marginal area (avoids overlapping candidates).
    candidates=sorted(candidates,key=lambda a:-a['size'])[:120]
    chosen=[];covered=None
    for _ in range(min(24,max(0,int(limit)))):
        best=None;gain=0
        for cand in candidates:
            if cand.get('chosen'):continue
            if any(cand['point'].distance(old['point'])<220 for old in chosen):continue
            diff=cand['impact'] if covered is None else cand['impact'].difference(covered)
            area=diff.area
            # Slight preference for explicitly tagged canals over small drainage ditches.
            rank=area*(1.05 if cand['type']=='canal' else 1.0)
            if rank>gain:gain=rank;best=(cand,area)
        if best is None or best[1]<1500:break
        cand,area=best;cand['chosen']=True
        covered=cand['impact'] if covered is None else covered.union(cand['impact'])
        chosen.append(cand)
    def serialize(c,rank=None):
        x,y=frame['rev'](c['point'].x,c['point'].y)
        return {'lon':round(x,7),'lat':round(y,7),'line_id':c['line_id'],
                'type':c['type'],'name':c['name'] or c['type'].capitalize(),
                'coverage_ha':round(c['impact'].area/1e4,2),
                'rank':rank}
    return {'status':'ready','method':'greedy-marginal-peat-coverage','metrics':stats,
            'candidates':[serialize(c) for c in candidates[:120]],
            'selected':[serialize(c,i+1) for i,c in enumerate(chosen)],
            'total_screened_coverage_ha':round((covered.area if covered else 0)/1e4,2),
            'spacing_m':220,'buffer_m':350,'terrain_head_constraints':'not available'}
