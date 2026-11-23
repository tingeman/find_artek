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
 * single markers, lines and polygons (FindArtekMap.singleGeometries), one layer each, so each
 * part can be moved, reshaped or deleted on its own. They are added polygons first, then lines
 * (FindArtekMap.inDrawOrder; T17), so a line on a polygon is above its fill and clickable;
 * raiseEditLayer() puts the drawing above the report's other features after they are loaded.
 *
 * Joining back: Leaflet's toGeoJSON gives a FeatureCollection with one Feature per layer
 * (Point, LineString, Polygon); the server (publications.geometry.from_geojson) collects them
 * into the MultiPoint / MultiLineString / MultiPolygon columns. The drawing order keeps the
 * order within each kind, so an unchanged drawing compares equal (same_geometry).
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
 *   raiseEditLayer()      bring the drawing above the other features (T17)
 *   FindArtekMap.singleGeometries(geojson), FindArtekMap.inDrawOrder(geometries)  pure helpers
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

    var SINGLE_TYPE = {MultiPoint: 'Point', MultiLineString: 'LineString', MultiPolygon: 'Polygon'};
    // Bottom to top (plan "features" T17): polygons first, so a line or point on a polygon
    // is drawn above its fill and can still be clicked (delete mode, edit mode).
    var DRAW_RANK = {Polygon: 0, LineString: 1, Point: 2};

    // GeoJSON (FeatureCollection, Feature, geometry, GeometryCollection) -> array of single
    // GeoJSON geometries (Point, LineString, Polygon), multi-geometries split, in input order.
    // Pure (no Leaflet): FindArtekMap.singleGeometries. Unknown types are logged and skipped.
    function singleGeometries(data) {
        if (!data) {
            return [];
        }
        switch (data.type) {
        case 'FeatureCollection':
            return (data.features || []).reduce(function (all, feature) {
                return all.concat(singleGeometries(feature));
            }, []);
        case 'Feature':
            return singleGeometries(data.geometry);
        case 'GeometryCollection':
            return (data.geometries || []).reduce(function (all, geometry) {
                return all.concat(singleGeometries(geometry));
            }, []);
        case 'Point':
        case 'LineString':
        case 'Polygon':
            return [{type: data.type, coordinates: data.coordinates}];
        case 'MultiPoint':
        case 'MultiLineString':
        case 'MultiPolygon':
            return (data.coordinates || []).map(function (coordinates) {
                return {type: SINGLE_TYPE[data.type], coordinates: coordinates};
            });
        default:
            console.error('find-artek-map-edit: geometry type not editable', data);
            return [];
        }
    }

    // The single geometries in drawing order (DRAW_RANK). Stable: each kind keeps its order,
    // so an untouched MultiLineString etc. is saved with its parts in the same order.
    function inDrawOrder(geometries) {
        return geometries
            .map(function (geometry, index) { return {geometry: geometry, index: index}; })
            .sort(function (a, b) {
                return (DRAW_RANK[a.geometry.type] - DRAW_RANK[b.geometry.type]) ||
                    (a.index - b.index);
            })
            .map(function (item) { return item.geometry; });
    }

    // One editable layer (marker, polyline, polygon) per single geometry.
    function layerOfGeometry(geometry) {
        switch (geometry.type) {
        case 'Point':
            return L.marker(L.GeoJSON.coordsToLatLng(geometry.coordinates));
        case 'LineString':
            return L.polyline(lineLatLngs(geometry.coordinates), EDIT_STYLE);
        default:   // Polygon
            return L.polygon(polygonLatLngs(geometry.coordinates), EDIT_STYLE);
        }
    }

    function layersOfGeoJSON(data) {
        return inDrawOrder(singleGeometries(data)).map(layerOfGeometry);
    }

    FindArtekMap.singleGeometries = singleGeometries;
    FindArtekMap.inDrawOrder = inDrawOrder;

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

    // Put the drawing above the other features of the report (loaded later, they would
    // otherwise cover it and take its clicks); polygons first, so lines stay above polygon
    // fills. Markers have their own pane above all paths.
    FindArtekMap.prototype.raiseEditLayer = function () {
        if (!this.editLayer) {
            return;
        }
        var layers = this.editLayer.getLayers();
        var polygons = layers.filter(function (layer) { return layer instanceof L.Polygon; });
        var lines = layers.filter(function (layer) {
            return layer instanceof L.Polyline && !(layer instanceof L.Polygon);
        });
        polygons.concat(lines).forEach(function (layer) {
            if (layer._map) {
                layer.bringToFront();
            }
        });
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
