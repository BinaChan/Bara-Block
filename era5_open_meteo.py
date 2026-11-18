#!/usr/bin/env python3
"""One-time ERA5-Land weather via the Open-Meteo historical archive API.

This is an ERA5-Land-specific model request (models=era5_land), not a blended
forecast. Batched, cached, explicit missing states; no re-fetch of saved sites.
For official CDS access and original NetCDF use era5_land.py instead.
"""
from __future__ import annotations
import argparse,json,math,time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen,Request
from persistent_cache import key_for,read as cache_read,write as cache_write
ROOT=Path(__file__).resolve().parent
API='https://archive-api.open-meteo.com/v1/archive'
FIELDS=['temperature_2m','relative_humidity_2m','dew_point_2m','precipitation',
        'wind_speed_10m','wind_direction_10m',
        'soil_moisture_0_to_7cm','soil_moisture_7_to_28cm','soil_moisture_28_to_100cm',
        'surface_pressure']

def finite(value,decimals=3):
    try:
        num=float(value)
        return round(num,decimals) if math.isfinite(num) else None
    except (TypeError,ValueError):return None

def cache_key(site,when):return key_for('era5_open_meteo',{'site':site['id'],'date':when,'model':'era5_land'})

def parse_site(site,data,when):
    if data.get('error'):raise ValueError(str(data.get('reason','Provider error')))
    hr=data.get('hourly') or {};times=hr.get('time') or []
    hh=when+'T02:00'
    if hh not in times:raise ValueError('No 02:00 UTC observation for '+when)
    i=times.index(hh)
    def v(k):
        a=hr.get(k,[])
        return finite(a[i]) if len(a)>i else None
    temp=v('temperature_2m');dew=v('dew_point_2m');wind=v('wind_speed_10m');wd=v('wind_direction_10m')
    return {'site':site['id'],'name':site['name'],'datetime_utc':hh+':00Z',
         'sample_lat':finite(data.get('latitude'),5),'sample_lon':finite(data.get('longitude'),5),
         'temp_c':temp,'dewpoint_c':dew,'rh_pct':v('relative_humidity_2m'),
         'wind_kmh':wind,'wind_toward_deg':finite((wd+180)%360,1) if wd is not None else None,
         'precipitation_1h_mm':v('precipitation'),'soil_water_l1_m3m3':v('soil_moisture_0_to_7cm'),
         'soil_water_l2_m3m3':v('soil_moisture_7_to_28cm'),
         'soil_water_l3_m3m3':v('soil_moisture_28_to_100cm'),
         'surface_pressure_pa':finite(v('surface_pressure')*100) if v('surface_pressure') is not None else None,
         'source':'ERA5-Land via Open-Meteo historical archive API'}

def get_many(sites,when):
    params={'latitude':','.join(str(s['lat']) for s in sites),
            'longitude':','.join(str(s['lon']) for s in sites),
            'start_date':when,'end_date':when,'timezone':'UTC',
            'models':'era5_land','hourly':','.join(FIELDS),
            'temperature_unit':'celsius','wind_speed_unit':'kmh','precipitation_unit':'mm',
            'cell_selection':'nearest'}
    url=API+'?'+urlencode(params)
    req=Request(url,headers={'User-Agent':'BARA-BLOCK/23 research site collector','Accept':'application/json'})
    with urlopen(req,timeout=40) as f:
        if int(f.headers.get('Content-Length','0') or 0)>10_000_000:raise ValueError('API response too large')
        raw=f.read(10_000_001)
    if len(raw)>10_000_000:raise ValueError('API response too large')
    data=json.loads(raw)
    if isinstance(data,dict) and data.get('error'):raise ValueError(str(data.get('reason','API error'))[:220])
    if isinstance(data,dict):data=[data]
    if not isinstance(data,list) or len(data)!=len(sites):raise ValueError('ERA5-Land returned an unexpected site count')
    return [parse_site(s,d,when) for s,d in zip(sites,data)]

def export(sites,when,root=ROOT):
    all_rows=[cache_read('era5_open_meteo',cache_key(site,when)) for site in sites]
    rows=[r for r in all_rows if r]
    if not rows:return 0
    doc={'source':'ERA5-Land via Open-Meteo historical archive API','date_utc':when,
         'sample_hour_utc':2,'dataset':'ERA5-Land (models=era5_land)',
         'spatial_resolution':'~9 km / 0.1 degree',
         'method':'One 02:00 UTC hourly sample per site; wind direction converted from FROM to TOWARD',
         'variables':FIELDS,'sites':rows}
    target=root/'data'/'derived';target.mkdir(parents=True,exist_ok=True)
    (target/'era5_sites.json').write_text(json.dumps(doc,indent=2),encoding='utf8')
    import csv
    with (target/'era5_sites.csv').open('w',newline='',encoding='utf8') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
    return len(rows)

def collect(when='2024-01-01',max_sites=29):
    sites=json.loads((ROOT/'sites.json').read_text(encoding='utf8'))['sites'][:max_sites]
    missing=[s for s in sites if cache_read('era5_open_meteo',cache_key(s,when)) is None]
    print(f'ERA5-Land: {len(sites)-len(missing)} sites cached, {len(missing)} remaining.',flush=True)
    errors=[]
    for i in range(0,len(missing),4):
        group=missing[i:i+4]
        try:
            result=get_many(group,when)
            for s,row in zip(group,result):cache_write('era5_open_meteo',cache_key(s,when),row)
            print('  saved',', '.join(s['id'] for s in group),flush=True)
            if i+4<len(missing):time.sleep(3)
        except Exception as e:
            errors.append(str(e)[:150]);print('  unavailable',','.join(s['id'] for s in group),str(e)[:120],flush=True)
    n=export(sites,when)
    print('ERA5-Land saved:',n,'of',len(sites),flush=True)
    if errors:print('Provider issues:', '; '.join(errors[:3]),flush=True)
    return n

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--date',default='2024-01-01')
    ap.add_argument('--max-sites',type=int,default=29)
    args=ap.parse_args();collect(args.date,args.max_sites)
