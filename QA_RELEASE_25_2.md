# QA — BARA-BLOCK 25.2

## Results

- 7 automated regression tests passed: offline API imports, public mode, basemap, dynamic fire-block rankings, Play/Pause, OSM cache and ERA5 acquisition mock, uncached OSM/BIG fetch responding promptly, and strict peat-soil filtering.
- A real-data browser test using the bundled SUM-05 OSM and peat-mask snapshots passed: 298 OSM features, 34 filtered peat features, 120 canal-block candidates, physical peat area of 9,802.83 ha, visible logo, Terrain selected, fire animation advancing.
- Spatial processing benchmarks (local machine, only calculate time, 8 included OSM caches): about 0.01–0.16 s per site. Live network time is separate and variable.
- No live upstream BIG/OSM/ERA5 fetch confirmed from this build environment; no availability or response-time guarantee is implied for these external sources.

## Known data constraints

- 8 sites include saved OSM geometries in the supplied ZIP; the remaining sites fetch when opened if the remote provider allows it.
- Only the available site peat masks and cached BIG overlays are bundled; newly selected sites do not gain invented peat polygons.
- ERA5-Land is requested on demand for the historical date in the server configuration. The fire model continues in scenario mode if it is not available.
