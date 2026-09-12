# Offline country basemap

`world-map.json` is geometry, not research observations. It contains 177 simplified SVG paths prepared from Natural Earth v5.1.2, 1:110m admin-0 countries, using the Natural Earth 1 projection and a 960 × 490 viewBox. Only the source feature identifier, display name, ISO_A2_EH code (or null) and path are retained. Coordinates are rounded to one decimal screen unit; no country statistics are included or inferred.

- Source: https://github.com/nvkelso/natural-earth-vector/blob/v5.1.2/geojson/ne_110m_admin_0_countries.geojson
- Input SHA-256: `6866c877d39cba9c357620878839b336d569f8c662d3cfab4cb1dbe2d39c977f`
- Public-domain terms: https://www.naturalearthdata.com/about/terms-of-use/
- Projection tooling: `d3-geo` 3.1.1, development dependency only. The map needs no runtime projection package, tiles, remote fonts or external API.

To reproduce, download the linked source GeoJSON, run `node scripts/prepare-country-map.mjs /path/to/ne_110m_admin_0_countries.geojson` and compare stdout with the checked-in asset. The script rejects a different source checksum. It is not part of the statistical pipeline or normal site build, and performs no network calls.

The map joins exact two-letter source codes to existing country aggregates. Regions without a usable source code remain unassigned; no territorial aggregation or alias guessing is performed. Unrepresented small countries/territories remain available in the report selector and complete data table. Borders are background reference, not the basis for assigning papers to countries or a statement of sovereignty.
