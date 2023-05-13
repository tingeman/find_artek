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
  const map = createMap('map', 66.9393, -53.6734, 13);
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
  