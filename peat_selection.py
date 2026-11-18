"""Strict mapped-peat mask from BIG soil layer 6 or explicit FEG soil attributes.

Layer 6 includes mineral/wetland landforms, so use Gambut landforms only.
Layer 48 is an ecosystem-function map, not itself proof of peat soil.
"""
from __future__ import annotations

def _word(val):
    return str(val if val is not None else '').strip().lower()

def _peat_tag(text):
    s=_word(text)
    return ('gambut' in s or 'peat' in s) and not any(x in s for x in ('non gambut', 'non-gambut', 'bukan gambut', 'tidak gambut', 'no peat', 'nonpeat', 'mineral'))

def is_peat_feature(feature, layer):
    p=feature.get('properties') or {}
    if layer==6:
        return _peat_tag(p.get('landform') or p.get('LANDFORM'))
    if layer==48:
        # Only explicit soil evidence; do not treat the entire FEG ecosystem as peat soil.
        soil=p.get('tnh_gambut') if p.get('tnh_gambut') is not None else p.get('TNH_GAMBUT')
        # An explicit non-peat/mineral soil designation overrides the ecosystem class.
        if soil is not None and str(soil).strip():return _peat_tag(soil)
        return _peat_tag(p.get('feg_peat') or p.get('FEG_PEAT'))
    return False

def select_peat_mask(soil, ecosystem):
    result=[];sources=[]
    for layer,doc in ((6,soil),(48,ecosystem)):
        if not isinstance(doc,dict):continue
        chosen=[f for f in doc.get('features',[]) if isinstance(f,dict) and f.get('geometry') and is_peat_feature(f,layer)]
        if chosen:
            if layer==6:
                return {'type':'FeatureCollection','features':chosen,'source':'BIG peat soil map','layer':6}
            result.extend(chosen);sources.append('BIG FEG peat-soil attributes')
    return {'type':'FeatureCollection','features':result,'source':', '.join(sources),'layer':48 if result else None}
