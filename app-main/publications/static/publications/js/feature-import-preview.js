// Excel import of features, preview map (plan "features" T10): the shared map component
// (find-artek-map.js) shows the features read from the sheet, before anything is saved. The
// page puts them as a GeoJSON FeatureCollection (WGS84) into a json_script element named by
// the map's data-geojson-source; colours by feature type as on the other maps.
document.addEventListener('DOMContentLoaded', function () {
    const element = document.getElementById('feature-import-map');
    if (!element) {
        return;
    }
    const source = document.getElementById(element.dataset.geojsonSource || '');
    let data = {type: 'FeatureCollection', features: []};
    if (source) {
        try {
            data = JSON.parse(source.textContent);
        } catch (error) {
            console.error('feature import preview: invalid GeoJSON', error);
        }
    }

    const findArtekMap = new FindArtekMap({element: element, mode: 'preview', syncUrl: false});

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    L.geoJSON(data, {
        pointToLayer: function (feature, latlng) {
            return L.circleMarker(latlng, {
                radius: 7, fillColor: FindArtekMap.colorForType(feature.properties.type),
                color: '#000', weight: 1, opacity: 1, fillOpacity: 0.8,
            });
        },
        style: function (feature) {
            return {color: FindArtekMap.colorForType(feature.properties.type), weight: 2,
                    opacity: 1};
        },
        onEachFeature: function (feature, layer) {
            const p = feature.properties || {};
            layer.bindPopup(
                '<b>Feature#:</b> ' + escapeHtml(p.feature_no) + '<br>' +
                '<b>Name:</b> ' + escapeHtml(p.name) + '<br>' +
                '<b>Type:</b> ' + escapeHtml(p.type) + '<br>' +
                '<b>Report:</b> ' + escapeHtml(p.report) +
                (p.warning ? '<br><i>Has a warning (see the list)</i>' : ''));
        },
    }).addTo(findArtekMap.featureLayer);
    findArtekMap.fitToFeatures();
});
