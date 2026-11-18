# BARA—BLOCK 25.2

Burned Area and Rewetting Analysis for Optimized Canal Blocking. Based on the user-supplied BARA-BLOCK 25, retaining the original interface, supplied logo, and existing site data.

## Run

Windows: extract this ZIP, then double-click `START_WINDOWS.bat`. Requires Python 3.10+ and internet access for basemap and first-time live source collection. The launcher installs only core spatial packages when needed.

macOS/Linux: run `START_MAC_LINUX.sh` from the extracted folder. Server defaults to `http://127.0.0.1:8768`.

## Map workflow

1. Select a site. Terrain is the default basemap; Street and Satellite remain available.
2. The cached OSM canal/river/structure network appears first when present. `Sync OSM` requests updated geometry; the server revalidates stale data after 30 minutes and the open app checks periodically.
3. BIG peat soil, ecosystem and peat-system overlays load separately; saved mapped peat soil masks are shown immediately where available. No ecosystem boundary is automatically assumed to be peat soil.
4. Fire mode: click a starting point and press Play. Animation does not depend on the status of OSM, peat, or ERA5.
5. Candidate canal blocks first appear from mapped artificial canals; the fire footprint determines their numbering. Peat area coverage appears only when mapped peat soil polygons are available.
6. ERA5-Land is acquired per site when the external provider is reachable, and saved automatically. If unavailable, Fire continues as a scenario using the visible panel controls.

## Data behavior

- The ZIP includes the user's previously saved site cache. Other sites are fetched asynchronously and cached per site; successful downloads are reused.
- OSM queries run on the server with bounded provider concurrency, saved-first behavior, and live refresh. Failed refreshes do not erase cached geometry.
- BIG peat polygons are fetched asynchronously. A saved peat mask or map overlay is shown before remote queries complete. Empty response caches are periodically rechecked.
- Physical site measurements describe analytical 15 × 15 km footprints, not legal property boundaries.
- Initial canal candidates are real OSM/drawn-line candidates but are **not** certified engineering placements. Peat coverage estimates require mapped peat polygons.
- ERA5-Land dataset in this workflow is the historical snapshot dated 2024-01-01; it is not a current weather feed.
- Public deployments can set `BARA_PUBLIC_READ_ONLY=1`; Dockerfile is included. Use a persistent writable volume for `data/tersimpan` if desired.

## Tests

`python -m pytest -q test_progressive25_2.py test_server25.py test_integration29.py test_public25.py`

The external OSM/BIG/ERA5 services were not downloaded live during this build; background acquisition paths were tested with controlled provider responses, and the included cache was tested using real bundled geometries.

## Docker deployment and persistent geospatial cache

Bundled seed data for OSM, BIG peat and precomputed foundations are stored under
`data/tersimpan/{osm,peat_shapes,peat_raster,peat_masks,foundation}`.
Docker now **includes these seed datasets**. A deployed container can display
previously collected map layers before live providers respond.

Set `BARA_CACHE_DIR=/app/data/runtime_cache` to store new live data separately.
Reads prioritize the writable runtime directory and fall back to bundled seed
data when a new runtime volume is empty:

```bash
docker build -t bara-block .
docker run --rm -p 8080:8080 \
  -v bara-block-runtime:/app/data/runtime_cache \
  bara-block
```

Open `http://localhost:8080`. On a cloud host, configure the persistent volume
**at `/app/data/runtime_cache`**, *not* at `/app/data/tersimpan`: mounting
over the latter would hide bundled data. Runtime records otherwise disappear
when an ephemeral container is replaced, but bundled seed data remain.

`BARA_PUBLIC_READ_ONLY=1` disallows editing shared datasets while still
allowing the API to read precomputed optimization results. Public structured
exports do not include local manual edits.

GitHub Pages cannot serve this Python application's `/api/*` endpoints;
deploy the backend to a Docker/Python service to use the cache and simulator.
`.gitignore` does not untrack previously committed edit files: review any
existing `data/tersimpan/edits` files before public redistribution.

## GitHub Pages: cache-backed demo (no Python backend)

The URL `https://binachan.github.io/Bara-Block/` is static-only. The
`static_api.js` adapter runs **before** `app.js` and maps the app's
`/api/*` calls to existing repository JSON datasets on GitHub Pages.
It retrieves cached OpenStreetMap features, peat polygon/soil masks,
peat raster layers, SMAP snapshots and precomputed foundation candidates
using deterministic SHA-256 cache paths.

- Initial demo site is `SUM-05`, which has existing OSM, peat and optimized-block data.
- Previously cached sites load from `data/tersimpan`; sites with no
  cache cannot show invented maps or measurements.
- `Sync OSM` attempts a best-effort browser-side Overpass refresh, subject
  to CORS, provider rate limits and connectivity; it cannot persist new
  data to the GitHub repository.
- Fire animation continues to be computed client-side. Optimization for
  previously cached sites is from precomputed results. Browser-side
  screening of new mapped canals is **not** full Python hydrological
  optimization.
- ERA5-Land cannot be fetched dynamically from the Python provider on Pages.
  Only a saved `data/derived/era5_sites.json`, if present, can be displayed.
- For an actually live multi-user deployment, deploy the Docker/Python
  server with persistent `BARA_CACHE_DIR` storage. GitHub Pages is not
  a substitute for it.
