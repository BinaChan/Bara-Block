# BARA—BLOCK 25 · Public Interface

- Removed the Sentinel-1 peat-only dashboard, VV/VH overlays, radar API endpoints and related processing dependencies.
- Reduced map legend to Canal, River, Structure, Peat, Block and Fire.
- Removed illustrative legacy canal lines from default public map; mapped OSM/GeoJSON hydrology remains.
- Ranked canal-block proposals by the position and modeled extent of the ignition fire; ranked circles match the numbered candidate list.
- Changed simulation grid to a site-fixed 15 × 15 km frame; zooming/panning does not move the modeled fire.
- Repositioned overlapping number labels with anchor connectors.
- Retained editable canals, manual blocks (M), ERA5-Land/SMAP feeds, site dimensions, BIG/OSM caches, GeoJSON import and all three basemaps.
- Enabled same-origin APIs on public HTTPS hosts and added optional public read-only hosting mode with browser-local imports and edits.
- Restricted static-file exposure and supplied a container-based deployment template.
