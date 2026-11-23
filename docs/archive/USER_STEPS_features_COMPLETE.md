# User steps: Feature registration (browser checks, T12)

Plan: [PLAN_features_COMPLETE.md](PLAN_features_COMPLETE.md). Status: [STATUS_features_COMPLETE.md](STATUS_features_COMPLETE.md). Branch: `agent-features`.

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

- [x] The map opens on the **topographic** base layer, not Arctic SDI. A new private window has no stored choice.
    - ***All OK; Report list shows only 24 reports within all Greenland domain; Are there only 24 reports with features registered?***
- [x] Next to the map there is a **type filter** with one checkbox and coloured swatch per type, plus **All / None** buttons.
- [x] Untick two types. Those features disappear, and the URL gets `types=...`.
- [x] Reload the page (`F5`). The same boxes are still unticked, and the map shows the same view.
- [x] Copy the URL into a new private tab. You see the same filter and view.
- [x] Look at **Reports in view**. Zoom into one area: the list gets shorter. Pan: it changes. Untick a type: reports that only have that type drop out.
- [x] Click a report in the list. Its report page opens.
- [x] The mouse wheel zooms this full-page map directly. That is intended here.
- [x] Optional: make the window narrow. The side panel should move below the map.
  
***General comment: The report list should look like the regular reports list, and show both title and authors. We probably have to look at a different layout, maybe with the full-width reports list below the map. ***

***General comment: The Map view has a white background, and no border. Doesn't look nice on the grey background. Could we use maybe the Arctic Basemap below the other layers, to provide map coverage outside Geenland, also when other map products are loaded? ***


### 1.2 Public report page: http://localhost:8098/publications/report/511/ (report 15-29)

- [x] The **legend** below or next to the map has the same colours as the overview map's filter.
- [x] Put the mouse over the map and turn the wheel. The **page scrolls**; the map does not zoom.
- [x] Click once into the map, then turn the wheel. The **map zooms**. Move the mouse out of the map and turn the wheel. The page scrolls again.
- [x] There are **no** buttons for Draw on map, Enter coordinates, Import from Excel or Delete all features (you are signed out).
- [x] Open one of its features. The feature page shows **no** Edit on map, Edit coordinates, Delete or "Add files or images" buttons.
    - ***General comment: The Feature page layout is not good; It is like the map view takes up the entire column, So text fields are compressed. Consider different layouts***
  

### 1.3 Delete page while signed out: http://localhost:8098/publications/feature/489/delete/

- [x] You are sent to the **login** page; nothing is deleted. Don't log in here; close the tab.

Leave Window B open; you need it again in step 2.6.

---

## 2. Signed in (Window A), about 40 minutes

Sign in with CAS in Window A at http://localhost:8098/.

### 2.1 Create a test report

