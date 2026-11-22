# Status: Feature registration

Plan: [PLAN_features.md](PLAN_features.md). Branch: `agent-features` (from `develop/main`, not created yet).

## Now
Plan draft written 2026-11-22, waiting for owner approval. Then T0: owner approves the fast-forward of `develop/main` to `agent-fixes` (FA-R101), creates the Dataforsyningen token and runs the capabilities check.

## Done
- 2026-11-22: exploration (new and classic feature code), owner decisions (Leaflet polar, preview before save, scope incl. FA-R64, FA-R65 part, feature-page map, FA-R104; token in the page).

## Open questions
- Which CRS do Dataforsyningen `gl_satellitfoto` and `gl_aabent_land` serve (T0/T1)?

## Notes for the next session
- Add-by-map page in dev: OSM tiles blocked with 403 (tile usage policy), checked 2026-11-22. The overview map (EPSG:3575, GBIF) works.
- Old branches `develop/add_feature_by_map` and `origin/bug/add-feature-map/main` are fully merged into `develop/main` (no lost work).
- FA-R101 fix is on `agent-fixes` (348219a), not yet on `develop/main`.
