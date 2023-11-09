class MyMapClass {
  constructor() { }

  initialize() {
    return new Promise((resolve, reject) => {



      try {
        // if featureData is not null, use it to set the map center and zoom
        var params = this.#_getURLParameters(window.location.href);
        var lat = params.lat;
        var lng = params.lng;
        var zoom = params.zoom;

        // if lat, lng or zoom are not defined, use default values
        if (!lat || !lng || !zoom) {
          lat = 74.86;
          lng = -44.60;
          zoom = 4.00;
        }

        const map = this.#_createMap('map', lat, lng, zoom);
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

        this.#_addTileLayer(map, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 29,
          attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        });

        // Resolve the promise with the map object
        resolve(map);
      } catch (error) {
        reject(error);
      }
    });
  }

  addFeatureDataToMap(map, featureData, relocate = false) {
    // if featureData not null, add a geojson layer to the map
    if (featureData) {
      const allFeatures = {
        type: "FeatureCollection",
        features: []
      };
  
      featureData.forEach(feature => {
        const color = this.#_getColorByType(feature.type);

        // Create popop data
        const featureReportsString = this.#_createFeatureReportsString(feature.related_publications);


        const popupContent = this.#_createPopupContent(feature, featureReportsString);
  
        this.#_addGeoJSONLayer(feature.points, map, color, popupContent);
        this.#_addGeoJSONLayer(feature.lines, map, color, popupContent);
        this.#_addGeoJSONLayer(feature.polys, map, color, popupContent);
  
        // add points, lines, and polys to allFeatures
        if (feature.points) {
          allFeatures.features.push(JSON.parse(feature.points));
        }
        if (feature.lines) {
          allFeatures.features.push(JSON.parse(feature.lines));
        }
        if (feature.polys) {
          allFeatures.features.push(JSON.parse(feature.polys));
        }
      });
  
      if (relocate) {
        // compute the bounds of allFeatures
        const bounds = L.geoJSON(allFeatures).getBounds();
        map.fitBounds(bounds);
      }
    }
  }

  #_createMap(id, lat, lng, zoom) {
    return L.map(id).setView([lat, lng], zoom);
  };

  #_addTileLayer(map, url, options) {
    L.tileLayer(url, options).addTo(map);
  };

  #_getURLParameters(url) {
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

  #_createPopupContent(feature, featureReportsString) {
    const newUrlFeatureName = new URL(`/publications/feature/${feature.feature_pk}`, window.location.href);
    return `<b>Name:</b> <a style="text-decoration:underline" href=${newUrlFeatureName}>${feature.name}</a><br>
            <b>Type:</b> ${feature.type}<br>
            <b>Date:</b> ${feature.date}<br>
            <b>Reports:</b> ${featureReportsString}<br>`;
  };



  #_createFeatureReportsString(publications) {
    return publications.map(pub => `<a style="text-decoration:underline" href="/publications/report/${pub.id}/">${pub.number}</a>`).join(', ');
  };

  #_getColorByType(type) {
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

  #_addGeoJSONLayer(geoJSONData, map, color, popupContent) {
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





}