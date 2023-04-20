
var map = L.map('map').setView([66.9393, -53.6734], 13);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 29,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

// Function to add GeoJSON data to the map
function addGeoJSONLayer(geoJSONData, map, color, popupContent) {




    if (geoJSONData) {
        var options = {
            pointToLayer: function (feature, latlng) {
                var marker =  L.circleMarker(latlng, {
                    radius: 8,
                    fillColor: color,
                    color: "#000",
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                });

                // Bind a multiline popup to the marker
                marker.bindPopup(popupContent);

                return marker;
            }
        };

        var geoJSONLayer = L.geoJSON(JSON.parse(geoJSONData), options);
        geoJSONLayer.addTo(map);
    }
}

// Iterate through the feature data and add points, lines, and polys to the map
for (var i = 0; i < featureData.length; i++) {
    var feature = featureData[i];
    var type = feature.type;

    // console.log(feature.related_publications)

    // featureURL = new 

    // ------------ Create URL for feature name ------------ //
    const currentUrl = new URL(window.location.href);

    const protocol = currentUrl.protocol;
    const hostname = currentUrl.hostname;
    const port = currentUrl.port;

    const newPath = "/publications/feature/";
    const featureId = feature.feature_pk;

    const newUrlFeatureName = new URL(`${protocol}//${hostname}${port ? ':' + port : ''}${newPath}${featureId}/`);
    // console.log(newUrlFeatureName.toString())
    // ------------ Create URL for feature name ------------ //



    var featureReportsString = "";


    for (var j = 0; j < feature.related_publications.length; j++) {

        console.log(feature.related_publications[j].pk)
        console.log(feature.related_publications[j].number)
        featureReportsString += `<a href="/publications/publication/${feature.related_publications[j].pk}/">${feature.related_publications[j].number}</a>`;

    }


    var popupContent = "<b>Name:</b> " + `<a href=${newUrlFeatureName.toString()}>${feature.name}</a>` + "<br>" +
    "<b>Type:</b> " + feature.type + "<br>" +
    "<b>Date:</b> " + feature.date + "<br>" +
    "<b>Reports:</b> " + featureReportsString + "<br>";


    // Set the color of the point based on the type
    var color = "white";
    switch (type) {
        case "PHOTO":
            color = "red";
            break;
        case "SAMPLE":
            color = "green"
            break;
        case "BOREHOLE":
            color = "yellow"
            break;
        case "GEOPHYSICAL DATA":
            color = "blue"
            break;
        case "FIELD MEASUREMENT":
            color = "purple"
            break;
        case "LAB MEASUREMENT":
            color = "pink"
            break;
        case "RESOURCE":
            color = "brown"
            break;
        case "OTHER":
            color = "white"
            break;
        default:
            break;
    }




    addGeoJSONLayer(feature.points, map, color, popupContent);
    addGeoJSONLayer(feature.lines, map, color, popupContent);
    addGeoJSONLayer(feature.polys, map, color, popupContent);
}
