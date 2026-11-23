/*
 * FindArtekMap edit mode (plan "features" T5): draw, edit and delete the geometry of one
 * feature with Leaflet.draw on the shared polar map (EPSG:3574, no rotation).
 *
 * Scripts, in this order: leaflet.js, leaflet.draw.js, proj4.js, proj4leaflet.js,
 * find-artek-map-layers.js, find-artek-map.js, find-artek-map-edit.js.
 *
 * This file replaces FindArtekMap.prototype.enableEditing. A map created with
 * {editable: true} calls it at the end of the constructor. Options (data-* attributes of the
 * map element are used when an option is not given):
 *   input       the hidden form field (or its id) with the GeoJSON   (data-geojson-input)
 *   imagePath   URL of Leaflet's images/ folder for the marker icons (data-leaflet-images)
 *
 * The drawing lives in its own L.FeatureGroup, `editLayer`, above `featureLayer` (other
 * features shown for orientation, not editable). The field's value at start (the stored
 * geometry, a FeatureCollection of MultiPoint / MultiLineString / MultiPolygon) is split into
 * single markers, lines and polygons, so each part can be moved, reshaped or deleted.
 *
 * The field gets the drawing as a GeoJSON FeatureCollection in WGS84 (lon/lat, coordinates
 * not rounded) after each created / edited / deleted event, and from syncEditInput() (the
 * page calls it on submit, for changes made in edit or delete mode without pressing "Save").
 * Until something is drawn, edited or deleted, the field keeps its value unchanged, so the
 * server sees an untouched geometry as unchanged. Empty drawing: empty field.
 *
 * Added members:
 *   editLayer             L.FeatureGroup with the drawn layers
 *   drawControl           the L.Control.Draw (marker, polyline, polygon; edit, delete)
 *   syncEditInput()       write the drawing to the field if anything was touched
 *   editCounts()          {points, lines, polygons} in the drawing
 * The map fires 'findartek:editchange' with {counts} after the field was written.
 */
(function () {
    'use strict';

    if (!window.FindArtekMap) {
        console.error('find-artek-map-edit: load find-artek-map.js first');
        return;
    }

    var EDIT_STYLE = {color: '#e6007e', weight: 3, opacity: 1, fillOpacity: 0.2};

    function lineLatLngs(coords) {
        return L.GeoJSON.coordsToLatLngs(coords, 0);
    }

    function polygonLatLngs(rings) {
        return L.GeoJSON.coordsToLatLngs(rings, 1);
    }

    // Single editable layers (marker, polyline, polygon) of one GeoJSON geometry.
    function layersOfGeometry(geometry) {
        var coords = geometry && geometry.coordinates;
        switch (geometry && geometry.type) {
        case 'Point':
            return [L.marker(L.GeoJSON.coordsToLatLng(coords))];
        case 'MultiPoint':
            return coords.map(function (c) { return L.marker(L.GeoJSON.coordsToLatLng(c)); });
        case 'LineString':
            return [L.polyline(lineLatLngs(coords), EDIT_STYLE)];
        case 'MultiLineString':
            return coords.map(function (c) { return L.polyline(lineLatLngs(c), EDIT_STYLE); });
        case 'Polygon':
            return [L.polygon(polygonLatLngs(coords), EDIT_STYLE)];
        case 'MultiPolygon':
            return coords.map(function (c) { return L.polygon(polygonLatLngs(c), EDIT_STYLE); });
        default:
            console.error('find-artek-map-edit: geometry type not editable', geometry);
            return [];
        }
    }

    function layersOfGeoJSON(data) {
        if (!data) {
            return [];
        }
        if (data.type === 'FeatureCollection') {
            return (data.features || []).reduce(function (all, feature) {
                return all.concat(layersOfGeoJSON(feature));
            }, []);
        }
        if (data.type === 'Feature') {
            return data.geometry ? layersOfGeometry(data.geometry) : [];
        }
        return layersOfGeometry(data);
    }

    function element(value) {
        return typeof value === 'string' ? document.getElementById(value) : (value || null);
    }

    FindArtekMap.prototype.enableEditing = function (options) {
        if (this.editLayer) {
            return this.editLayer;
        }
        if (!L.Control || !L.Control.Draw) {
            console.error('find-artek-map-edit: load leaflet.draw.js first');
            return null;
        }
        options = options || {};
        var data = this.element.dataset || {};
        var self = this;
        var map = this.map;

        var imagePath = options.imagePath || data.leafletImages;
        if (imagePath) {
            L.Icon.Default.imagePath = imagePath;   // the vendored Leaflet images/
        }

        this.editInput = element(options.input || data.geojsonInput);
        this.editLayer = L.featureGroup().addTo(map);
        this._editTouched = false;

        if (this.editInput && this.editInput.value) {
            try {
                layersOfGeoJSON(JSON.parse(this.editInput.value)).forEach(function (layer) {
                    self.editLayer.addLayer(layer);
                });
            } catch (error) {
                console.error('find-artek-map-edit: the stored geometry is not GeoJSON', error);
            }
        }

        this.drawControl = new L.Control.Draw({
            position: 'topleft',
            draw: {
                marker: {icon: new L.Icon.Default()},
                polyline: {shapeOptions: EDIT_STYLE},
                // showArea off: Leaflet.draw 1.0.4's readableArea assigns an undeclared
                // variable (`type`), which throws in strict mode.
                polygon: {allowIntersection: false, showArea: false, shapeOptions: EDIT_STYLE},
                rectangle: false,   // a lon/lat box is not a rectangle on the polar map
                circle: false,
                circlemarker: false,
            },
            edit: {featureGroup: this.editLayer, remove: true},
        });
        map.addControl(this.drawControl);

        map.on('draw:created', function (event) {
            if (event.layer.setStyle) {
                event.layer.setStyle(EDIT_STYLE);
            }
            self.editLayer.addLayer(event.layer);
            self._editTouched = true;
            self.syncEditInput();
        });
        map.on('draw:edited draw:deleted', function () {
            self._editTouched = true;
            self.syncEditInput();
        });
        // Layers change while edit or delete mode is on, before "Save" is pressed.
        map.on('draw:editstart draw:deletestart', function () {
            self._editTouched = true;
        });

        var bounds = this.editLayer.getBounds();
        if (bounds.isValid()) {
            map.fitBounds(bounds, {maxZoom: this.fitMaxZoom, padding: [30, 30]});
        }
        return this.editLayer;
    };

    FindArtekMap.prototype.syncEditInput = function () {
        if (!this.editLayer || !this.editInput || !this._editTouched) {
            return;
        }
        var empty = this.editLayer.getLayers().length === 0;
        // false: no rounding (Leaflet rounds to 6 decimals by default).
        this.editInput.value = empty ? '' : JSON.stringify(this.editLayer.toGeoJSON(false));
        this.map.fire('findartek:editchange', {counts: this.editCounts()});
    };

    FindArtekMap.prototype.editCounts = function () {
        var counts = {points: 0, lines: 0, polygons: 0};
        if (!this.editLayer) {
            return counts;
        }
        this.editLayer.eachLayer(function (layer) {
            if (layer instanceof L.Marker) {
                counts.points += 1;
            } else if (layer instanceof L.Polygon) {   // before Polyline: Polygon extends it
                counts.polygons += 1;
            } else if (layer instanceof L.Polyline) {
                counts.lines += 1;
            }
        });
        return counts;
    };
})();
