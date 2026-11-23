# User steps: Feature registration (browser checks, T12)

Plan: [PLAN_features.md](PLAN_features.md). Status: [STATUS_features.md](STATUS_features.md). Branch: `agent-features`.

This list checks T5–T11 in the dev stack. It is grouped by page, so related checks happen together:

- **Window A** is a normal browser window. Sign in once (CAS) and stay signed in.
- **Window B** is a private window (Edge: `Ctrl+Shift+N`; Chrome: `Ctrl+Shift+N`). It stays signed out the whole time.

You never have to sign out. All test data goes into one test report, which you delete at the end. Tick each box as you go. Write anything odd under **Findings** at the bottom, or tell the session.

---

## 0. Before you start (about 2 minutes)

The dev stack must run the branch code from the worktree. Check in PowerShell:

```powershell
cd C:\thin\02_Code\docker_projects\find_artek_agent-features
docker compose -f docker-compose.yml -f docker-compose.develop.yml ps
```

- [ ] `webapp-find-artek` is `Up` (healthy). If it isn't, run `docker compose -f docker-compose.yml -f docker-compose.develop.yml up -d --build` in the same folder.

Prepare three small files on your desktop. Any content will do:

- `test.dat`: a text file renamed to `.dat`.
- `test.xml`: e.g. `<data><v>1</v></data>`.
- `test.svg`: any SVG figure. Also put it in a zip as `test_svg.zip`: right-click, then "Compress to ZIP file".
- A photo `test.jpg`. A `.webp` file is optional.

---

## 1. Signed out (Window B, private), about 10 minutes

### 1.1 Overview map: http://localhost:8098/publications/map/

- [ ] The map opens on the **topographic** base layer, not Arctic SDI. A new private window has no stored choice.
- [ ] Next to the map there is a **type filter** with one checkbox and coloured swatch per type, plus **All / None** buttons.
- [ ] Untick two types. Those features disappear, and the URL gets `types=...`.
- [ ] Reload the page (`F5`). The same boxes are still unticked, and the map shows the same view.
- [ ] Copy the URL into a new private tab. You see the same filter and view.
- [ ] Look at **Reports in view**. Zoom into one area: the list gets shorter. Pan: it changes. Untick a type: reports that only have that type drop out.
- [ ] Click a report in the list. Its report page opens.
- [ ] The mouse wheel zooms this full-page map directly. That is intended here.
- [ ] Optional: make the window narrow. The side panel should move below the map.

### 1.2 Public report page: http://localhost:8098/publications/report/511/ (report 15-29)

- [ ] The **legend** below or next to the map has the same colours as the overview map's filter.
- [ ] Put the mouse over the map and turn the wheel. The **page scrolls**; the map does not zoom.
- [ ] Click once into the map, then turn the wheel. The **map zooms**. Move the mouse out of the map and turn the wheel. The page scrolls again.
- [ ] There are **no** buttons for Draw on map, Enter coordinates, Import from Excel or Delete all features (you are signed out).
- [ ] Open one of its features. The feature page shows **no** Edit on map, Edit coordinates, Delete or "Add files or images" buttons.

### 1.3 Delete page while signed out: http://localhost:8098/publications/feature/489/delete/

- [ ] You are sent to the **login** page; nothing is deleted. Don't log in here; close the tab.

Leave Window B open; you need it again in step 2.6.

---

## 2. Signed in (Window A), about 40 minutes

Sign in with CAS in Window A at http://localhost:8098/.

### 2.1 Create a test report

