#!/usr/bin/env python3
"""One request for all sites to the Copernicus ERA5-Land hourly CDS API.

A single day is collected and retained locally. No fabricated weather on failure.
CDS personal access token stays outside the application, in ~/.cdsapirc.
"""
from __future__ import annotations
import argparse,datetime as dt,json,math,os,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
VARIABLES=[
 '2m_temperature','2m_dewpoint_temperature',
 '10m_u_component_of_wind','10m_v_component_of_wind',
 'total_precipitation',
 'volumetric_soil_water_layer_1','volumetric_soil_water_layer_2',
 'volumetric_soil_water_layer_3','volumetric_soil_water_layer_4',
 'soil_temperature_level_1','surface_pressure',
]
SHORT={
 'temp_k':'t2m','dewpoint_k':'d2m','u10_ms':'u10','v10_ms':'v10',
 'soil_water_l1_m3m3':'swvl1','soil_water_l2_m3m3':'swvl2',
 'soil_water_l3_m3m3':'swvl3','soil_water_l4_m3m3':'swvl4',
 'soil_temp_l1_k':'stl1','surface_pressure_pa':'sp',
 'precipitation_accumulated_m':'tp',
}

def round_or_null(x,digits=3):
    try:
        val=float(x)
        return round(val,digits) if math.isfinite(val) and abs(val)<1e8 else None
    except (TypeError,ValueError):return None

def rh_percent(temp_c,dew_c):
    if temp_c is None or dew_c is None:return None
    # Magnus approximation for temperature and dewpoint in Celsius
    return round_or_null(100*math.exp(17.625*dew_c/(243.04+dew_c)-17.625*temp_c/(243.04+temp_c)),1)

def extract_era5(source,when='2024-01-01',root=ROOT):
    import xarray as xr
    import numpy as np
    source=Path(source)
    files=[source]
    if zipfile.is_zipfile(source):
        temp=root/'data'/'era5'/'extracted';temp.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(source) as z:
            names=[n for n in z.namelist() if n.lower().endswith(('.nc','.nc4')) and '..' not in Path(n).parts]
            if not names:raise ValueError('ERA5 archive contains no NetCDF files')
            files=[]
            for n in names:
                target=temp/Path(n).name
                if not target.exists():
                    with z.open(n) as inp,target.open('wb') as out:
                        import shutil;shutil.copyfileobj(inp,out)
                files.append(target)
    sites=json.loads((root/'sites.json').read_text(encoding='utf8'))['sites']
    datasets=[xr.open_dataset(file) for file in files]
    ds=xr.merge(datasets,compat='override',join='outer') if len(datasets)>1 else datasets[0]
    try:
        lat_dim=next((x for x in ('latitude','lat') if x in ds.coords),None)
        lon_dim=next((x for x in ('longitude','lon') if x in ds.coords),None)
        time_name=next((x for x in ('valid_time','time') if x in ds.coords),None)
        if not lat_dim or not lon_dim or not time_name:raise ValueError('ERA5 expected latitude/longitude/time coordinates')
        if len(ds[time_name].dims)!=1:raise ValueError('ERA5 must have 1D observation time')
        time_dim=ds[time_name].dims[0]
        # Match the supplied SMAP acquisition day and sample 02:00 UTC after 01:00.
        times=np.asarray(ds[time_name].values).astype('datetime64[h]')
        target=np.datetime64(when+'T02:00')
        idx=int(np.argmin(abs(times-target)))
        if str(times[idx])[:10]!=when:raise ValueError('ERA5 source date differs from '+when)
        output=[]
        for s in sites:
            site_ds=ds.sel({lat_dim:s['lat'],lon_dim:s['lon']},method='nearest')
            fields={}
            for label,var in SHORT.items():
                fields[label]=round_or_null(site_ds[var].isel({time_dim:idx}).values) if var in site_ds else None
            t=round_or_null((fields['temp_k']-273.15) if fields['temp_k'] is not None else None,2)
            dew=round_or_null((fields['dewpoint_k']-273.15) if fields['dewpoint_k'] is not None else None,2)
            u=fields['u10_ms'];v=fields['v10_ms']
            wind=round_or_null(3.6*math.hypot(u,v),1) if u is not None and v is not None else None
            wind_to=round_or_null((math.degrees(math.atan2(u,v))+360)%360,1) if u is not None and v is not None else None
            # ERA5-Land accumulations are not hourly increments; subtract within same day.
            rain=None
            if 'tp' in site_ds and idx>0 and str(times[idx-1])[:10]==when:
                v2=round_or_null(site_ds['tp'].isel({time_dim:idx}).values,7)
                v1=round_or_null(site_ds['tp'].isel({time_dim:idx-1}).values,7)
                if v1 is not None and v2 is not None:rain=round_or_null(max(0,(v2-v1)*1000),3)
            output.append({'site':s['id'],'name':s['name'],
                'sample_lon':round(float(site_ds[lon_dim].values),5),
                'sample_lat':round(float(site_ds[lat_dim].values),5),
                'datetime_utc':str(times[idx]).replace(' ','T')+':00Z',
                **fields,'temp_c':t,'dewpoint_c':dew,'rh_pct':rh_percent(t,dew),
                'wind_kmh':wind,'wind_toward_deg':wind_to,'precipitation_1h_mm':rain})
        output_doc={'source':'Copernicus CDS ERA5-Land hourly reanalysis',
            'date_utc':when,'sample_hour_utc':2,
            'dataset':'reanalysis-era5-land',
            'spatial_resolution':'~9 km / 0.1 degree',
            'method':'Nearest grid-cell instantaneous weather at 02 UTC; precipitation 02-01 UTC accumulated difference',
            'variables':VARIABLES,'sites':output}
        target_dir=root/'data'/'derived';target_dir.mkdir(parents=True,exist_ok=True)
        (target_dir/'era5_sites.json').write_text(json.dumps(output_doc,indent=2),encoding='utf8')
        import csv
        with (target_dir/'era5_sites.csv').open('w',newline='',encoding='utf8') as f:
            wr=csv.DictWriter(f,fieldnames=list(output[0]));wr.writeheader();wr.writerows(output)
        return output_doc
    finally:
        ds.close()
        for opened in datasets:
            if opened is not ds:opened.close()

