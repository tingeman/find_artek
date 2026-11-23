# Status: Feature registration

Plan: [PLAN_features.md](PLAN_features.md). Branch: `agent-features` (from `develop/main`), worktree `..\find_artek_agent-features`.

## Now
Plan approved 2026-11-23. T2 done. Three implementers running (started 2026-11-23), each in its own worktree, all uncommitted:
- **T3** (still running; redirected 2026-11-23 to EPSG:3574 without rotation, Arctic SDI fallback, archive of the old code, readme "Map projection") in `..\find_artek_agent-features` (branch `agent-features`): shared map component `static/publications/js/map/find-artek-map.js` (EPSG:3575, layer switcher with Dataforsyningen WMS, rotation as option `bearing`), map/report/feature/frontpage pages, tests `test_map_component.py`, run.sh image `find_artek:features-t3`. Then the main session's browser check (dev stack from the worktree).
- **T9 committed** on `agent-features-t9` (b6a4b1d), to be merged into `agent-features` after T3 is committed.
- **T4 committed** on `agent-features-t4` (`2ce832e`, gate rerun by the main session: 22/22, 807 tests OK). Merge order: T3 commit on `agent-features`, then merge `agent-features-t9`, then `agent-features-t4` (rerun run.sh after each), then remove both worktrees and branches. Showing the original coordinates on `feature.html` moved from T4 to T5.

Parallel rule: agents only in separate worktrees (run.sh builds from the folder) and without shared files. T5-T8 and T10 share `views.py`/`urls.py`/templates: one at a time. T9 could run beside T3 in its own worktree.

Next: T3. Browser checks: owner chose (a) 2026-11-23, `.dev.env` is in the worktree; the main session runs the dev stack from `..ind_artek_agent-features` (`docker compose -f docker-compose.yml -f docker-compose.develop.yml up -d --build` there; same DB volume; stop it first in the owner's checkout). T4 and T9 could then follow; run agents one at a time in the worktree (they share `views.py`, `urls.py`, `report.html`; owner allows parallel agents only without shared files).

## Done
- T4 2026-11-23: `publications/geometry.py` (from_geojson, from_vertices, GeometryResult.apply_to, parse_srid, transform_note, GR96 detection by datum), Feature `source_srid`/`source_geometry`/`transform_note`/`observation_date` + `epoch_date`, migration 0006 (4 AddField only), `EDIT_FEATURE`, FA-R107 dead form path, `modified_by` in add-by-map; 55 tests; `test_person_markers` migration test changed to reverse only 0005 (MariaDB DDL in test transaction); agent's run.sh 22/22, 807 tests OK. GDAL 3.10.3, PROJ 9.6.0; GR96 -> WGS84 is the null transformation in PROJ.
- T9 2026-11-23: appendix delete (`EDIT`, confirm page, FileObject kept when still used, file removed after commit), 15 tests, smoke entry added; run.sh 22/22, 783 tests OK (`b6a4b1d` on `agent-features-t9`).
- 2026-11-23 owner decision: **EPSG:3574 without rotation** (Greenland upright; no GPL-3.0 leaflet-rotate; no draw/rotate risk). GBIF (3575 only) dropped; base layers Dataforsyningen topographic (default with token), satellite, Sentinel-2, and the **Arctic SDI basemap** (`https://basemap.arctic-sdi.org/mapcache/wmts/1.0.0/arctic_cascading/default/3574/{z}/{y}/{x}.png`, 256 px, levels 0-10, origin ±4889334.802955, no token; fallback outside Greenland and without token). Owner's rotated 3575 code kept, not served, in `docs/archive/map_epsg3575_rotate/` (T3). Decision and arguments go into `readme.md` "Map projection" (T3).
- T2 2026-11-23: map scripts vendored in `static/publications/vendor/` (Leaflet 1.9.4, proj4 2.22.0, Proj4Leaflet 1.0.2 unpatched, leaflet-rotate 0.2.8, leaflet-draw 1.0.4; npm sha512 checked), `FA_DATAFORSYNINGEN_TOKEN` + context processor `map_settings`, readme "Third-party JavaScript", 18 tests; run.sh 22/22, 769 tests OK (`cf7ed98`).
- T0 2026-11-23: `agent-features` created from `develop/main` with worktree; `agent-fixes` (FA-R101, 348219a) merged into it instead of a fast-forward of `develop/main` (FA-R101 reaches `develop/main` with the feature merge). Owner put the token into `.dev.env`.
- 2026-11-23: owner decisions: original coordinates + `observation_date` (migration adding nullable columns approved), upload path `reports/<year>/<number>/features/<id>/`, any EPSG code, scripts local with reasons in readme; FA-R108 on the roadmap.
- T1 2026-11-23: both Dataforsyningen WMS (`gl_satellitfoto`, `gl_aabent_land`) serve EPSG:3575; map stays polar at every zoom; layers recorded in PLAN design note 1. Token in owner's `.dev.env` (`FA_DATAFORSYNINGEN_TOKEN`).
- 2026-11-22: exploration (new and classic feature code), owner decisions (Leaflet polar, preview before save, scope incl. FA-R64, FA-R65 part, feature-page map, FA-R104; token in the page).

## Open questions

## Notes for the next session
- T4 open points for T5/T6: overlapping polygons in one feature are rejected (invalid MultiPolygon); swapped UTM easting/northing only gives the outside-Greenland warning (T6 may add a per-CRS plausibility check); `AddFeatureByMap.clean_geojson_data` raises TypeError (500) for non-numeric coordinates before the new check (fix in T5).
- For the roadmap at the end: `DeleteReportView._delete_publication_files` deletes appendix files without checking whether another FileObject/report uses them, and only unlinks the records (found in T9).
- Merge note: T8 will add smoke entries next to T9's in `test_smoke_urls.py` (small conflict expected).
- T3: check proj4 2.22.0 (was 2.9.2) in the browser. Proj4Leaflet is the unpatched 1.0.2: pass `bounds` as `L.bounds(...)`, not an array. `feature.html` lacks proj4/proj4leaflet/rotate scripts (T3 fixes). Source maps not vendored (devtools 404, harmless).
- For the roadmap at the end: Bootstrap 4.6.2 (jsdelivr) and jQuery 3.5.1/3.6.0/3.7.1 (code.jquery.com) still load from CDNs on most pages; serve locally as well (same reasons as T2).
- Owner is near the weekly usage cap and may switch accounts: keep this file current after every step; resume with skill `plan-work` (Resume).
- Add-by-map page in dev: OSM tiles blocked with 403 (tile usage policy), checked 2026-11-22. The overview map (EPSG:3575, GBIF) works.
- Old branches `develop/add_feature_by_map` and `origin/bug/add-feature-map/main` are fully merged into `develop/main` (no lost work).
- FA-R101 fix is on `agent-fixes` (348219a) and merged into `agent-features`; not yet on `develop/main`.
- The dev stack runs the owner's checkout (`find_artek_DEVELOP`), not the worktree. Browser checks of the branch (T3, T5, T11) need the dev stack built from the worktree, the owner put `.dev.env` there 2026-11-23 (never read or copy it).
- Check later (roadmap item at the end): 48 of 1746 existing geometries lie outside a rough Greenland box (lon -75..-10, lat 58..85); Svalbard/Canada or swapped lat/lon?
