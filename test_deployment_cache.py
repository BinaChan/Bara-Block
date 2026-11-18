"""Regressions for the container seed-cache and public-read-only deployments."""
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import json
import persistent_cache as pc
import server


def test_seed_fallback_and_runtime_priority(tmp_path):
    seed, runtime = tmp_path / 'seed', tmp_path / 'runtime'
    key = pc.key_for('osm', {'site': 'EXAMPLE'})
    file = seed / 'osm' / (key + '.json')
    file.parent.mkdir(parents=True)
    file.write_text('{"source":"seed"}', encoding='utf-8')
    with patch.object(pc, 'BASE', runtime), patch.object(pc, 'SEED_BASE', seed):
        assert pc.read('osm', key)['source'] == 'seed'
        pc.write('osm', key, {'source': 'live'})
        assert pc.read('osm', key)['source'] == 'live'
        assert json.loads(file.read_text())['source'] == 'seed'
        (runtime / 'osm' / (key + '.json')).unlink()
        assert pc.read('osm', key)['source'] == 'seed'


def test_public_mode_reads_precomputed_foundation():
    payload = {'site': 'SUM-05', 'lat': -0.65, 'lon': 103.3,
               'osm': None, 'peat': None}
    saved = {'status': 'ready',
             'metrics': {'osm_available': True, 'peat_available': True},
             'selected': [{'lon': 103.3}], 'candidates': []}
    raw = json.dumps(payload).encode()
    handler = server.Handler.__new__(server.Handler)
    handler.headers = {'Content-Length': str(len(raw))}
    handler.rfile = BytesIO(raw)
    handler.reply = lambda code, value: (code, value)
    with patch.object(server, 'PUBLIC_READ_ONLY', True), \
         patch.object(server, 'disk_read', return_value=saved), \
         patch.object(server, 'optimize',
                      side_effect=AssertionError('recomputed cached result')):
        status, response = handler.site_foundation()
    assert status == 200
    assert response['cached']
    assert response['selected'] == saved['selected']


def test_public_site_export_keeps_edits_private():
    site = next(s for s in server.site_entries() if s['id'] == 'SUM-01')
    handler = server.Handler.__new__(server.Handler)
    handler.site_id = lambda: site['id']
    handler.reply = lambda code, value: (code, value)
    private = {'canals': [{'name': 'private'}], 'blocks': []}
    with patch.object(server, 'PUBLIC_READ_ONLY', True), \
         patch.object(server, 'disk_read', return_value=private), \
         patch.object(server.Handler, 'environment_data', return_value={}):
        status, response = handler.structured()
    assert status == 200
    assert response['manual_edits'] == {'canals': [], 'blocks': []}


def test_build_includes_seed_data():
    root = Path(__file__).parent
    ignore = (root / '.dockerignore').read_text()
    docker = (root / 'Dockerfile').read_text()
    assert 'data/tersimpan\n' not in ignore
    assert 'data/tersimpan/edits/' in ignore
    assert 'BARA_CACHE_DIR=/app/data/runtime_cache' in docker
    assert 'COPY . /app' in docker
