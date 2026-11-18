# BARA—BLOCK 25.1 Quality Checks

## Automated tests
- Public UI regression: canvas interaction, canal network, area units, optimized block order changing when fire moves, basemap choices, GeoJSON imports, Play/Pause.
- API safety: anonymous read-only permissions and private file restrictions.
- OSM cache + live update: saved geometry shown before provider refresh, fresh features replace cache successfully.
- ERA5-Land ingest: fake provider returns genuine-schema record, saved to disk, then available from /api/environment without requesting it twice.
- Browser integration (mocked ERA5-Land and peat fixture, original OSM cached geometry): desktop and mobile, initial Terrain, real bundled logo, fire timeline and block visualization.

## Data and deployment
- Bundled OSM geometry and SMAP extracts are taken from the user's uploaded BARA_BLOCK_25.zip.
- Live provider availability and official BIG/OSM tile-server access depend on hosting network and provider uptime. Tests used controlled provider fixtures, not confirmed live remote downloads.
- Site boundaries represent the analytical 15 × 15 km footprint; they are not cadastral boundaries.
