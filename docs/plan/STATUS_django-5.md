# Status: Django 5.2 LTS upgrade (Phase 3)

Plan: [PLAN_django-5.md](PLAN_django-5.md). Branch: `agent-django-5` (from `develop/main`; worktree `..\find_artek_agent-django-5`).

## Now
T3 (implementer): dependency upgrades still on Django 4.2.

## Done
- T1 2026-11-21: no RemovedInDjango50/51 warnings from our code; drf-yasg `SWAGGER_USE_COMPAT_RENDERERS = False`; `accounts/logout/` and custom `LogoutView` removed; 543 tests; gate 22/22; `check --deploy` allowed warnings today: `security.W004 security.W008` (`bc4cd51`)
- T2 2026-11-21: django-taggit, psycopg, PyPDF2, python-dotenv, ping3 (+ typing-extensions) removed from the lock, 37 pins, nothing else changed; 543 tests, gate 22/22 (`e9f5f77`)

## Open questions
- `DeleteFeatureView.delete()` (`views.py:~2012`) has been dead for form POSTs since Django 4.0 (`DeleteViewCustomDeleteWarning`): its file cleanup (delete each `FileObject` file + row) never runs. Moving it to `form_valid()` would start deleting media files and rows shared through `Feature.files` (M2M): a data decision. Left as is; proposed for the roadmap at Finish.

## Notes for the next session
- Third-party warnings (not fixed): pyasn1 `tagMap`/`typeMap`; pybtex `Person.first()/middle()/...` deprecated since 0.19, called from our code (`forms/person.py:97-101`, `utils_person.py`, `models.py:162-170`, `register_from_file.py:371`): candidate roadmap item.
- `python -W error::django.utils.deprecation.X` does not work (Python can't import the class at startup); use a `python -c` wrapper with `warnings.filterwarnings` (T1 report) for T4.
- Dev stack runs from the worktree: `docker compose -p find_artek_develop -f docker-compose.yml -f docker-compose.develop.yml`.
- Decided 2026-11-21: one release (`2026.6`); remove `accounts/logout/`; `check --deploy` = no errors, no new warnings (FA-R31 stays later).
- CAS login works in the dev stack (quick guide 01), so T8 checks it before tagging.