def download_era5(when='2024-01-01',root=ROOT):
    try:import cdsapi
    except ImportError:raise RuntimeError('Install CDS API: pip install cdsapi>=0.7.7')
    cdsfile=Path.home()/'.cdsapirc'
    if not cdsfile.exists() and not os.environ.get('CDSAPI_KEY'):
        raise RuntimeError('ERA5-Land needs your CDS access token (~/.cdsapirc). Accept dataset terms at cds.climate.copernicus.eu first.')
    sites=json.loads((root/'sites.json').read_text(encoding='utf8'))['sites']
    west=math.floor((min(s['lon'] for s in sites)-0.2)*10)/10
    east=math.ceil((max(s['lon'] for s in sites)+0.2)*10)/10
    south=math.floor((min(s['lat'] for s in sites)-0.2)*10)/10
    north=math.ceil((max(s['lat'] for s in sites)+0.2)*10)/10
    output=root/'data'/'era5';output.mkdir(parents=True,exist_ok=True)
    target=output/f'era5_land_{when}.nc'
    if target.exists() and target.stat().st_size>10000:return target
    request={'variable':VARIABLES,'year':[when[:4]],'month':[when[5:7]],'day':[when[8:10]],
             'time':[f'{h:02d}:00' for h in range(24)],'area':[north,west,south,east],
             'data_format':'netcdf','download_format':'unarchived'}
    client=cdsapi.Client()
    client.retrieve('reanalysis-era5-land',request,str(target))
    if not target.exists() or target.stat().st_size<10000:raise RuntimeError('ERA5-Land download did not complete')
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Collect ERA5-Land once for all 29 sites')
    parser.add_argument('--date',default='2024-01-01')
    parser.add_argument('--input',help='Use an existing ERA5 NetCDF/ZIP without downloading')
    args=parser.parse_args();dt.date.fromisoformat(args.date)
    source=Path(args.input) if args.input else download_era5(args.date)
    print('ERA5-Land:',len(extract_era5(source,args.date)['sites']),'site summaries saved')
