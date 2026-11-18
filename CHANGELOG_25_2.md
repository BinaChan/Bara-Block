# Changes — BARA-BLOCK 25.2

- Original BARA-BLOCK 25 interface and local logo preserved. Terrain remains the initial basemap.
- Uncached OSM queries are now asynchronous and return a fetch status immediately. Two providers are queried concurrently in a rate-limited worker, with fallback providers if needed.
- Cached OSM features render before background refresh; 30-minute TTL and periodic checks keep the current site updatable without wiping saved data.
- Peat boundaries load independently using saved site masks, BIG soil/ecosystem/system polygon layers and map overlays. Previously saved peat masks are reused.
- Old empty BIG result caches are eligible for recheck rather than remaining empty forever.
- Explicit mineral soil values override peat ecosystem designations in soil classification.
- Canal-only candidate ranking is available while peat downloads; peat coverage remains blank until real geometry arrives.
- Canal geometry/peat geometry updates trigger additional foundation calculations without waiting for other services.
- Spatial optimizer avoids redundant projection/area operations and caps expensive candidate ranking; fire-grid peat rasterization is reused across simulation variants.
- Site switch sequencing prevents stale older calculations replacing new site results.
- Fire and ERA5-Land behavior from BARA-BLOCK 25.1 remains intact.