- [ ] Create a report through the normal "Add report" form (http://localhost:8098/publications/report/add/). Use the title **`ZZ test features (delete me)`**. Use a small PDF of your own if the form asks for one, and leave the report unvalidated.
- [ ] Write down its **page number (pk)** from the URL `/publications/report/<pk>/` and its **report number** (e.g. `26-xx`): pk ______, number ______

All steps below use this report. "The test report" means http://localhost:8098/publications/report/<pk>/.

### 2.2 Test report page: buttons

- [ ] The report page shows **Draw on map**, **Enter coordinates** and **Import from Excel**.
- [ ] **Delete all features** is not shown yet, because the report has no features.

### 2.3 Enter coordinates (T6)

Click **Enter coordinates** on the test report.

- [ ] The page has a help box: x is always easting/longitude, the UTM zone by longitude, GR96 vs WGS84. The EPSG field offers a list (4326, 4747, GR96/UTM 3178–3189, WGS84/UTM 32618–32629, 3857).
- [ ] **Unknown code:** EPSG `999999`, x `1`, y `1`, Save. You get an **error**, nothing is saved, and there is no confirm page.
- [ ] **Swapped UTM:** EPSG `32622`, x `7120000`, y `465000`, fill name, type, date and quality, Save. A **confirm page** with a warning appears. Click **Back to the form**. Your values are still there.
- [ ] **Good UTM point near Nuuk:** EPSG `32622`, x `465000`, y `7120000`, name `T6 UTM`, a date, **GNSS observation date** e.g. `2026-07-01`, Save. You get **no** confirm page and land on the test report with the new feature.
- [ ] **Outside Greenland:** Enter coordinates again, EPSG `4326`, x `12.5`, y `55.7` (Copenhagen), name `T6 outside`, Save. The **confirm page** shows the warning and the WGS84 point. Click **Save anyway**. You are back on the report with a "Saved with a warning" message.

### 2.4 Feature page of `T6 UTM`: edit, files, images (T6, T8, T8a)

Open the feature `T6 UTM` from the test report.

- [ ] The feature page shows the **original coordinates** (EPSG:32622, 465000 / 7120000), the **observation date** and a **transformation note**. The map shows the point near Nuuk.
- [ ] **Edit coordinates** is shown. Click it. The form is prefilled with EPSG 32622 and your x/y.
  - [ ] Change x to `466000` and save. The message says "saved with the new coordinates", and the point has moved a little.
  - [ ] Open Edit coordinates again, change **only the name** to `T6 UTM edited` and save. The message says "coordinates unchanged".
- [ ] Click **Add files or images**.
  - [ ] The page **lists the blocked file types** (html, svg, js, …) and says to put them in a **zip archive**. The image part names JPEG, PNG, GIF, TIFF and WebP.
  - [ ] Upload `test.svg` as a file. It is **refused**, and the message names the zip workaround.
  - [ ] Upload `test.dat`, `test.xml` and `test_svg.zip` as files. They are accepted.
  - [ ] Upload `test.jpg` (and `.webp` if you have one) as images. They are accepted.
- [ ] Back on the feature page, the files are listed and the images show a **thumbnail**.
- [ ] Click `test.xml`. The browser **downloads** it and does not show it.
- [ ] Click the image. It **opens in the browser**.
- [ ] Optional, DevTools (`F12`, Network tab, click `test.xml` again): the response headers have `Content-Disposition: attachment`, `Content-Type: application/octet-stream` and `X-Content-Type-Options: nosniff`.
- [ ] Right-click `test.xml`, choose **Copy link** and paste it here for step 2.6: ______
- [ ] Delete `test.dat` with its Delete button. The confirm page says it will be deleted. Confirm, and you are back on the feature page without it.

### 2.5 Draw on the map (T5 leftovers, T11 wheel)

From the test report, click **Draw on map**.

- [ ] The base layer is **topographic**. Over the map the wheel **scrolls the page** until you click into the map.
- [ ] Draw a **line** with 3 points and a **polygon**, name `T5 drawn`, Save. You are back on the test report.
- [ ] Open `T5 drawn` and click **Edit on map**:
  - [ ] **drag one vertex** of the line and save;
  - [ ] edit again, **delete the polygon** (trash tool) and save. The feature now holds only the line.
- [ ] On the feature page of `T5 drawn`, **Edit coordinates is not shown** (it is not a one-point feature). It isn't sent back to coordinates.
- [ ] **Base layer per tab:** switch the base layer to **Satellite** on this map, then open the test report's map. It is still Satellite in this tab. Open http://localhost:8098/publications/map/ in a **new tab**. It starts on **topographic**.

### 2.6 Back in Window B (signed out), 1 minute

- [ ] Open the test report URL. It is **not visible** to anonymous users (not found or not listed), because it is unvalidated.
- [ ] Open the `test.xml` link from 2.4. You get **not found**.

### 2.7 Excel import from the report page (T10)

On the test report, click **Import from Excel**.

- [ ] Click **Feature Excel template (ARTEK_feature_list.xlsx)** and save it. Open it in Excel: there are sheets **Features** (example point, line and polygon) and **Help**.
- [ ] In the Features sheet, **clear the Report column** (or replace `25-07` with your test report number) and save it as `test_import.xlsx`.
- [ ] Upload it. The **preview** shows a map with the 3 features, a status table, and an **Import** button. Nothing is saved yet: check the test report in another tab.
- [ ] Click **Import**. You are back on the test report with 3 new features.
- [ ] **Re-import:** Import from Excel again with the same file. The preview shows a **duplicate warning** for each feature. Click **Cancel**: nothing is added.
- [ ] **A bad sheet:** in `test_import.xlsx`, empty the **Date** cell of the first row and save as `test_bad.xlsx`. Upload it. The preview lists the **error with the row number**, and there is **no Import button**. Cancel.

### 2.8 Excel import from Administration (T10)

Go to http://localhost:8098/publications/administration/.

- [ ] The tile **Import features from Excel** is active (not greyed). Click it.
- [ ] Upload `test_import.xlsx` with the **Report column filled** with your test report number on every row. The preview shows the features and the duplicate warnings.
- [ ] Upload the same file with the Report column **empty** on one row. That row gets an **error** (the Report column is required here). Cancel.

### 2.9 Delete (T7, T7a)

- [ ] **Single delete:** on the test report, click Delete next to `T6 outside`. The confirm page lists the feature and its report. Confirm. You are **back on the test report**, and the feature is gone.
- [ ] **Feature on two reports (refused):** open http://localhost:8098/publications/feature/489/delete/ (feature "Oversigtsbillede", on reports 06-07 and 06-09; real data, read only). The page says it **belongs to more than one report and cannot be deleted** and has **no delete button**. Click Cancel. Don't change anything on this feature.
- [ ] **Delete all features:** on the test report, the **Delete all features** button is now shown. Click it. The confirm page lists every test feature under "to delete" (none under "unlink" or "kept"). Confirm. The test report has **no features** left, and the button is gone.

### 2.10 Clean up

- [ ] Delete the test report `ZZ test features (delete me)` with its delete function.
- [ ] Optional: delete the files from your desktop.

---

## Findings

Write one line per problem: step number, what you saw, and what you expected.

-

---

When everything is ticked, tell the session ("browser checks done"). It will then:

1. merge `develop/main` into `agent-features`;
2. run the full suite and `tests/run.sh`;
3. ask you for the fast-forward of `develop/main`.

The release (tag, build, deploy, and the token and nginx header in dtu_sus_web_server) follows in its own release plan.
