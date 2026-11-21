# Status: Django 5.2 LTS upgrade (Phase 3)

Plan: [PLAN_django-5.md](PLAN_django-5_COMPLETE.md). Branch: `agent-django-5` (from `develop/main`; worktree `..\find_artek_agent-django-5`).

## Now
Done 2026-11-21: release `2026.6` deployed and checked. Plan closed; follow-ups in the roadmap (FA-R94 to FA-R96, additions to FA-R2, FA-R5, FA-R31, FA-R33).

## Done
- T1 2026-11-21: no RemovedInDjango50/51 warnings from our code; drf-yasg `SWAGGER_USE_COMPAT_RENDERERS = False`; `accounts/logout/` and custom `LogoutView` removed; 543 tests; gate 22/22; `check --deploy` allowed warnings today: `security.W004 security.W008` (`bc4cd51`)
- T2 2026-11-21: django-taggit, psycopg, PyPDF2, python-dotenv, ping3 (+ typing-extensions) removed from the lock, 37 pins, nothing else changed; 543 tests, gate 22/22 (`e9f5f77`)
- T3 2026-11-21: DRF 3.16.1, drf-yasg 1.21.18 (+ swagger-spec-validator/jsonschema stack), django-cas-ng 5.1.2, python-cas 1.7.2, django-select2 8.4.8; `find_artek/cas_views.py`: off-site `?next=` at CAS login gives 400 (cas-ng 5.1 now checks it; was an open redirect in 5.0.1); 561 tests, gate 22/22 (`0feb880`)
- T4 2026-11-21: Django 5.2.19, DRF 3.18.3, no code breakage; `SWAGGER_SETTINGS['LOGOUT_URL'] = 'cas_ng_logout'`; no RemovedInDjango60/61 warnings; no migrations; DB, tables and columns all utf8mb4_general_ci; 563 tests, coverage 71.1 %, gate 22/22; new `check --deploy` warning `gis.W001` (GDAL 3.6 < 3.9) -> T5 moves to trixie (`189a7c1`)
- T5 2026-11-21: `python:3.13.18-slim-trixie` by digest (GDAL 3.10.3, GEOS 3.13.1, PROJ 9.6, poppler 25.03, libmariadb 11.8); no apt or lock version changes; `gis.W001` gone; prod image 881 -> 927 MB; 563 tests, gate 22/22 (`d3abad3`)
- T6 2026-11-21: `tests/run.sh` `DEPLOY_WARNINGS_ALLOWED="security.W004 security.W008"`; a new ID fails, a vanished one is shown as INFO; test name now "... has no errors and only allowed warnings"; gate 22/22 (`d0088f1`)
- T7 2026-11-21: CLAUDE.md (Django 5.2; `/find/media/` goes to Django since 2026.4), readme (Django bound, release notes 2026.6) (`1105aeb`)
- T8 fix 2026-11-21: dev test found that a typed "thin" (initials) got no match in the disambiguation step: `get_person_matches` only compared a single word with `id_number`. Now also `initials` (iexact, from 2 characters, confidence 0.9 like id_number). Never on develop/main before (only on the disambiguation branches); 569 tests, gate 22/22 (`2315198`)
- T8 2026-11-21: your dev checks pass. CAS logout ends on DTU's logout page; the redirect (`https://auth2.dtu.dk/dtu/logout?url=<front page>`) is identical with django-cas-ng 5.0.1/python-cas 1.6 and 5.1.2/1.7.2, so not an upgrade change; DTU's CAS ignores `url` (CAS v2). Roadmap candidate with FA-R33 (CAS 3 would send `service`, and adds single logout).

## Done (release)
- T9 2026-11-21: `develop/main` fast-forwarded to `d7aef5d`, tag `2026.6`, built by `build_image.sh` (22/22, 569 tests), published, web_server `releases.yml` (`0b4d515`); deployed by you, production checks pass (thumbnail cron check pending).

## Open questions
- `DeleteFeatureView.delete()` (`views.py:~2012`) has been dead for form POSTs since Django 4.0 (`DeleteViewCustomDeleteWarning`): its file cleanup (delete each `FileObject` file + row) never runs. Moving it to `form_valid()` would start deleting media files and rows shared through `Feature.files` (M2M): a data decision. Left as is; proposed for the roadmap at Finish.

## Notes for the next session
- Swagger UI logout button posts to drf-yasg's default `/accounts/logout/` (404, already before T3): T4 sets `SWAGGER_SETTINGS['LOGOUT_URL']` to the CAS logout.
- CAS v2 has no single logout (logging out at the CAS server leaves the find_artek session): unchanged, roadmap candidate (FA-R33).
- Third-party warnings (not fixed): pyasn1 `tagMap`/`typeMap`; pybtex `Person.first()/middle()/...` deprecated since 0.19, called from our code (`forms/person.py:97-101`, `utils_person.py`, `models.py:162-170`, `register_from_file.py:371`): candidate roadmap item.
- `python -W error::django.utils.deprecation.X` does not work (Python can't import the class at startup); use a `python -c` wrapper with `warnings.filterwarnings` (T1 report) for T4.
- Dev stack runs from the worktree: `docker compose -p find_artek_develop -f docker-compose.yml -f docker-compose.develop.yml`.
- Decided 2026-11-21: one release (`2026.6`); remove `accounts/logout/`; `check --deploy` = no errors, no new warnings (FA-R31 stays later).
- CAS login works in the dev stack (quick guide 01), so T8 checks it before tagging.