- [x] Create a report through the normal "Add report" form (http://localhost:8098/publications/report/add/). Use the title **`ZZ test features (delete me)`**. Use a small PDF of your own if the form asks for one, and leave the report unvalidated.
- [x] Write down its **page number (pk)** from the URL `/publications/report/<pk>/` and its **report number** (e.g. `26-xx`): pk ***568***, number ***26-06***

All steps below use this report. "The test report" means http://localhost:8098/publications/report/<pk>/.

### 2.2 Test report page: buttons

- [x] The report page shows **Draw on map**, **Enter coordinates** and **Import from Excel**.
- [x] **Delete all features** is not shown yet, because the report has no features.
  
### 2.3 Enter coordinates (T6)

Click **Enter coordinates** on the test report.

- [x] The page has a help box: x is always easting/longitude, the UTM zone by longitude, GR96 vs WGS84. The EPSG field offers a list (4326, 4747, GR96/UTM 3178–3189, WGS84/UTM 32618–32629, 3857).
    - ***The collapsed list of SRIDs for relevant reference systems easy to overlook. Could we give it the same light blue background as the help-text?***
- [x] **Unknown code:** EPSG `999999`, x `1`, y `1`, Save. You get an **error**, nothing is saved, and there is no confirm page.
- [x] **Swapped UTM:** EPSG `32622`, x `7120000`, y `465000`, fill name, type, date and quality, Save. A **confirm page** with a warning appears. Click **Back to the form**. Your values are still there.
- [x] **Good UTM point near Nuuk:** EPSG `32622`, x `465000`, y `7120000`, name `T6 UTM`, a date, **GNSS observation date** e.g. `2026-07-01`, Save. You get **no** confirm page and land on the test report with the new feature.
- [x] **Outside Greenland:** Enter coordinates again, EPSG `4326`, x `12.5`, y `55.7` (Copenhagen), name `T6 outside`, Save. The **confirm page** shows the warning and the WGS84 point. Click **Save anyway**. You are back on the report with a "Saved with a warning" message.
    - ***The background outside Greenland is white, features of type Other do not show, as they are also white! The feature does show, when I select the Arctic Basemap.***


### 2.4 Feature page of `T6 UTM`: edit, files, images (T6, T8, T8a)

Open the feature `T6 UTM` from the test report.

- [x] The feature page shows the **original coordinates** (EPSG:32622, 465000 / 7120000), the **observation date** and a **transformation note**. The map shows the point near Nuuk.
- [x] **Edit coordinates** is shown. Click it. The form is prefilled with EPSG 32622 and your x/y.
  - [x] Change x to `466000` and save. The message says "saved with the new coordinates", and the point has moved a little.
      - ***The return page is the report page, I would expect the Feature page, because that is where I came from***
  - [x] Open Edit coordinates again, change **only the name** to `T6 UTM edited` and save. The message says "coordinates unchanged".
- [x] Click **Add files or images**.
  - [x] The page **lists the blocked file types** (html, svg, js, …) and says to put them in a **zip archive**. The image part names JPEG, PNG, GIF, TIFF and WebP.
  - [x] Upload `test.svg` as a file. It is **refused**, and the message names the zip workaround.
  - [x] Upload `test.dat`, `test.xml` and `test_svg.zip` as files. They are accepted.
  - [x] Upload `test.jpg` (and `.webp` if you have one) as images. They are accepted.
  - ***Why are file and image uploads separate? Couldn't the code itself distinguish by type?***
  - ***Input accepts multiple files for upload, but only one description. That description is applied to all the files... We should consider a better way, or a way to edit once files are uploaded.***
  - ***The file input UI element doesn't look nice. It has a button in the input field, visual expression is not nice. Could we support drag&drop?***
- [x] Back on the feature page, the files are listed and the images show a **thumbnail**.
- [x] Click `test.xml`. The browser **downloads** it and does not show it.
- [x] Click the image. It **opens in the browser**.
- [x] Optional, DevTools (`F12`, Network tab, click `test.xml` again): the response headers have `Content-Disposition: attachment`, `Content-Type: application/octet-stream` and `X-Content-Type-Options: nosniff`.
- [x] Right-click `test.xml`, choose **Copy link** and paste it here for step 2.6: ***http://localhost:8098/find/media/reports/2026/26-06/features/1833/test.xml***
- [x] Delete `test.dat` with its Delete button. The confirm page says it will be deleted. Confirm, and you are back on the feature page without it.

### 2.5 Draw on the map (T5 leftovers, T11 wheel)

From the test report, click **Draw on map**.

- ***General comment: The feature information page should list the reports that a feature is related to.***

- [x] The base layer is **topographic**. Over the map the wheel **scrolls the page** until you click into the map.
- [x] Draw a **line** with 3 points and a **polygon**, name `T5 drawn`, Save. You are back on the test report.
- [x] Open `T5 drawn` and click **Edit on map**:
  - [x] **drag one vertex** of the line and save;
  - [ ] edit again, **delete the polygon** (trash tool) and save. The feature now holds only the line.
  - ***I find no way to mark only the polygon for deletion. I can only delete both features at the same time!***
- [x] On the feature page of `T5 drawn`, **Edit coordinates is not shown** (it is not a one-point feature). It isn't sent back to coordinates.
- [x] **Base layer per tab:** switch the base layer to **Satellite** on this map, then open the test report's map. It is still Satellite in this tab. Open http://localhost:8098/publications/map/ in a **new tab**. It starts on **topographic**.

### 2.6 Back in Window B (signed out), 1 minute

- [x] Open the test report URL. It is **not visible** to anonymous users (not found or not listed), because it is unvalidated.
- [x] Open the `test.xml` link from 2.4. You get **not found**.
    - ***I see Djangos "Page not found (404)" page***

### 2.7 Excel import from the report page (T10)

On the test report, click **Import from Excel**.

- [x] Click **Feature Excel template (ARTEK_feature_list.xlsx)** and save it. Open it in Excel: there are sheets **Features** (example point, line and polygon) and **Help**.
- [x] In the Features sheet, **clear the Report column** (or replace `25-07` with your test report number) and save it as `test_import.xlsx`.
- [x] Upload it. The **preview** shows a map with the 3 features, a status table, and an **Import** button. Nothing is saved yet: check the test report in another tab.
- [x] Click **Import**. You are back on the test report with 3 new features.
- [x] **Re-import:** Import from Excel again with the same file. The preview shows a **duplicate warning** for each feature. Click **Cancel**: nothing is added.
- [x] **A bad sheet:** in `test_import.xlsx`, empty the **Date** cell of the first row and save as `test_bad.xlsx`. Upload it. The preview lists the **error with the row number**, and there is **no Import button**. Cancel.

***General comment: The tables across the site have quite different visual expression. I like this feature table.***

### 2.8 Excel import from Administration (T10)

Go to http://localhost:8098/publications/administration/.

- [x] The tile **Import features from Excel** is active (not greyed). Click it.
- [x] Upload `test_import.xlsx` with the **Report column filled** with your test report number on every row. The preview shows the features and the duplicate warnings.
- [x] Upload the same file with the Report column **empty** on one row. That row gets an **error** (the Report column is required here). Cancel.

### 2.9 Delete (T7, T7a)

- [x] **Single delete:** on the test report, click Delete next to `T6 outside`. The confirm page lists the feature and its report. Confirm. You are **back on the test report**, and the feature is gone.
- [x] **Feature on two reports (refused):** open http://localhost:8098/publications/feature/489/delete/ (feature "Oversigtsbillede", on reports 06-07 and 06-09; real data, read only). The page says it **belongs to more than one report and cannot be deleted** and has **no delete button**. Click Cancel. Don't change anything on this feature.
  - ***The info box states that to delete the feature from a report, user has to delete "all features" from that report. That is not good, we may want to delete only that one feature from the report. So there should be a way to remove a feature from a report, even if it still belongs to another report. It just can't be fully deleted from the database.***
- [x] **Delete all features:** on the test report, the **Delete all features** button is now shown. Click it. The confirm page lists every test feature under "to delete" (none under "unlink" or "kept"). Confirm. The test report has **no features** left, and the button is gone.
  - ***The page should link to the feature pages, so that they can be inspected before deletion.***
  - ***Each feature should be listed with the number of files and images.***

### 2.10 Clean up

- [x] Delete the test report `ZZ test features (delete me)` with its delete function.
    - ***The test features are still present in the database, after deleting the report. I can see them when zooming on Nuuk. The delete confirmation page did not list them as something to be deleted. This needs handling. I suggest a report cannot be deleted, as long as features are associated with it. Features would have to be deleted first. If they belong to other reports too, they would have to be removed from the report to be delted, not necessarily deleted from the database.***
- [ ] Optional: delete the files from your desktop.

---

## Findings

Write one line per problem: step number, what you saw, and what you expected.

- ***See comments with findings in the text above. They are all enclosed in three aterix.***

### Summary (2026-11-23)

Checks run 2026-11-23 on test report pk 568 / 26-06. Everything ticked passed except 2.5 "delete the polygon". The proposed tasks (T13–T18) and the roadmap split are **waiting for the owner's confirmation**.

**Bugs: proposed fixes before the merge**

| Step | Finding | Checked in the dev DB | Proposed |
|---|---|---|---|
| 2.10 | Deleting the test report left its features in the database, without a report but visible on the map near Nuuk. The confirm page did not list them. | Orphans 1839 "Sample S1", 1840 "Profile P1", 1841 "Survey area A" (from the second Excel import). `DeleteReportView` only removes the links (old behaviour). 17 older orphans come from the production copy (e.g. 788, 850, 1125–1141). | T13: a report cannot be deleted while it has features; delete them or remove them from the report first. |
| 2.9 | On a feature that is on two reports, the info box points to "Delete all features". You may want to remove only that one feature from one report. | | T14: a "Remove from this report" action for shared features. The feature is still never fully deleted while another report uses it. |
| 2.5 | In Edit on map, you cannot delete only the polygon: the trash tool removes both geometries. | | T17: delete one geometry of a feature and keep the rest. |
| 1.1 | Reports in view lists only 24 reports at the all-Greenland view. | The API returns 1749 features on 161 public reports to signed-out users, so the list should be much longer. | T18: fix the reports-in-view calculation. |
| 2.3 | Outside Greenland the map background is white, so features of type Other (white) don't show. With the Arctic basemap they do. | | T16: give Other a visible colour; always lay the Arctic basemap underneath other layers; give the map a border (also 1.1: white map with no border on the grey page). |
| 2.4 | Edit coordinates returns to the report page, not to the feature page you came from. | | T15 |
| 2.4 | The feature page should list the reports the feature belongs to. | | T15: only the reports the user may see. |
| 2.9 | The "Delete all features" confirm page should link to each feature page and show its number of files and images. | | T15 |
| 2.3 | The collapsed EPSG list is easy to overlook. | | T15: same light blue background as the help text. |
| 2.4 | | Deleting files leaves empty folders (`reports/2026/26-06/features/1833/img/thumbs`); the files themselves were deleted. | T15: remove the empty folders. |

**Design and layout: proposed for the roadmap**

- **1.1, overview map:** the reports list should look like the regular reports list, with title and authors. It may need to sit full width below the map.
- **1.2, feature page:** the map takes up the whole column and squeezes the text fields. Consider another layout.
- **2.4, uploads:**
  - Why are file and image uploads separate? The code could tell them apart by type.
  - One description is applied to every file in a multi-file upload. Give each file its own description, or let descriptions be edited after the upload.
  - The file input looks poor; support drag & drop.
- **Tables:** tables across the site look very different. The feature table is the style to follow.
- **Data:** decide on the orphan features that already exist in production (see 2.10).

**No action needed**

- **2.6:** the xml link gives Django's "Page not found (404)" page. That is the dev debug page (`DEBUG=True`); production shows the normal 404 page. The file stays hidden either way, as intended.

---

## R. Recheck of the fixes T13–T18 (about 25 minutes)

The dev stack already runs the fixed code from the worktree. In both windows, reload each page once with `Ctrl+F5` (new script versions). Same two windows as before: **Window B** private and signed out, **Window A** signed in.

### R1. Signed out (Window B): overview map (T16, T18)

http://localhost:8098/publications/map/

- [x] **T18:** at the all-Greenland view, **Reports in view** lists about 140–160 reports, not 24.
- [x] **T18:** zoom into Ilulissat: the list shrinks to the reports there (mostly point features). Tick only **Borehole**: only reports with boreholes in view remain.
- [x] **T16:** the map has a thin grey **border** and a light blue-grey background where there are no tiles.
- [x] **T16:** choose **Topographic**, then zoom out until Canada/Iceland show. Outside Greenland you see the **Arctic basemap**, not white. Same with **Satellite**.
    - ***Arctic basemap shows in both situations. It works well with sattelite, but not so well with topographic. The topographic basemap seems to have a wide white border. Is it possible to make that white area transparent, so the Arctic basemap below shows?***
- [ ] **T16:** the colours: **Other** is teal, **Borehole** dark gold, **Lab measurement** deep pink. All are easy to see. Do you like them? 
    - ***They are all easy to see now, but I don't like especially the gold. Let us stick with the old colorscheme, but give each marker a black border. Also make the markers smaller, they are currently quite big.***

### R2. Signed in (Window A): two test reports

- [x] Create two reports with the normal "Add report" form: **`ZZ recheck A (delete me)`** and **`ZZ recheck B (delete me)`**, unvalidated. Note the pks: A ***569***, B ***570***

### R3. Report A: draw, coordinates, feature page (T15, T17)

- [x] On report A, **Draw on map**: a **polygon**, a **line inside the polygon**, and a **line outside it**. Name `R drawn`, Save.
- [x] Open `R drawn`, click **Edit on map**. Bin tool, click the **inner line**: only that line disappears. Toolbar **Save**, then **Save changes**. You land on the **feature page** (T15), which shows the polygon and the outer line.
- [x] **Edit on map** again. Bin tool, click the **polygon**: only the polygon goes. Save, Save changes: the outer line remains.
- [x] **Edit on map** again. Pencil tool: drag a vertex of the line. It moves. Save.
- [x] On report A, **Enter coordinates**: the EPSG list is in a **light blue box** (T15). Enter EPSG `32622`, x `465000`, y `7120000`, name **`R shared`**, Save.
- [x] Open `R shared`. The feature page lists **Report: <A number> …** (T15). Click **Edit coordinates**, change x to `466000`, Save: you are back on the **feature page**, not the report.
- [x] On `R shared`, **Add files or images**: upload `test.jpg`. Back on the feature page.

### R4. Make `R shared` belong to both reports (PowerShell)

The site has no button to put one feature on two reports, so link it in the dev database (test data only):

```powershell
cd C:\thin\02_Code\docker_projects\find_artek_agent-features
docker compose -f docker-compose.yml -f docker-compose.develop.yml exec -T webapp-find-artek python manage.py shell --settings find_artek.development_settings -c "from publications.models import Feature, Publication; f=Feature.objects.get(name='R shared'); f.publications.add(Publication.objects.get(title='ZZ recheck B (delete me)')); print(list(f.publications.values_list('title', flat=True)))"
```

- [x] It prints both report titles A and B.

### R5. Delete pages (T13, T14, T15)

- [x] **T13:** open report A's delete function. The page says the report **cannot be deleted yet**, shows **2 features**, offers **Delete all features** (link) and "one by one", lists `R drawn` and `R shared` with links, and has **no delete button**. Click Cancel.
    - ***When clicking delete report on the report page, a dialogue first appears asking if I am absolutely sure. This seems unnecessary, as there is a second page to review before the actual delete action. On the Delete Publication page, yes, it says the report cannot be deleted and explains why, but some of the text in the box is cropped (extends too far left, outside the box, but is cropped by the box). It is the two item numbers of the numbered list.***
- [x] **T14:** on report **B**, click Delete next to `R shared`. The page says it belongs to more than one report and cannot be deleted, and offers **Remove from report <B number>**. Click it. You are back on report B with "removed from report …; it stays on the other report(s)". `R shared` is gone from B.
- [x] Open `R shared` from report A: it still has its image, and the page lists only report A.
- [x] **T15:** on report A, **Delete all features**: each feature is a **link** and shows its files and images (`R shared`: "0 files, 1 image"). Confirm.
- [x] **T13:** report A's delete function now shows the normal delete page with the button. Delete report A, then report B.
    - ***The final delete action (pressing the button of the delete page) also shows the dialogue (are you absolutely sure?). This is fine, because this is the step where deleting actually happens. Could have the dialogue also when deleting all features etc. But only just before the actual delete action.***
- [x] Optional, **T13 bulk delete:** http://localhost:8098/publications/reports/bulk-delete/ — only if you know this page; a report with features is listed apart as "not deleted".
    - ***This page works well. Could be linked from the administration page, only for superusers.***


### R6. Findings of the recheck

-  See above, my comments are all enclosed in three asterix `***<comment>***`

---

## S. Second recheck: T19 and T20 (about 10 minutes)

The dev stack already runs this code. Reload each page once with `Ctrl+F5`.

### S1. Signed out (Window B): overview map (T19)

http://localhost:8098/publications/map/

- [x] Point markers are **smaller**, and every marker has a **black ring**. Other is **white**, Borehole **yellow**, Lab measurement **pink**.
- [x] The legend shows small circles with black rings; the white "Other" swatch is visible.
- [ ] Find a feature of type Other with a line or polygon: the white line has a thin **black edge**. Untick "Other": line and edge both disappear.
    - ***The lines are completely black, not just a black outline. But they do disappear when Other is unticked.***
- [x] Choose **Topographic** and zoom out: the white border around Greenland now shows the **Arctic basemap**.
- [ ] Zoom into a town with Topographic: does the map look **darker** than before, or show doubled coastlines or labels? ______ (If yes, the fix is a one-word CSS change to `darken`.)
    - ***At zoom levels where the arctic base map is visible in part of the map view (e.g. zoom=8), two coast lines are visible. When I zoom in further, the second (Arctic basemap) coastlines are no longer visible, but some place names and e.g. Airport markers (airplane pictogram) are visible in a fuzzy maner. They do originate from the Arctic Basemap, because they stay in the same place when I switch to that basemap as the chosen layer.***
- [x] Satellite and Sentinel-2 look as before.

### S2. Signed in (Window A): delete dialogs and Administration (T20)

Create one report **`ZZ recheck C (delete me)`** and draw one point on it, name `S point`.

- [x] On report C, click **Delete** (the report's delete action): **no dialog**; the delete page opens. The numbers **1** and **2** and the feature bullets sit **inside** the pink box. Click Cancel: no dialog.
- [x] Click **Delete** next to `S point`: no dialog. On its page, **Yes, delete feature** asks "Delete this feature? This cannot be undone." Click OK. Cancel on that page never asks.
- [x] Report C's delete page now has the button. **Delete Publication** asks "Delete this report? This cannot be undone." Click OK.
- [x] As **superuser**: http://localhost:8098/publications/administration/ shows a **Bulk delete reports** tile before "Django admin". Open it; select nothing and go back (don't delete real reports).
    - ***The tile should have an image. Use the same report background as in "Add report" but add a small overlay icon, which indicates deleting. Maybe a trash can? Or a red cross?***
- [ ] Optional: as a non-superuser editor, the tile is not shown.
    - I don't know, I don't have a non-superuser editor. How do I make one?

### S3. Findings

- See above, my comments are all enclosed in three asterix `***<comment>***`


---

## T. Third recheck: T21 and T22 (about 10 minutes)

The dev stack already runs this code. Reload each page once with `Ctrl+F5`.

### T1. Overview map, signed out (Window B)

http://localhost:8098/publications/map/

- [x] **T21:** find a feature of type **Other** with a line or polygon: the line is **white with a thin black edge** (not all black). Untick and tick "Other": still white.
- [x] **T22:** choose **Topographic**. The white border around Greenland is gone; about 12 km off the coast the **Arctic basemap** takes over.
- [x] **T22:** zoom to level 8–10 near Nuuk, Ilulissat and Tasiilaq: **no double coastlines, no ghost place names or airport icons** inside Greenland.
- [x] **T22:** pan and zoom (wheel and +/-): the edge stays aligned, no white flash.
- [ ] **T22:** look at **Scoresby Sund** (east coast): the wide fjord shows the Arctic basemap instead of the topographic map's water (known: the 12 km band can't fill fjords wider than ~24 km). Acceptable? ***No***
- [x] **T22:** **Box zoom:** under + and − there is a new button. Click it, drag a box: the map zooms to it and the button returns to normal. Click it and press `Esc`: cancelled. Shift+drag still works without the button.
    - ***Works as described. But it should not turn off when one zoom has been completed. It should stay on, until the user clicks the button again, or presses escape, or maybe (if possible) scrolls outside window or inside the window (which zooms by standard amounts).***
- [x] Satellite, then Arctic SDI, then Topographic, reload: the last choice is kept.

### T2. Signed in (Window A)

- [x] **T22:** open any report with features and a feature page: the box-zoom button is there. On **Draw on map** (add or edit) there is **no** box-zoom button.
- [x] **T21:** Administration: the **Bulk delete reports** tile shows the report picture with a **red trash can**. Don't delete anything.

### T3. Findings

- See above, my comments are all enclosed in three asterix `***<comment>***`


---

## U. Fourth recheck: T23 (about 10 minutes)

The dev stack already runs this code. Reload each page once with `Ctrl+F5`.

### U1. Overview map, signed out (Window B)

http://localhost:8098/publications/map/

- [x] Choose **Topographic**. Town names that run into the sea and small islands off the coast are **no longer cut off**; outside the topographic map's white border the **Arctic basemap** shows (blended).
    - ***Place names are all ok. There is still some minor coastline cutting, and by Hans Ø, the white is visible. But I think we will accept this current solution as good enough.***
- [x] Zoom 8-10 near Nuuk, Ilulissat and Tasiilaq: on land and in the fjords **no double coastlines, no ghost names or airport icons** from the Arctic basemap.
- [x] **Scoresby Sund**, **Disko Bay** and **Vaigat**: topographic water, no Arctic basemap coastlines.
- [x] Look along the whole coast at zoom 5-7 for **white patches** (sea inside the outline beyond the topographic map's blue band, e.g. in wide bays such as Melville Bugt). Note where: ***White band only shows up north-west of Hans Ø***
- [x] Off the coast, between the outline and the white edge, the sea is a little darker blue (blend). Acceptable? ***Yes***
- [x] Choose **Satellite**: unchanged from before (Arctic basemap outside Greenland).
- [x] **Box zoom:** click the button and drag several boxes one after another: it **stays on**. It turns off with a second click, with `Esc`, and with the mouse wheel over the map.

### U2. Findings

- Comments in `***<comment>***` as before.

---

When everything is ticked, tell the session ("browser checks done"). It will then:

1. merge `develop/main` into `agent-features`;
2. run the full suite and `tests/run.sh`;
3. ask you for the fast-forward of `develop/main`.

The release (tag, build, deploy, and the token and nginx header in dtu_sus_web_server) follows in its own release plan.
