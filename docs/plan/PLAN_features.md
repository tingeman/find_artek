# Plan: Feature registration

Status: **approved 2026-11-23**. Roadmap: FA-R61 (delete all features), FA-R62 (edit feature), FA-R63 (features from Excel), FA-R64 (files and images on features), FA-R65 (map type filter, legend, reports in view), FA-R104 (delete appendices), FA-R107 (feature form leftovers), FA-R13 (edit-feature TODO); needs FA-R101 (fixed on `agent-fixes`, 348219a). Branch: `agent-features` (from `develop/main`), worktree `..\find_artek_agent-features`. Ships with the next regular release; no fix release before it (owner 2026-11-22).

## Goal

1. Permitted users can register features of a report in three ways, as in the classic version: **digitize on a map** (points, lines, polygons), **coordinate entry** (a point in WGS84, UTM or GR96), and an **Excel sheet "Features"** with a preview before anything is saved.
2. Features can be **edited** (attributes and geometry) and **deleted**, one at a time or all features of a report.
3. **Files and images** can be uploaded to a feature and deleted again; report **appendices** can be deleted.
4. **One shared map component**: Leaflet in the polar projection EPSG:3575 on every map (overview, report, feature, digitize), with a layer switcher (map, Dataforsyningen satellite and topographic map) and scripts served from our own static files.
5. The overview map has a **feature-type filter, a legend and a list of the reports in view**.

## Current state

From the exploration 2026-11-22 (code on `agent-fixes`, = `develop/main` + FA-R101):

- **Model** `Feature` (`publications/models.py:587-694`): `name, type` (8 choices), `area, date` (NOT NULL in the DB), `direction, description, comment, pos_quality` (4 choices), `quality`; `points` (FA-R101 `MultiPointField`), `lines`, `polys` (all SRID 4326); M2M `publications`, `files`, `images` (through `ImageObjectship`), `URLs`. `is_editable_by` / `is_deletable_by` (`:657, :676`): `change_feature`/`delete_feature`, or `edit_own_feature`/`delete_own_feature` and listed on one of the feature's reports.
- **Permissions** (`permissions.py`): `ADD_FEATURE` = `add_feature` and report editable (`:124`); `DELETE_FEATURE`; no `EDIT_FEATURE`. Groups (`migrations/0003`): dtu_user add/edit_own/delete_own; artek_editor change/delete.
- **Views**: `AddFeatureCoordinatesView` (`views.py:1788`, one point, SRID free text, GDAL transform since FA-R101), `AddFeatureByMapView` (`views.py:1869`, points only, no `modified_by`), `DeleteFeatureView` (`views.py:2055`, deletes files, not images, redirects to the first report), `FeatureView` (`views.py:1313`, no edit/delete links). No edit view, no delete-all, no file/image upload for features.
- **Forms** (`forms/feature.py`): coordinate range "warnings" are `add_error` and block the save; `coordinate_warnings` is never set; dead `instance.geometry` path (`:338-368`, FA-R107).
- **Maps**:
  - `my-map-class.js`: EPSG:3575 (`L.Proj.CRS`, laea lat_0=90 lon_0=10), GBIF tiles `tile.gbif.org/3575/omt/...osm-light`, `rotate: true` + `setBearing(-54)` (leaflet-rotate 0.2.8); features from `/api/feature/` as GeoJSON strings; colours by type. Works on the overview map (checked in the browser 2026-11-22).
  - Scripts from CDNs: Leaflet 1.9.3/1.9.4 (unpkg, SRI), proj4 2.9.2 (cdnjs, no SRI), leaflet-rotate and leaflet-draw 1.0.4 (unpkg, no SRI), local `proj4leaflet.js`.
  - `add_feature_by_map.html`: inline script, Web Mercator, OSM tiles **blocked with 403** (tile usage policy, checked 2026-11-22), Esri satellite, leaflet-draw markers only, broken marker icon path, Cancel goes to the map.
  - `feature.html`: map cannot work (no proj4/rotate scripts, `new MyMapClass()` without div id).
  - `feature-map-selector.js`: not loaded anywhere (dead).
  - No legend or filter on `map.html`; hard-coded legend on `report.html:236-270`.
