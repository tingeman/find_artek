// Overview map: every feature the user may see (plan "features" T3, FindArtekMap), with the
// feature type filter and the list of reports in view (T11).
//
// Type filter: the checkboxes of #feature-type-filter (rendered by the server from ?types=,
// publications/map_styles.py). A change shows/hides the types on the map and writes
// `types=<slug>,...` into the page URL next to lat/lng/zoom (no parameter when every type is
// checked), so a reload or a shared link keeps the filter.
//
// Reports in view: the reports of the features shown (type filter) whose bounding box
// overlaps the current view, from the features already loaded (the API's
// related_publications: only reports the user may see). Updated after move/zoom (debounced)
// and after a filter change.
document.addEventListener('DOMContentLoaded', function () {
    const element = document.getElementById('map');
    if (!element) {
        return;
    }
    const overlay = document.getElementById('loading-overlay');
    const filter = document.getElementById('feature-type-filter');
    const summary = document.getElementById('reports-in-view-summary');
    const list = document.getElementById('reports-in-view-list');
    const section = document.getElementById('reports-in-view');
    const maxItems = parseInt(section && section.dataset.maxItems, 10) || 200;
    const UPDATE_DELAY_MS = 250;

    const findArtekMap = new FindArtekMap({element: element, mode: 'overview'});
    let loaded = false;
    let timer = null;

    function checkboxes() {
        return filter ? Array.from(filter.querySelectorAll('input[type="checkbox"]')) : [];
    }

    // null when every type is checked (no filter), otherwise the checked Feature.type values.
    function checkedTypes() {
        const boxes = checkboxes();
        const checked = boxes.filter(function (box) { return box.checked; });
        if (checked.length === boxes.length) {
            return null;
        }
        return checked.map(function (box) { return box.dataset.type; });
    }

    function writeTypesToUrl() {
        if (!filter) {
            return;
        }
        const param = filter.dataset.param || 'types';
        const boxes = checkboxes();
        const slugs = boxes.filter(function (box) { return box.checked; })
            .map(function (box) { return box.value; });
        const params = new URLSearchParams(window.location.search);
        if (slugs.length === boxes.length) {
            params.delete(param);
        } else {
            params.set(param, slugs.join(','));
        }
        const query = params.toString();
        window.history.replaceState(window.history.state, '',
            window.location.pathname + (query ? '?' + query : '') + window.location.hash);
    }

    function plural(count, word) {
        return count + ' ' + word + (count === 1 ? '' : 's');
    }

    // [{id, number, title, count}] of the reports of the features in view, by report number.
    function reportsInView() {
        const reports = new Map();
        findArtekMap.recordsInView().forEach(function (record) {
            (record.related_publications || []).forEach(function (pub) {
                const entry = reports.get(pub.id) ||
                    {id: pub.id, number: pub.number, title: pub.title, count: 0};
                entry.count += 1;
                reports.set(pub.id, entry);
            });
        });
        return Array.from(reports.values()).sort(function (a, b) {
            return String(a.number || '').localeCompare(String(b.number || ''), undefined,
                {numeric: true});
        });
    }

    function showReports() {
        if (!list || !summary || !loaded) {
            return;
        }
        const reports = reportsInView();
        list.replaceChildren();
        reports.slice(0, maxItems).forEach(function (report) {
            const item = document.createElement('li');
            const link = document.createElement('a');
            link.href = FindArtekMap.reportUrl(report.id);
            link.textContent = report.number || ('Report ' + report.id);
            item.appendChild(link);
            const count = document.createElement('span');
            count.className = 'map-report-count';
            count.textContent = ' (' + plural(report.count, 'feature') + ')';
            item.appendChild(count);
            if (report.title) {
                const title = document.createElement('span');
                title.className = 'map-report-title';
                title.textContent = report.title;
                item.appendChild(title);
            }
            list.appendChild(item);
        });
        if (reports.length === 0) {
            summary.textContent = 'No report has features in this view.';
        } else if (reports.length > maxItems) {
            summary.textContent = plural(reports.length, 'report') + ' in this view; the first ' +
                maxItems + ' are listed. Zoom in to see the others.';
        } else {
            summary.textContent = plural(reports.length, 'report') + ' in this view.';
        }
    }

    function scheduleShowReports() {
        window.clearTimeout(timer);
        timer = window.setTimeout(showReports, UPDATE_DELAY_MS);
    }

    function applyFilter() {
        findArtekMap.setTypeFilter(checkedTypes());
        showReports();
    }

    if (filter) {
        filter.addEventListener('change', function () {
            applyFilter();
            writeTypesToUrl();
        });
        filter.querySelectorAll('button[data-select]').forEach(function (button) {
            button.addEventListener('click', function () {
                const on = button.dataset.select === 'all';
                checkboxes().forEach(function (box) { box.checked = on; });
                applyFilter();
                writeTypesToUrl();
            });
        });
    }
    // The checkboxes start as the server rendered them from ?types=.
    findArtekMap.setTypeFilter(checkedTypes());
    findArtekMap.map.on('moveend', scheduleShowReports);

    if (overlay) {
        overlay.style.display = 'flex';
    }
    findArtekMap.loadFeatures()
        .then(function () {
            loaded = true;
            showReports();
        })
        .catch(function (error) {
            console.error('Could not load the features:', error);
            if (summary) {
                summary.textContent = 'The features could not be loaded.';
            }
        })
        .finally(function () {
            if (overlay) {
                overlay.style.display = 'none';
            }
        });
});
