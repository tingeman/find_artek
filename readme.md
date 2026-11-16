# Tests

`tests/run.sh` tests a built image. From the repository root (Git Bash on Windows, WSL or Linux, with Docker):

```bash
docker build -t find_artek:local .                       # builds the last stage, prod
bash tests/run.sh find_artek:local                       # everything (~40-55 s)
bash tests/run.sh --quick find_artek:local               # image checks only, no database (~10 s)
TEST_FILTER='^smoke' bash tests/run.sh find_artek:local  # tests whose name matches (grep -E)
```

- **image:** user `dockeruser` (uid/gid 30000), `WORKDIR /app`, the entrypoint, gunicorn on `0.0.0.0:8099` without `--reload`, a `HEALTHCHECK`, `pip check`, the key packages import (GDAL, GEOS), no compilers or admin tools, the thumbnail cron file, the `Dockerfile`'s `ARG PYTHON_IMAGE` equals `FA_PYTHON_IMAGE` in `compose.pins.env` (by digest), stages `runtime`, `dev`, `prod` with `prod` last.
- **smoke:** a throwaway MariaDB on an `--internal` network with generated credentials; `migrate --skip-checks` (FA-R14), `check`, `check --deploy` (warnings reported, not failed), `makemigrations --check`, all with the production settings; the image's own command becomes healthy and answers 200 on `/publications/frontpage/`; with `ENABLE_CRON=true` the cron daemon runs and the thumbnail job, run as cron runs it, succeeds and logs to `docker logs`; no log contains the generated secrets.
- **django:** `manage.py test` with the labels in `DJANGO_TEST_LABELS` at the top of the script. Empty in 2026.1 (no test passes at baseline), so it prints `SKIP: django: ...`; Phase 2 fills it.

Each test prints `PASS:`/`FAIL:`; the last line is `ALL <n> TESTS PASSED` (exit 0) or `<m> OF <n> TESTS FAILED` (exit 1). All containers, the network and the temporary directory are removed at the end, also on failure. The release build (`scripts/build_image.sh` in dtu_sus_web_server) runs `bash tests/run.sh <image>` in the checkout of the release tag and publishes nothing unless it exits 0.

# TODO list

### To do...

***URGENT***
- [] In production, add/edit report form does not properly handle new persons not already in database
- [] In production, add/edit report form fails during upload of pdf report.

***Not urgent***
- [] MAJOR: change to postgresql/postgis backend! (to allow handling of coordinate transformations)
- [] MAJOR: implement unit testing
- [] The add feature button is shown also when not logged in, at least in production. Check/fix
- [] remove pop-ups for user acknowledgements when separate views also ask for akcnowledgement.
       Or move popups to acknowledgement view instead of happening from report view.
- [] implement edit feature view/form
- [] check data in database against old find-artek
- [] check model setup against old find-artek
- [] clean up code (remove commented code, newlines etc) [started]


### Completed
- [x] caching causes problems when new features are added (and possibly reports added). Using context 
        variable to trigger invalidation of report feature session cache. The template then injects
        js to clear the relevant session cache key.
- [x] implement feature view
- [x] implement links to edit and delete publication        
- [x] implemented appendices upload
- [x] implemented report pdf upload
- [x] fix map view on report page (and limit features to those from the report)
- [x] fix author links, etc...
- [x] implement simple search from front page
- [x] implement individual person view
- [x] Fix null issue for person list!
- [x] implement persons api
- [x] implement persons view (list of all persons)
- [x] Ensure confidential and unvalidate entries are filtered out! (This happens in the api serializer)






### Other notes:

```python
import 
ldap_server = 'ldaps://win.dtu.dk'     # Your LDAP server address
user = 'BYG-Artek_AD_Read'             # Your AD read-only username
password = 'xxxxxxxxxxxxxxxxxxx'       # Replace with your AD password
search_base = 'dc=win,dc=dtu,dc=dk'    # Base DN for your domain
```

```python
search_filter = '(&(givenName=Thomas)(sn=I*))'
```

```python
# Connect to the LDAP server
try:
    # Set up the server with secure connection and detailed logging
    server = Server(ldap_server, get_info=ALL, use_ssl=True)
    conn = Connection(server, user=user, password=password, auto_bind=True)
    # Perform the search
    conn.search(
        search_base=search_base,
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes=['*']  # Retrieve all attributes
    )
    # Process the results
    if conn.entries:
        for entry in conn.entries:
            print(entry.displayName)  # Print all details about the found entry
    else:
        print("No entries found .")
    # Unbind the connection
    conn.unbind()
except Exception as e:
    print(f"An error occurred: {e}")
```