- **API** `FeatureSerializer` (`api/serializers.py:110-160`): geometry as GeoJSON strings, name, type, date, pk, visible reports; visibility from `publications/visibility.py:80-120` (unchanged by this plan).
- **Excel import of reports** (`register_from_file.py`): openpyxl, one transaction, problems per sheet and row, column aliases, Help sheet in the template; no preview. Commented-out port of the classic `xlsx_features` at `:400-718`. Administration page tile "Import features from Excel" is greyed out (`views_administration.py:51-73`).
- **Classic** (`find_artek_OLD`): choice page (online form / Excel / digitize); olwidget digitizing of points, lines and polygons with OSM and Google satellite; coordinate form with 8 SRIDs (32622, 4326, 3182, 32618-32621, 32623); Excel sheet `Features` with `Publication_ID, Feature#, Feature_type, Name, Geometry_type, SRID, UTMX/LON, UTMY/LAT, Pos_quality, Date, Description, Comment, Direction`, one row per vertex, rows with the same `Feature#` form a line or polygon; save, preview, "cancel" deletes (no transaction, no permission check on cancel); delete feature, delete all features of a report; file and image upload per feature.
- **Tests**: `test_feature_geometry.py`, `test_write_access.py:85-260`, `test_permissions_models.py:154-255`, `test_pages_visibility.py:166-206`, `api/test_feature_api_reports.py`, API snapshot and query-count tests, `test_media_access.py:245-249`.

## Design notes

**Owner decisions 2026-11-23:** keep the original coordinates, SRID and a GNSS observation date next to the WGS84 geometry (note 8); new feature uploads under the report folder (note 5); any EPSG code in coordinate entry, with a help list for Greenland; map scripts served locally, with the reasons in `readme.md`.

**Owner decisions 2026-11-22:** Leaflet in the polar projection; Excel import with preview before save; scope includes FA-R64, FA-R65 (filter, legend, reports in view), the feature-page map and FA-R104; Dataforsyningen token rendered into the page from an env variable; FA-R4: stay on MariaDB, transforms in Python.

1. **Shared map component** (`publications/static/publications/js/map/`, replacing `my-map-class.js` and the inline script of `add_feature_by_map.html`):
   - **Decided 2026-11-23 (T1):** both Dataforsyningen services list EPSG:3575 (also 3571-3576, 3182-3184, 3187, 32624, 3857, 4326, 4747), so the map stays in EPSG:3575 at every zoom, no Mercator mode. Layers: base `gl_satellitfoto` layer `ortofoto` (group: 10 m whole country, 1.6 m and 0.2 m regional), alternatives `sentinel2_10m_2022`; topographic `gl_aabent_land` layer `gl_aabent_land`; optional overlays `stednavne` (place names), `hoejdekurver_og_koter` (contours), `utm_net` (UTM grid, useful next to coordinate entry). GBIF OSM-light stays the default without a token.
   - CRS EPSG:3575 as today, bearing -54 for Greenland upright. Same component on map, report, feature and digitize pages; options for the div, the data source (`?publication_id=`, one feature) and edit mode.
   - **Base layers** in a layer switcher: GBIF OSM-light (default, no key); Dataforsyningen `gl_satellitfoto` and `gl_aabent_land` as `L.tileLayer.wms` **if their GetCapabilities lists EPSG:3575** (or another polar CRS we then switch to, e.g. EPSG:3413; T1 decides). If they don't, the satellite layer is shown only above a zoom threshold in a Web Mercator mode, or left out; T1 records the outcome and the main session decides with the owner before T3.
   - **Drawing** with leaflet-draw (markers, polylines, polygons; edit and delete of existing shapes). Risk: leaflet-draw with leaflet-rotate. If drawing on a rotated map misbehaves, edit mode uses bearing 0 (documented in the page help).
   - **Scripts served locally**: Leaflet, proj4, Proj4Leaflet, leaflet-rotate, leaflet-draw copied as release files into `static/publications/vendor/<lib>-<version>/` with their licence files, versions listed in `readme.md`. Removes the CDN dependencies without SRI. `versioned_static` for our own scripts; raise `STATIC_ASSET_VERSION`.
   - **Token**: new env variable `FA_DATAFORSYNINGEN_TOKEN` (default empty = no Dataforsyningen layers), passed to the template through a context processor or the map views, rendered into a `data-` attribute. It is visible in the page; Dataforsyningen tokens for web maps are meant for that. The token is not logged and not in any test fixture; tests use a dummy value.
