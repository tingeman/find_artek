class MyMapClass {
  constructor() { }


  // this funcion creates a map you can work with
  // const map = await myMapClass.initialize();
  initialize() {
    return new Promise((resolve, reject) => {



      try {



        // ================= this part is to (attempt) retrive a location, that is passed in the url ================= //
        // ================= http://localhost:8080/publications/map/?lat=66.99&lng=-53.22&zoom=14.00 ================= //

        // if featureData is not null, use it to set the map center and zoom
        var params = this.#_getURLParameters(window.location.href);
        var lat = params.lat;
        var lng = params.lng;
        var zoom = params.zoom;

        // if lat, lng or zoom are not defined, use default values
        if (!lat || !lng || !zoom) {
          lat = 70.00;
          lng = -44.00; // Fixed syntax error: removed extra dot
          zoom = 4.00;
        }

        // // ================= this part is to (attempt) retrive a location, that is passed in the url ================= //
        // // ================= http://localhost:8080/publications/map/?lat=66.99&lng=-53.22&zoom=14.00 ================= //



        // // Create the map, set the view to the lat, lng, and zoom
        // // I think lat, lng, and zoom will be what you see in the map.
        // const map = L.map('map').setView([lat, lng], zoom);
        // const url = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
        // const options = {
        //   maxZoom: 29,
        //   attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">'
        // };
        // L.tileLayer(url, options).addTo(map);

        // // ================= this part is that sets a location, that is passed in the url             ================= //
        // // ================= http://localhost:8080/publications/map/?lat=66.99&lng=-53.22&zoom=14.00  ================= //
        // // it sort of a side effect, that is happening here, which i am not pitucularly big fan of. but it is my implementation so fare.


        // ================= THIN attempt at better map projection ================= //
        var pixel_ratio = parseInt(window.devicePixelRatio) || 1;
        var max_zoom = 16;
        var tile_size = 512;
        var extent = Math.sqrt(2) * 6371007.2;
        var resolutions = Array(max_zoom + 1).fill().map((_, i) => ( extent / tile_size / Math.pow(2, i-1) ));

        console.log('Debug information:')
        console.log(proj4); // Should log the Proj4 object
        console.log(L.Proj); // Should log the Proj4Leaflet namespace

        var crs = new L.Proj.CRS(
          'EPSG:3575',
          '+proj=laea +lat_0=90 +lon_0=10 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs',
          {
              origin: [-extent, extent],
              projectedBounds: L.bounds(L.point(-extent, extent), L.point(extent, -extent)),
              resolutions: resolutions
          }
        );

        var map = L.map('map', {
          crs: crs,
          rotate: true,
        }).setView([lat, lng], zoom);

        try {
          //https://gibs.earthdata.nasa.gov/wmts/epsg{*EPSG:Code*}/best/{*LayerIdentifier*}/default/{*Time*}/{*TileMatrixSet*}/{*ZoomLevel*}/{*TileRow*}/{*TileCol*}.png
          //https://gibs.earthdata.nasa.gov/wmts/epsg3413/best/Reference_Features_15m/default/2014-04-09/GoogleMapsCompatible_Level6/{z}/{x}/{y}.png
          L.tileLayer('https://tile.gbif.org/3575/omt/{z}/{x}/{y}@{r}x.png?style=osm-light'.replace('{r}', pixel_ratio), {
              tileSize: tile_size,
              minZoom: 1,
              maxZoom: 16
          }).addTo(map);
        }
        catch (err) {
            console.error(err);
        }
        
        map.setBearing(-54);
        // ================= END of THIN attempt at better map projection ================= //
        
        map.on('moveend zoomend', function () {
          const center = map.getCenter();
          const zoom = map.getZoom();

          // Update parameters
          const newParams = new URLSearchParams(window.location.search);
          newParams.set('lat', center.lat.toFixed(2));
          newParams.set('lng', center.lng.toFixed(2));
          newParams.set('zoom', zoom.toFixed(2));

          // Update the URL without reloading the page
          window.history.replaceState({}, '', '?' + newParams.toString());
        });

        // ================= this part is that sets a location, that is passed in the url             ================= //
        // ================= http://localhost:8080/publications/map/?lat=66.99&lng=-53.22&zoom=14.00  ================= //


        // Resolve the promise with the map object
        resolve(map);
      } catch (error) {
        reject(error);
      }
    });
  }










  addFeatureDataToMap(map, featureData = self.getFeatureData(), relocate = false) {



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





        // add points, lines, and polys to allFeatures
        if (feature.points) {
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
              return marker;
            }
          };

          this.#_addGeoJSONLayer(feature.points, map, options, popupContent);
          allFeatures.features.push(JSON.parse(feature.points));
        }

        if (feature.lines) {
          const options = {
            style: {
              color: color,
              weight: 2,
              opacity: 1
            }
          };

          this.#_addGeoJSONLayer(feature.lines, map, options, popupContent);
          allFeatures.features.push(JSON.parse(feature.lines));
        }

        if (feature.polys) {
          const options = {
            style: {
              color: color,
              weight: 2,
              opacity: 1
            }
          };

          this.#_addGeoJSONLayer(feature.polys, map, options, popupContent);
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




  async getFeatureData() {
    // Try to get the data from session storage first
    let featureData = sessionStorage.getItem('featureData');

    if (featureData) {
      // If data exists in storage, parse it from the string and return
      return JSON.parse(featureData);
    } else {
      // If not, fetch the data from the endpoint
      const response = await fetch(URL_PREFIX + '/api/feature/');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      featureData = await response.json();

      // Store the data in session storage as a string
      sessionStorage.setItem('featureData', JSON.stringify(featureData));

      // Return the fetched data
      return featureData;
    }
  }




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

  #_addGeoJSONLayer(geoJSONData, map, options, popupContent) {
    if (!geoJSONData) return;

    options.onEachFeature = function (feature, layer) {
      // bind popup to each feature in the GeoJSON layer
      layer.bindPopup(popupContent);
    };

    L.geoJSON(JSON.parse(geoJSONData), options).addTo(map);
  }





}
