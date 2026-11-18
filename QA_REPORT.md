# QA · BARA—BLOCK 25

**Automated browser checks**: desktop (1440 × 900) and mobile (390 × 844), no JavaScript page exceptions, geospatial site units, six-item legend, all three basemaps, waterways/structures, peat mask, fire Play/Pause, scenario control, numbered proposals.

**Spatial ranking regression**: moving simulated ignition from centre to a southern canal then to a northern canal changed the first proposed canal accordingly. Matched marker ranks 1, 2, 3. Camera moves do not change simulation frame.

**Imports**: GeoJSON canal import exercised in public browser-local mode; count increased from 5 to 6 test canals.

**API**: untrusted public mode blocks server-edits and imports, and prevents public static access to Python source, site catalog, and cache contents.

**Test fixtures**: preview screenshots use synthetic OSM canals and peat boundaries. They do not claim a live download of BIG or OSM services. Upstream network downloads were not verified here.
