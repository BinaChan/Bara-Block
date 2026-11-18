"""Durable, site-keyed JSON cache for BARA-BLOCK.

The repository ships a read-only seed cache under ``data/tersimpan``. In hosted
installations ``BARA_CACHE_DIR`` can point to an independently mounted, writable
volume. Runtime records take precedence; missing records fall back to bundled
seed data. This keeps map layers available even when the runtime volume starts
empty or when an external geospatial service is temporarily unavailable.
"""
from pathlib import Path
import json
import os
import hashlib
import threading

ROOT = Path(__file__).resolve().parent
BUNDLED = ROOT / 'data' / 'tersimpan'
_runtime = os.getenv('BARA_CACHE_DIR', '').strip()
BASE = Path(_runtime).expanduser() if _runtime else BUNDLED
if not BASE.is_absolute():
    BASE = ROOT / BASE
# Only deployments with a separate runtime volume need a seed fallback. This
# also lets isolated tests override BASE without accidentally reading real data.
SEED_BASE = BUNDLED if _runtime else None
LOCK = threading.RLock()


def key_for(kind, payload):
    safe = json.dumps(payload, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':'))
    return hashlib.sha256((kind + '|' + safe).encode()).hexdigest()[:24]


def _validated_filename(kind, key):
    if (not kind.replace('_', '').isalnum() or len(key) != 24 or
            any(c not in '0123456789abcdef' for c in key)):
        raise ValueError('Invalid cache key')
    return kind, key + '.json'


def path_for(kind, key):
    directory, filename = _validated_filename(kind, key)
    return BASE / directory / filename


def read(kind, key):
    directory, filename = _validated_filename(kind, key)
    search = [BASE / directory / filename]
    if SEED_BASE is not None and BASE != SEED_BASE:
        search.append(SEED_BASE / directory / filename)
    with LOCK:
        for file in search:
            try:
                return json.loads(file.read_text(encoding='utf-8'))
            except (FileNotFoundError, ValueError, UnicodeError, OSError):
                continue
    return None


def write(kind, key, data):
    file = path_for(kind, key)
    with LOCK:
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_name(file.name + '.tmp' + str(os.getpid()) +
                             str(threading.get_ident()))
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False,
                                      separators=(',', ':')), encoding='utf-8')
            os.replace(tmp, file)
        finally:
            if tmp.exists():
                tmp.unlink()
    return file
