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
