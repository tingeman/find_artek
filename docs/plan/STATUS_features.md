# Status: Feature registration

Plan: [PLAN_features.md](PLAN_features.md). Branch: `agent-features` (from `develop/main`), worktree `..\find_artek_agent-features`.

## Now
Plan approved 2026-11-23. T2 (implementer): vendor map scripts, token setting, readme section.

## Done
- T0 2026-11-23: `agent-features` created from `develop/main` with worktree; `agent-fixes` (FA-R101, 348219a) merged into it instead of a fast-forward of `develop/main` (FA-R101 reaches `develop/main` with the feature merge). Owner put the token into `.dev.env`.
- 2026-11-23: owner decisions: original coordinates + `observation_date` (migration adding nullable columns approved), upload path `reports/<year>/<number>/features/<id>/`, any EPSG code, scripts local with reasons in readme; FA-R108 on the roadmap.
- T1 2026-11-23: both Dataforsyningen WMS (`gl_satellitfoto`, `gl_aabent_land`) serve EPSG:3575; map stays polar at every zoom; layers recorded in PLAN design note 1. Token in owner's `.dev.env` (`FA_DATAFORSYNINGEN_TOKEN`).
- 2026-11-22: exploration (new and classic feature code), owner decisions (Leaflet polar, preview before save, scope incl. FA-R64, FA-R65 part, feature-page map, FA-R104; token in the page).

## Open questions

## Notes for the next session
- Add-by-map page in dev: OSM tiles blocked with 403 (tile usage policy), checked 2026-11-22. The overview map (EPSG:3575, GBIF) works.
- Old branches `develop/add_feature_by_map` and `origin/bug/add-feature-map/main` are fully merged into `develop/main` (no lost work).
- FA-R101 fix is on `agent-fixes` (348219a) and merged into `agent-features`; not yet on `develop/main`.
- The dev stack runs the owner's checkout (`find_artek_DEVELOP`), not the worktree. Browser checks of the branch (T3, T5, T11) need the dev stack built from the worktree, which has no `.dev.env` (secret, not copied by agents): ask the owner how to run it before T3.
- Check later (roadmap item at the end): 48 of 1746 existing geometries lie outside a rough Greenland box (lon -75..-10, lat 58..85); Svalbard/Canada or swapped lat/lon?
