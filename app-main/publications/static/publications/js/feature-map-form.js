// Add / edit a feature on the map (plan "features" T5): the shared map in edit mode
// (find-artek-map-edit.js) writes the drawing into the form's hidden geojson_data field.
// The other features of the report are shown for orientation (not editable); when editing,
// the feature itself is only in the edit layer.
document.addEventListener('DOMContentLoaded', function () {
    const element = document.getElementById('feature-map');
    if (!element) {
        return;
    }
    const findArtekMap = new FindArtekMap({element: element, mode: 'report', editable: true});
    const summary = document.getElementById('geometry-summary');

    function plural(count, word) {
        return count + ' ' + word + (count === 1 ? '' : 's');
    }

    function showSummary() {
        if (!summary) {
            return;
        }
        const counts = findArtekMap.editCounts();
        if (counts.points + counts.lines + counts.polygons === 0) {
            summary.textContent = 'Nothing drawn yet.';
        } else {
            summary.textContent = 'Drawn: ' + plural(counts.points, 'point') + ', ' +
                plural(counts.lines, 'line') + ', ' + plural(counts.polygons, 'polygon') + '.';
        }
    }

    findArtekMap.map.on('findartek:editchange', showSummary);
    showSummary();

    const form = element.closest('form');
    if (form) {
        form.addEventListener('submit', function () {
            findArtekMap.syncEditInput();
        });
    }

    if (findArtekMap.publicationId != null) {
        const editedId = parseInt(element.dataset.featureId, 10);
        FindArtekMap.fetchFeatures({publicationId: findArtekMap.publicationId})
            .then(function (records) {
                const others = records.filter(function (record) {
                    return record.feature_pk !== editedId;
                });
                const nothingDrawn = findArtekMap.editLayer &&
                    findArtekMap.editLayer.getLayers().length === 0;
                findArtekMap.addFeatures(others, {fit: nothingDrawn});
            })
            .catch(function (error) {
                console.error('Could not load the features of the report:', error);
            });
    }
});
