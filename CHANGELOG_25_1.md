# BARA—BLOCK 25.1 · Integrated Fix

Based on the user's uploaded BARA_BLOCK_25.zip. The original BARA 25 layout, fixed 29-site catalog and imported/cached data are retained.

- Terrain is the default basemap; Satellite and Street remain selectable.
- Bundled Burned Area and Rewetting Analysis logo added as a local lightweight WebP asset.
- The source archive's existing OSM and peat cache files are preserved.
- OSM is served from cache immediately. Stale entries are refreshed asynchronously from Overpass (approximately every 30 minutes per site while visited); Sync OSM starts a live refresh on demand. Refresh failures never erase a saved network.
- Play with Fire starts independently of the GIS foundation; waterway moisture/drainage, wind, SMAP moisture, and available ERA5-Land data are used in the scenario.
- ERA5-Land retrieval automatically fetches and persists a 2024-01-01, 02:00 UTC record through Open-Meteo, matching the included SMAP snapshot date. The interface polls until the result is available and updates the scenario without stopping playback.
- Optimized block ranking follows fire origin and burn exposure along mapped canal candidates.
- Existing 25 GeoJSON imports, conservation structures, export, and deployment files remain supported.

## Status

This release contains the user's existing OSM/peat cache and SMAP extracts, but no downloaded ERA5-Land observations from the remote provider. The archive API request is implemented and exercised through mocked provider tests; successful remote downloads occur when network access permits. The fire model is a *scenario*, not an observed active-fire detection.
