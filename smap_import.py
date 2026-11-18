#!/usr/bin/env python3
"""Extract actual SMAP L4 GPH point samples for the 29 defined site centres.

EPSG:6933 EASE-Grid 2.0, ~9 km cells. This file is a single 3-hour geophysical
snapshot, NOT Sentinel-1 and NOT a map of canals or structures.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,re
from pathlib import Path
import h5py
import numpy as np
from pyproj import Transformer

ROOT=Path(__file__).resolve().parent
FIELDS={
 'surface_soil_moisture_m3m3':'sm_surface',
 'rootzone_soil_moisture_m3m3':'sm_rootzone',
 'profile_soil_moisture_m3m3':'sm_profile',
 'surface_wetness_fraction':'sm_surface_wetness',
 'rootzone_wetness_fraction':'sm_rootzone_wetness',
 'profile_wetness_fraction':'sm_profile_wetness',
 'modeled_water_table_depth_m':'depth_to_water_table_from_surface',
 'near_surface_air_temp_k':'temp_lowatmmodlay',
 'soil_temp_layer1_k':'soil_temp_layer1',
 'near_surface_wind_ms':'windspeed_lowatmmodlay',
 'precipitation_flux_kgm2s':'precipitation_total_surface_flux',
 'land_saturated_fraction':'land_fraction_saturated',
 'peat_surface_water_flux_kgm2s':'free_surface_water_on_peat_flux',
 'vegetation_leaf_area_index':'leaf_area_index',
}

def clean(value):
    v=float(value)
    return round(v,6) if math.isfinite(v) and v>-9990 else None

def nearest_idx(axis,value):
    # axis may ascend (x) or descend (y), and is a regular grid
    i=round((value-float(axis[0]))/(float(axis[-1])-float(axis[0]))*(len(axis)-1))
    return max(0,min(len(axis)-1,int(i)))

def import_smap(src, root=ROOT):
    src=Path(src)
    sites=json.loads((root/'sites.json').read_text(encoding='utf8'))['sites']
    trans=Transformer.from_crs('EPSG:4326','EPSG:6933',always_xy=True)
    digest=hashlib.file_digest(src.open('rb'),'sha256').hexdigest()
    with h5py.File(src,'r') as h5:
        x=h5['x'][:];y=h5['y'][:]
        grp=h5['Geophysical_Data']
        missing=[name for name in FIELDS.values() if name not in grp]
        if missing:raise ValueError('Missing SMAP fields: '+', '.join(missing))
        results=[]
        for s in sites:
            e,n=trans.transform(s['lon'],s['lat'])
            ix=nearest_idx(x,e);iy=nearest_idx(y,n)
            lon=float(h5['cell_lon'][iy,ix]);lat=float(h5['cell_lat'][iy,ix])
            source_values={label:clean(grp[name][iy,ix]) for label,name in FIELDS.items()}
            results.append({
                'site':s['id'],'name':s['name'],'lon':s['lon'],'lat':s['lat'],
                'sample_lon':round(lon,6),'sample_lat':round(lat,6),
                'distance_to_cell_center_km':round(math.hypot(float(x[ix])-e,float(y[iy])-n)/1000,3),
                'grid_row':iy,'grid_column':ix,**source_values})
        match=re.search(r'(\d{8})T(\d{6})',src.name)
        timestamp=(match.group(1)[:4]+'-'+match.group(1)[4:6]+'-'+match.group(1)[6:8]+'T'+match.group(2)[:2]+':'+match.group(2)[2:4]+':'+match.group(2)[4:]+'Z') if match else None
        result={'source':'NASA SMAP L4 SM geophysical data (SPL4SMGP)',
                'file':src.name,'sha256':digest,'datetime_utc':timestamp,
                'resolution_km':9,'grid':'EASE-Grid 2.0 / EPSG:6933',
                'sampling':'nearest model grid cell to each site centre; no site-scale interpolation',
                'units':'Variables carry unit suffixes; null means file missing value',
                'sites':results}
    target=root/'data'/'derived';target.mkdir(parents=True,exist_ok=True)
    (target/'smap_sites.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    with (target/'smap_sites.csv').open('w',newline='',encoding='utf-8') as f:
        wr=csv.DictWriter(f,fieldnames=list(results[0]));wr.writeheader();wr.writerows(results)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('source',help='Path to downloaded SMAP .h5 or .nc4 file')
    args=ap.parse_args();res=import_smap(args.source)
    print('SMAP samples:',len(res['sites']),'saved in data/derived/',flush=True)
