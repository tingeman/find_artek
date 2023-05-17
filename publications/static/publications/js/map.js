function getURLParameters(url) {
  // Create a new URL object
  var urlObj = new URL(url);

  // Get the search parameters from the URL
  var params = new URLSearchParams(urlObj.search);

  // Create an empty object to store the parameters
  var paramsObj = {};

  // Iterate over each parameter and add it to the object
  for (let param of params) {
    paramsObj[param[0]] = param[1];
  }

  // Return the object with the parameters
  return paramsObj;
}


const createMap = (id, lat, lng, zoom) => {
  return L.map(id).setView([lat, lng], zoom);
};

const addTileLayer = (map, url, options) => {
  L.tileLayer(url, options).addTo(map);
};

const createPopupContent = (feature, featureReportsString) => {
  const newUrlFeatureName = new URL(`/publications/feature/${feature.feature_pk}`, window.location.href);
  return `<b>Name:</b> <a href=${newUrlFeatureName}>${feature.name}</a><br>
      <b>Type:</b> ${feature.type}<br>
      <b>Date:</b> ${feature.date}<br>
      <b>Reports:</b> ${featureReportsString}<br>`;
};

const createFeatureReportsString = (publications) => {
  return publications.map(pub => `<a href="/publications/report/${pub.pk}/">${pub.number}</a>`).join('');
};

const getColorByType = (type) => {
  const colors = {
    "PHOTO": "red",
    "SAMPLE": "green",
    "BOREHOLE": "yellow",
    "GEOPHYSICAL DATA": "blue",
    "FIELD MEASUREMENT": "purple",
    "LAB MEASUREMENT": "pink",
    "RESOURCE": "brown",
    "OTHER": "white"
  };
  return colors[type] || "white";
};

const addGeoJSONLayer = (geoJSONData, map, color, popupContent) => {
  if (!geoJSONData) return;

  const options = {
    pointToLayer: (feature, latlng) => {
      const marker = L.circleMarker(latlng, {
        radius: 8,
        fillColor: color,
        color: "#000",
        weight: 1,
        opacity: 1,
        fillOpacity: 0.8
      });
      marker.bindPopup(popupContent);
      return marker;
    }
  };

  L.geoJSON(JSON.parse(geoJSONData), options).addTo(map);
};

// Initialize map
// id: any, lat: any, lng: any, zoom: any

// q: how to get full url including parameters?
// a: window.location.href

var params = getURLParameters(window.location.href)
console.log(params);
var lat = params.lat;
var lng = params.lng;
var zoom = params.zoom;

// if lat lng or zsom are not defined, use default values
if (!lat || !lng || !zoom) {
  lat = 0;
  lng = 0;
  zoom = 3;
}

const map = createMap('map', lat, lng, zoom);
map.on('moveend zoomend', function () {
  var center = map.getCenter();
  var zoom = map.getZoom();

  // Update parameters
  var newParams = new URLSearchParams(window.location.search);
  newParams.set('lat', center.lat.toFixed(2));
  newParams.set('lng', center.lng.toFixed(2));
  newParams.set('zoom', zoom.toFixed(2));


  
  // Update the URL without reloading the page
  window.history.replaceState({}, '', '?' + newParams.toString());
});

addTileLayer(map, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 29,
  attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
});

// Add features to the map
featureData.forEach(feature => {
  const color = getColorByType(feature.type);
  const featureReportsString = createFeatureReportsString(feature.related_publications);
  const popupContent = createPopupContent(feature, featureReportsString);

  addGeoJSONLayer(feature.points, map, color, popupContent);
  addGeoJSONLayer(feature.lines, map, color, popupContent);
  addGeoJSONLayer(feature.polys, map, color, popupContent);
});
