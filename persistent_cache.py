"""Durable local JSON cache for BARA-BLOCK 21; atomic writes, bounded keys."""
from pathlib import Path
import json,os,hashlib,threading
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'data'/'tersimpan'
LOCK=threading.RLock()

def key_for(kind, payload):
    safe=json.dumps(payload,sort_keys=True,ensure_ascii=True,separators=(',',':'))
    return hashlib.sha256((kind+'|'+safe).encode()).hexdigest()[:24]

def path_for(kind,key):
    if not kind.replace('_','').isalnum() or len(key)!=24 or any(c not in '0123456789abcdef' for c in key):
        raise ValueError('Invalid cache key')
    return BASE/kind/(key+'.json')

def read(kind,key):
    file=path_for(kind,key)
    try:
        with LOCK:return json.loads(file.read_text(encoding='utf-8'))
    except (FileNotFoundError,ValueError,UnicodeError):return None

def write(kind,key,data):
    file=path_for(kind,key)
    with LOCK:
        file.parent.mkdir(parents=True,exist_ok=True)
        tmp=file.with_name(file.name+'.tmp'+str(os.getpid())+str(threading.get_ident()))
        try:
            tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
            os.replace(tmp,file)
        finally:
            if tmp.exists():tmp.unlink()
    return file
