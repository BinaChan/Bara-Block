#!/usr/bin/env python3
"""Build structured per-site reports and GeoJSON from successful source caches.

Uncollected OSM/BIG/ERA5 fields remain null, never become zero measurements.
"""
from __future__ import annotations
import csv,json,math
from pathlib import Path
from persistent_cache import key_for,read as cache_read
from peat_selection import select_peat_mask
from hydro_foundation import inventory
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'/'derived'
ARTIFICIAL={'canal','drain','ditch'}
NATURAL={'river','stream','tidal_channel'}
STRUCT_WATER={'weir','dam','sluice_gate','lock_gate','floodgate'}
STRUCT_MAN={'weir','dam','pumping_station'}

def layer_key(site,layer):
    lat,lon=site['lat'],site['lon'];km=7.5
    dx=km/(111.195*max(.15,math.cos(math.radians(lat))));dy=km/111.195
    b={'w':max(94,lon-dx),'e':min(144,lon+dx),'s':max(-12,lat-dy),'n':min(7,lat+dy)}
    return key_for('peat_shapes',{'layer':layer,**{k:round(b[k],5) for k in ('w','s','e','n')}})

def documents():
    docs={}
    for name in ('smap','era5'):
        try:
            d=json.loads((OUT/f'{name}_sites.json').read_text(encoding='utf8'))
            docs[name]={x['site']:x for x in d['sites']}
        except (FileNotFoundError,ValueError):docs[name]={}
    return docs

def structured_geojson(osm,site):
    features=[]
    for e in osm.get('elements',[]):
        t=e.get('tags') or {};kind=t.get('waterway') or t.get('water') or ''
        line=t.get('waterway') in ARTIFICIAL|NATURAL or t.get('water')=='canal'
        structure=bool(t.get('sekat_kanal') or t.get('canal_block') or t.get('waterway') in STRUCT_WATER or
                 t.get('man_made') in STRUCT_MAN or t.get('barrier') in ('dam','sluice_gate') or t.get('tunnel')=='culvert')
        if not line and not structure:continue
        category=('canal' if kind in ARTIFICIAL or t.get('water')=='canal' else 'river') if line else 'structure'
        geom=None
        if e.get('type')=='way':
            coords=[[p['lon'],p['lat']] for p in e.get('geometry',[]) if 'lon' in p and 'lat' in p]
            if len(coords)>=2 and line:geom={'type':'LineString','coordinates':coords}
            elif coords and structure:geom={'type':'Point','coordinates':coords[len(coords)//2]}
        elif e.get('type')=='node' and 'lon' in e and 'lat' in e:
            geom={'type':'Point','coordinates':[e['lon'],e['lat']]}
        if geom is None:continue
        props={'osm_id':e.get('id'),'osm_type':e.get('type'),'site':site,
               'category':category,'type':kind or t.get('man_made') or t.get('barrier') or t.get('tunnel') or 'block',
               'name':t.get('name'),'source':'OpenStreetMap', 'tags':t,
               'is_structure':structure}
        features.append({'type':'Feature','geometry':geom,'properties':props})
    return {'type':'FeatureCollection','name':site+'_OSM_hydrology','features':features}

def export(root=ROOT):
    sites=json.loads((root/'sites.json').read_text(encoding='utf8'))['sites'];docs=documents();rows=[]
    geo_dir=OUT/'waterways';geo_dir.mkdir(parents=True,exist_ok=True)
    for site in sites:
        key=key_for('osm',{'site':site['id'],'lat':round(site['lat'],5),'lon':round(site['lon'],5),'radius_km':7.5,'schema':23})
        osm=cache_read('osm',key)
        peat=select_peat_mask(cache_read('peat_shapes',layer_key(site,6)),cache_read('peat_shapes',layer_key(site,48)))
        if not peat['features']:peat=None
        m=inventory(site['lon'],site['lat'],osm,peat)
        sm=docs['smap'].get(site['id']) or {}
        era=docs['era5'].get(site['id']) or {}
        row={'site':site['id'],'name':site['name'],'province':site['province'],'island':site['island'],
             'lon':site['lon'],'lat':site['lat'],'site_width_km':m['site_width_km'],
             'site_height_km':m['site_height_km'],'site_area_km2':m['site_area_km2'],
             'site_area_ha':m['site_area_ha'],'site_perimeter_km':m['site_perimeter_km'],
             'peat_km2':m['peat_km2'],'peat_ha':m['peat_ha'],
             'canal_km':m['canal_km'] if osm is not None else None,
             'river_km':m['river_km'] if osm is not None else None,
             'canal_count':m['canal_count'] if osm is not None else None,
             'river_count':m['river_count'] if osm is not None else None,
             'structure_count':m['structure_count'] if osm is not None else None,
             'osm_status':'saved' if osm else 'pending','peat_status':'saved' if peat else 'pending',
             'smap_status':'saved' if sm else 'pending','era5_status':'saved' if era else 'pending',
             'smap_date_utc':'2024-01-01' if sm else None,
             'smap_surface_m3m3':sm.get('surface_soil_moisture_m3m3'),
             'smap_rootzone_m3m3':sm.get('rootzone_soil_moisture_m3m3'),
             'smap_surface_wetness_fraction':sm.get('surface_wetness_fraction'),
             'smap_rootzone_wetness_fraction':sm.get('rootzone_wetness_fraction'),
             'smap_water_table_model_m':sm.get('modeled_water_table_depth_m'),
             'era5_date_utc':era.get('datetime_utc'),
             'era5_temp_c':era.get('temp_c'),'era5_dewpoint_c':era.get('dewpoint_c'),
             'era5_rh_pct':era.get('rh_pct'),'era5_wind_kmh':era.get('wind_kmh'),
             'era5_wind_toward_deg':era.get('wind_toward_deg'),
             'era5_precipitation_1h_mm':era.get('precipitation_1h_mm'),
             'era5_soil_water_l1_m3m3':era.get('soil_water_l1_m3m3')}
        rows.append(row)
        if osm is not None:
            (geo_dir/(site['id']+'.geojson')).write_text(json.dumps(structured_geojson(osm,site),separators=(',',':')),encoding='utf8')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'structured_sites.json').write_text(json.dumps({'type':'BARA-BLOCK site inventory','sites':rows},indent=2),encoding='utf8')
    with (OUT/'structured_sites.csv').open('w',newline='',encoding='utf8') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
    return rows

if __name__=='__main__':
    rows=export();print(f'Structured exports: {len(rows)} sites; OSM ready {sum(r["osm_status"]=="saved" for r in rows)}, ERA5 ready {sum(r["era5_status"]=="saved" for r in rows)}')