2. **Geometry handling** in one module (`publications/geometry.py`): build MultiPoint / MultiLineString / MultiPolygon from GeoJSON (map) or vertex lists (Excel, coordinates), validate (ring closed or closed automatically, at least 2 points for a line and 3 for a polygon, coordinates in range after transform, Greenland bounding box as a warning only), transform to 4326 with GDAL. A feature may hold several geometry kinds; the map edit saves each kind into its column.
3. **Permissions**: new action `EDIT_FEATURE` = `Feature.is_editable_by` (existing rule: `change_feature`, or `edit_own_feature` and listed on one of the feature's reports). Add on a report = `ADD_FEATURE` (unchanged). Delete all features of a report = `ADD_FEATURE` on the report **and** `DELETE_FEATURE` on every feature in it; a feature linked to several reports is only unlinked from this report, not deleted. Excel import per report = `ADD_FEATURE` on that report; from the Administration page = `ADD_FEATURE` on every report named in the sheet (a row for a report the user may not edit is an error). File/image upload and delete on a feature = `EDIT_FEATURE`. Appendix delete = `Publication.is_editable_by` (FA-R104 note). **No change to who can see what**: feature, file and image visibility stay as in `visibility.py` and the media access view (FA-R30).
4. **Excel "Features" import with preview**:
   - Sheet `Features`, columns as classic with aliases (`Report` = report number such as `25-07`, accepted for `Publication_ID`; `UTMX/LON`/`X`, `UTMY/LAT`/`Y`), case-insensitive headers read by name (classic read them by position). One row per vertex; rows with the same `Feature#` form one feature; first row gives the attributes; `Geometry_type` point / line / polygon; several rows for a point feature make a MultiPoint (classic silently dropped them).
   - Step 1 upload → parse in memory (openpyxl) and check everything; step 2 preview page: map with all features, table with status per feature, problems by row; step 3 "Import" saves all in one transaction. Between steps the parsed result (attributes and WGS84 geometry as GeoJSON, report pks) is kept **in the session**, keyed by a random import id, with a size limit (e.g. 2000 vertices); the confirm step re-checks permissions and that the reports still exist. No uploaded file is kept on disk.
   - `date` is NOT NULL in the DB: the Excel `Date` column is required (as classic). No migration.
   - Template `static/publications/docs/ARTEK_feature_list.xlsx` with sheets `Features` and `Help`, linked from the import page.
5. **Files and images on features** (FA-R64): reuse the appendix upload code (`utils_models.py`, upload limit, submit guard); storage under `MEDIA_ROOT/reports/<year>/<number>/features/<feature id>/` (images in `img/` below it), with the report the upload starts from (owner 2026-11-23; existing feature files and images mostly sit directly in `reports/<year>/<number>/` and `.../img/`, from the original data load; classic uploads used `reports/<year>/features/<year>_<id>/` or `reports/features/<id>/`; 26 records have an empty path, for FA-R86); served through the existing media access view (X-Accel-Redirect), visible to whoever may view the feature. Image thumbnails as for report images. Deleting a feature also deletes its images (today only files).
6. **Migrations**: one migration in T4 that **adds nullable columns** to `publications_feature` (note 8); approved by the owner 2026-11-23. It does not touch existing rows: existing features get NULL (origin unknown; all 1746 existing geometries are plausible lon/lat values, checked 2026-11-23). No other schema change; anything else stops the task and the main session asks the owner.
8. **Original coordinates and epoch** (owner 2026-11-23): `points`/`lines`/`polys` stay the WGS84 copy for the maps and the API. New fields:
   - `source_srid` (integer, NULL): the EPSG code the coordinates were entered in.
   - `source_geometry` (text, NULL): WKT of all geometries of the feature in the original coordinates, exactly as entered (a GEOMETRYCOLLECTION when there are several kinds).
   - `transform_note` (text, blank): the PROJ transformation used for the WGS84 copy and its stated accuracy (e.g. `EPSG:3182 -> EPSG:4326, ballpark, ~1 m`), from the operation PROJ/GDAL chose where available.
   - `observation_date` (date, NULL): GNSS observation date, basis for epoch calculations. Stored NULL when not given; `Feature.epoch_date` returns `observation_date or date` (not copied, so it stays visible whether it was given).
   - Set by coordinate entry (T6) and the Excel import (T10, optional `Observation_date` column). A map edit (T5) of the geometry clears `source_srid`/`source_geometry`/`transform_note` and the page says "digitized on the map (WGS84)"; attribute-only edits keep them.
   - Shown on the feature page (original coordinates, SRID, observation date, transformation note). Added to the API feature detail only if T4 finds it useful; the list output and its snapshot stay unchanged.
   - GR96 (EPSG:4747 and GR96 / UTM): PROJ's transformation to WGS84 without a time-dependent model is approximate (about 1 m today). The WGS84 copy is for display; precise work uses the original coordinates with `epoch_date`. A later time-dependent transformation can recompute the WGS84 copy from the originals.
7. **What dtu_sus_web_server must change**: add `FA_DATAFORSYNINGEN_TOKEN` to `webapp_find_artek.env` (secret store) for the release. Nothing else: no new route outside `/find/`, no port, no path change. The functional checks for the release add: overview map with satellite layer, add a line feature, Excel preview.

## Assumptions

- Coordinate form keeps one point per submission (as classic; owner 2026-11-23: OK for now, better solution FA-R108). SRID: **any EPSG code PROJ knows** (owner 2026-11-23), with a help list for Greenland: WGS84 lon/lat (4326), GR96 lon/lat (4747), GR96 / UTM 18N-29N, WGS84 / UTM 18N-29N (32618-32629), Web Mercator (3857); exact EPSG numbers checked against PROJ in T6. Help text: UTM zone by longitude, GR96 vs WGS84 accuracy. Fields labelled "Easting / Longitude (x)" and "Northing / Latitude (y)".
- `observation_date` is optional in forms and the Excel sheet; no default is written (see note 8). Out-of-range values are warnings shown on a confirm step, not errors (fixes the blocking "warning").
- Edit by coordinates is offered for features that hold exactly one point; otherwise edit goes through the map.
- The add choice on the report page: three buttons ("Draw on map", "Enter coordinates", "Import from Excel"), no separate choice page.
- `feature-map-selector.js` and the leftover inline map script are deleted (FA-R107).
- After add/edit/delete the user returns to the report the action started from.
- The overview map's "reports in view" list uses the features already loaded in the browser (no new API endpoint); filter state lives in the URL like lat/lng/zoom.
- The API output format does not change (the API snapshot tests stay green). If the legend needs `pos_quality` or similar, it is added as a new field and the snapshot test is updated deliberately in that task.
- Dates in Excel: date cells or ISO text; anything else is an error (no fuzzy parsing).

## Tasks

### T0. Base and token (you + main session)
- **Main session, with your permission:** fast-forward `develop/main` to `agent-fixes` (FA-R101, 348219a), then `git branch -f agent-fixes develop/main`; create branch `agent-features` from `develop/main` with worktree `..\find_artek_agent-features`.
- **You:** create a free token on dataforsyningen.dk (self-service), add `FA_DATAFORSYNINGEN_TOKEN=<token>` to `.dev.env` in `C:\thin\02_Code\docker_projects\find_artek_DEVELOP`, and run the capabilities check in PowerShell (prints projections and layer names, not the token):
  ```powershell
  $env:DFS_TOKEN = Read-Host "Dataforsyningen token"
  foreach ($s in 'gl_satellitfoto','gl_aabent_land') {
    $x = [xml](Invoke-WebRequest -UseBasicParsing -Headers @{token=$env:DFS_TOKEN} "https://api.dataforsyningen.dk/wms/$s`?service=WMS&request=GetCapabilities&version=1.3.0").Content
    "== $s"; ($x.GetElementsByTagName('CRS') | % InnerText | sort -Unique) -join ' '
    ($x.GetElementsByTagName('Layer') | % { $_.Name } | ? { $_ }) -join ', '
  }
  ```
  Paste the output into the chat (no token).
- Acceptance: `agent-features` exists at `develop/main` incl. FA-R101; the projection list is recorded in STATUS.
- Deployment impact: none yet.

### T1. Map projection decision (main session)
- From T0's projection list: choose the CRS (EPSG:3575 if both Dataforsyningen layers offer it; else EPSG:3413 if offered and GBIF/another polar base layer exists for it; else 3575 with Dataforsyningen only in a zoomed-in Mercator mode or left out) and the layer names. Ask the owner if the result is not the first case.
- Acceptance: decision and layer names in STATUS and in this plan's design note 1.
- Agent: you (main session).

### T2. Vendor the map scripts and add the token setting
- Files: `static/publications/vendor/...` (Leaflet 1.9.4, proj4 2.x, Proj4Leaflet, leaflet-rotate, leaflet-draw 1.0.4, licences), `readme.md` (versions), `find_artek/settings.py` (`FA_DATAFORSYNINGEN_TOKEN = os.environ.get(..., '')`), context processor or view context, `.dev.env.example`, `ENVIRONMENT_SETUP.md`, templates that load map scripts (switch to local files).
- Acceptance: no map script from a CDN; `readme.md` gets a section "Third-party JavaScript" with the versions and **why the scripts are served locally** (no third-party code without integrity check in editors' sessions, reproducible releases, availability, visitors' IP addresses not sent to CDNs, simpler security headers later (FA-R31); cost: versions updated by hand, about 0.5 MB in the repository; tiles stay external); all map pages still render; the token is available to templates and empty by default; `tests/run.sh` image checks pass (settings change).
- Tests: setting default empty; the token is rendered only into map pages, only as a `data-` attribute; templates reference no `unpkg`/`cdnjs` URL (test over the template directory).
- Validation: skill validate (check, makemigrations --check, `publications` tests); `docker build` + `tests/run.sh` (settings change).
- Agent: implementer.
- Deployment impact: new env variable `FA_DATAFORSYNINGEN_TOKEN` for `webapp_find_artek.env` (empty is safe).

### T3. Shared map component
- Files: `static/publications/js/map/*.js` (new), `map.html`, `report.html`, `feature.html`, `frontpage.html`/`frontpage.js` (prefetch), remove `class/my-map-class.js` once nothing uses it.
- Acceptance: overview, report and feature pages show their features in the chosen polar CRS with the layer switcher (GBIF, and Dataforsyningen layers when the token is set); the feature-page map works; URL keeps lat/lng/zoom; no console errors.
- Tests: page tests that each map page includes the component and the right data attributes (feature pk, report pk); manual check in the browser (main session, screenshots in STATUS notes).
- Validation: skill validate, `publications` and `api` tests; browser check of the three pages.
- Agent: implementer.
- Deployment impact: none beyond T2.

### T4. Geometry module, edit permission and FA-R107
- Files: `publications/geometry.py` (new), `permissions.py` (`EDIT_FEATURE`), `forms/feature.py` (remove dead path), views using it, `models.py` (`Feature.source_srid`, `source_geometry`, `transform_note`, `observation_date`, `epoch_date`), migration (adds nullable columns only, design note 8), (showing the original coordinates on `feature.html` moved to T5, 2026-11-23).
- Acceptance: new fields and migration as design note 8 (existing rows untouched, `makemigrations --check` clean afterwards); GeoJSON → geometries per kind; vertex lists → point/line/polygon; transform to 4326; validation messages; `EDIT_FEATURE` mixin action.
- Tests: `epoch_date` with and without `observation_date`; existing features keep their geometry and get NULL in the new fields; unit tests for every geometry kind, closed/unclosed rings, too few vertices, SRIDs 4326/32622/3182, out-of-range; `EDIT_FEATURE` matrix (anonymous, dtu_user listed / not listed, artek_editor, superuser).
- Validation: skill validate, `publications` tests.
- Agent: implementer.

### T5. Digitize on the map: add and edit
- Files: `views.py` (`AddFeatureByMapView` → add/edit view pair or one view with optional pk), `forms/feature.py`, `add_feature_by_map.html` (→ `feature_map_form.html`), `feature.html` (edit/delete links), `report.html` (three add buttons).
- Acceptance: the feature page shows the original coordinates, SRID, observation date and transformation note (moved from T4); a geometry edit on the map clears `source_srid`/`source_geometry`/`transform_note`, an attribute-only edit keeps them; points, lines and polygons can be drawn, edited and deleted on the polar map; an existing feature loads its geometry for editing; `created_by` on add, `modified_by` always; Cancel returns to the report; only users with `ADD_FEATURE`/`EDIT_FEATURE` reach the views.
- Tests: add with each geometry kind and a mix, read back via raw `ST_AsText` (as `test_feature_geometry.py`); edit replaces geometry and attributes; access matrix for add and edit (anonymous → login, other DTU user → 403, listed user, editor); `modified_by` set.
- Validation: skill validate, `publications` tests; browser check (draw a line and a polygon in the dev stack, then delete the test feature).
- Agent: implementer.

### T6. Coordinate entry: SRID list, warnings, edit
- Files: `forms/feature.py`, `views.py` (`AddFeatureCoordinatesView` + edit), `add_feature_coordinates.html`.
- Acceptance: any EPSG code with the Greenland help list; `source_srid`, `source_geometry`, `transform_note` and `observation_date` stored; range problems shown as warnings on a confirm step, saving after confirmation; edit by coordinates for one-point features; `modified_by` set.
- Tests: each listed SRID transforms to the expected WGS84 point (fixed reference points); unknown EPSG is an error; out-of-range is a warning that can be confirmed; edit of a one-point feature; access matrix.
- Validation: skill validate, `publications` tests.
- Agent: implementer.

### T7. Delete: feature, all features of a report
- Files: `views.py` (`DeleteFeatureView` redirect, images; new `DeleteReportFeaturesView`), templates, `urls.py`.
- Acceptance: delete returns to the report it was started from; images and files of a deleted feature are removed (or moved aside as the appendix delete does, T9); delete-all removes the report's features and only unlinks features that belong to other reports too; confirm page lists what will go.
- Tests: delete with files and images; delete-all with a feature shared by two reports; permissions (user who may add but not delete a feature of another report: that feature is not deleted, page says so).
- Validation: skill validate, `publications` tests.
- Agent: implementer.

### T8. Files and images on features (FA-R64)
- Files: `views.py` (upload and delete views), `utils_models.py` (reuse), `feature.html`, `urls.py`, media access view if the path scheme needs it.
- Acceptance: users with `EDIT_FEATURE` upload files and images to a feature and delete them; files are served through the media access view to whoever may view the feature; thumbnails for images; upload limit and submit guard as for appendices.
- Tests: upload and delete (small fixture files only); anonymous and other-user access to upload/delete; media access for a feature file of a confidential report (hidden from anonymous); thumbnail created.
- Validation: skill validate, `publications` tests; `tests/run.sh` if the media path or cron thumbnail job changes.
- Agent: implementer.
- Deployment impact: none if files stay under `MEDIA_ROOT` (checked in the task).

### T9. Delete report appendices (FA-R104)
- Files: `views.py`, `report.html`, `urls.py`.
- Acceptance: delete button per appendix for users who may edit the report; confirmation; file removed from the share (FA-R86 has not decided "move aside", so remove, as the feature delete does).
- Tests: access (anonymous, other user, author, editor); file removed; report unchanged otherwise.
- Validation: skill validate, `publications` tests.
- Agent: implementer.

### T10. Excel "Features" import with preview (FA-R63)
- Files: `publications/register_features_from_file.py` (new; remove the commented-out classic port from `register_from_file.py`), `views.py` (upload, preview, confirm), templates, `static/publications/docs/ARTEK_feature_list.xlsx` (Features + Help), Administration tile enabled, report page button.
- Acceptance: as design notes 4 and 8 (`source_*` per feature from the row SRID; optional `Observation_date` column); nothing is saved before "Import"; a second import of the same sheet is detected (same report + name + geometry) and listed as a warning per feature; import from the report page fills the report itself and ignores/validates the report column.
- Tests: small `.xlsx` fixtures built in the test (openpyxl): points, a line, a polygon, mixed SRIDs, missing column, bad SRID, date missing, unknown report, report the user may not edit, preview → confirm saves, preview → cancel saves nothing, session expired, template headers match the parser.
- Validation: skill validate, `publications` tests.
- Agent: implementer.

### T11. Overview map: type filter, legend, reports in view (FA-R65 part)
- Files: map component (T3), `map.html`, `report.html` (legend from the component, not hard-coded).
- Acceptance: checkboxes per feature type (state in the URL), legend with the type colours, list of reports with features in the current view, updated on move/zoom.
- Tests: page test for the filter and legend markup; browser check.
- Validation: skill validate; browser check.
- Agent: implementer.

### T12. Release checks (you)
- **You**, in the dev stack after the main session rebuilt it (`docker compose -f docker-compose.yml -f docker-compose.develop.yml up -d --build`, from `C:\thin\02_Code\docker_projects\find_artek_DEVELOP` after the merge, or the worktree): draw a point, line and polygon; enter UTM coordinates; import the template sheet with your real examples; edit and delete; upload a feature image; delete an appendix; switch to the satellite layer; check the overview filter. Findings go into STATUS.
- Main session: full suite and `tests/run.sh` on the branch, merge `develop/main` into `agent-features`, ask for the fast-forward. The release itself (tag, build, deploy, `FA_DATAFORSYNINGEN_TOKEN` in web_server) follows the release procedure in a separate release plan with its USER_STEPS, as for 2026.7.

## Out of scope

- PostgreSQL/PostGIS (FA-R4 long-term goal).
- Other map projections per zoom level beyond what T1 decides; own tile server.
- Hashed static file names (FA-R103), list caching (FA-R102).
- Person management beyond merge (FA-R58), Excel import of reports changes (FA-R57, FA-R106).
- Danish translation and keyword list (rest of FA-R65).
- Changes to who can see features, files or reports.
