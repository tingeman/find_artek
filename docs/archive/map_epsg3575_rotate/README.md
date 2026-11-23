# Archived: overview map in EPSG:3575, rotated with leaflet-rotate

What this is: the map code used until plan "features" T3 (2026-11-23). The overview map
(and the report page) was drawn in **EPSG:3575** (North Pole LAEA Europe,
`+proj=laea +lat_0=90 +lon_0=10 ...`) with **GBIF OSM-light** tiles
(`https://tile.gbif.org/3575/omt/{z}/{x}/{y}@{r}x.png?style=osm-light`, 512 px tiles) and
**rotated by -54°** with **leaflet-rotate 0.2.8** (`rotate: true`, `map.setBearing(-54)`) so
that Greenland was upright.

- `my-map-class.js`: the owner's map class (`MyMapClass`), unchanged from the last version in
  `app-main/publications/static/publications/js/class/`.
- `leaflet-rotate-0.2.8/`: the vendored release file and its licence (GPL-3.0).

It is **not served**: these files are outside every `static/` directory, so `collectstatic`
doesn't pick them up and no page loads them. They are kept for a possible revert.

Replaced by the shared map component `app-main/publications/static/publications/js/map/`
in **EPSG:3574** (North Pole LAEA Atlantic) without rotation; why: `readme.md`, section
"Third-party JavaScript", "Map projection".

## Reverting

1. Move `leaflet-rotate-0.2.8/` back to `app-main/publications/static/publications/vendor/`
   and add it to the table in `readme.md`.
2. Load it on the map pages after `proj4leaflet.js` and before the map scripts:
   `<script src="{% static 'publications/vendor/leaflet-rotate-0.2.8/leaflet-rotate-src.js' %}" defer></script>`.
3. Use the CRS, tiles and rotation of `my-map-class.js`: `L.Proj.CRS('EPSG:3575', ...)` with
   origin `[-extent, extent]`, `extent = Math.sqrt(2) * 6371007.2`, resolutions
   `extent / 512 / 2^(z-1)` for z = 0..16; the GBIF tile layer (tileSize 512); `L.map(el, {crs,
   rotate: true})` and `map.setBearing(-54)`. Either move `my-map-class.js` back or carry these
   settings into `find-artek-map.js` (the Dataforsyningen WMS services also list EPSG:3575).
