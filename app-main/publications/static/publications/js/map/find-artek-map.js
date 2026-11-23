/*
 * FindArtekMap: the shared Leaflet map of find_artek (plan "features" T3).
 *
 * One component for the overview map, the report page and the feature page (and, from T5,
 * the digitize page). Polar projection EPSG:3574 (North Pole LAEA Atlantic, Proj4Leaflet):
 * Greenland is upright without rotating the map (owner decision 2026-11-23; the earlier
 * EPSG:3575 map rotated with leaflet-rotate is kept in docs/archive/map_epsg3575_rotate/).
 * Background: Dataforsyningen WMS layers in a layer switcher when the page has a token
 * (find-artek-map-layers.js, load it before this file); without a token a plain background.
 *
 * Scripts, in this order: leaflet.js, proj4.js, proj4leaflet.js, find-artek-map-layers.js,
 * find-artek-map.js.
 *
 * Usage:
 *   const fam = new FindArtekMap({element: 'map', mode: 'report', publicationId: 12});
 *   await fam.loadFeatures();
 *
 * Options (data-* attributes of the element are used when an option is not given):
 *   element        the map element or its id (required)
 *   mode           'overview' | 'report' | 'feature'               (data-map-mode)
 *   publicationId  report whose features are shown (mode 'report')   (data-publication-id)
 *   featureId      the feature shown (mode 'feature')                (data-feature-id)
 *   token          Dataforsyningen token, '' for none          (data-dataforsyningen-token)
 *   syncUrl        keep lat/lng/zoom in the page URL; default true for 'overview' only
 *   fitMaxZoom     highest zoom when fitting the map to features (default 12)
 *   editable       false; true calls enableEditing() after the map is created (T5)
 *   wheelZoom      'always' | 'focus': with 'focus' the mouse wheel zooms the map only after
 *                  the user clicked into it (or focused it with the keyboard), until the
 *                  pointer leaves it or it loses focus; before that the wheel scrolls the
 *                  page. Default 'always' for 'overview' (a full-page map), 'focus' otherwise
 *                  (maps embedded in long pages; T11)
 *
 * Public members and methods:
 *   map                   the L.Map
 *   featureLayer          L.FeatureGroup with every feature drawn by addFeatures()
 *   layers                {baseLayers, overlays, control, active} from FindArtekMapLayers
 *   loadFeatures()        fetch the features for the mode and draw them; resolves to the
 *                         feature records (an array; empty when nothing is visible)
 *   addFeatures(records, {fit})  draw API feature records; fit = fit the map to them
 *   fitToFeatures()       fit the map to featureLayer (no change when it is empty)
 *   setTypeFilter(types)  show only features whose type is in `types` (an array of
 *                         Feature.type values); null shows every type (T11)
 *   recordsInView()       the records drawn by addFeatures() that are shown (type filter)
 *                         and whose bounding box overlaps the current view (T11)
 *   enableEditing(opts)   edit mode hook, see below
 *   FindArtekMap.fetchFeatures({publicationId, featureId})  the API call alone
 *   FindArtekMap.typeColors()  colour per feature type, read from the page's JSON block
 *                         #find-artek-type-colors ({% feature_type_colors_script %}, built
 *                         from publications/map_styles.py, the single source shared with the
 *                         legend); every page with this map must include it (T11)
 *   FindArtekMap.colorForType(type)  the colour of one type ('gray' when unknown)
 *   FindArtekMap.reportUrl(id)  the report page URL of a report id
 *   FindArtekMap.addInitHook(fn)  fn(instance) runs for every new map, after the map and its
 *                         layers exist and before any feature is loaded
 *
 * Edit mode (T5): T5 adds a file (e.g. find-artek-map-edit.js, loaded after this one) that
 * replaces FindArtekMap.prototype.enableEditing with the leaflet-draw implementation, drawing
 * into its own L.FeatureGroup. Pages create the map with {editable: true}. Without that file
 * enableEditing() only logs an error.
 */
(function () {
    'use strict';

    var CRS_CODE = 'EPSG:3574';
    var PROJ4_DEF = '+proj=laea +lat_0=90 +lon_0=-40 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs';
    // The tile grid of the Arctic SDI basemap (WMTS tile matrix set "3574"), so its tiles line
    // up exactly: origin top left, 256 px tiles, level 0 = one tile over the whole extent.
    var GRID_EXTENT = 4889334.802955;
    var TILE_SIZE = 256;
    var MAX_ZOOM = 18;
    var DEFAULT_VIEW = {lat: 70.0, lng: -44.0, zoom: 4};
    var DEFAULT_FIT_MAX_ZOOM = 12;
    var NO_BACKGROUND_COLOR = '#eef2f5';

    // Feature type colours: the JSON block rendered by {% feature_type_colors_script %}
    // (publications/map_styles.py). Not repeated here, so map and legend can't disagree.
    var TYPE_COLORS_ID = 'find-artek-type-colors';
    var UNKNOWN_TYPE_COLOR = 'gray';
    var typeColors = null;

    var initHooks = [];
    var crs = null;

    // EPSG:3574 on the Arctic SDI grid: resolution 2 * GRID_EXTENT / 256 / 2^z m/px (about
    // 38198 m/px at zoom 0, 37.3 at 10, 0.15 at 18). WMS layers work with any resolution.
    // No `bounds`: the CRS stays unbounded, as before (Proj4Leaflet 1.0.2 would need L.bounds).
    function polarCrs() {
        if (!crs) {
            var resolutions = [];
            for (var z = 0; z <= MAX_ZOOM; z++) {
                resolutions.push(2 * GRID_EXTENT / TILE_SIZE / Math.pow(2, z));
            }
            crs = new L.Proj.CRS(CRS_CODE, PROJ4_DEF, {
                origin: [-GRID_EXTENT, GRID_EXTENT],
                resolutions: resolutions,
            });
        }
        return crs;
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function intOrNull(value) {
        var number = parseInt(value, 10);
        return isNaN(number) ? null : number;
    }

    function prefix() {
        return typeof URL_PREFIX === 'string' ? URL_PREFIX : '';
    }

    function viewFromUrl() {
        var params = new URLSearchParams(window.location.search);
        var lat = parseFloat(params.get('lat'));
        var lng = parseFloat(params.get('lng'));
        var zoom = parseFloat(params.get('zoom'));
        if (isNaN(lat) || isNaN(lng) || isNaN(zoom)) {
            return null;
        }
        return {lat: lat, lng: lng, zoom: zoom};
    }

    function reportUrl(id) {
        return prefix() + '/publications/report/' + encodeURIComponent(id) + '/';
    }

    function popupContent(record) {
        var featureUrl = prefix() + '/publications/feature/' + encodeURIComponent(record.feature_pk) + '/';
        var reports = (record.related_publications || []).map(function (pub) {
            return '<a style="text-decoration:underline" href="' + reportUrl(pub.id) + '">' +
                escapeHtml(pub.number) + '</a>';
        }).join(', ');
        return '<b>Name:</b> <a style="text-decoration:underline" href="' + featureUrl + '">' +
            escapeHtml(record.name) + '</a><br>' +
            '<b>Type:</b> ' + escapeHtml(record.type) + '<br>' +
            '<b>Date:</b> ' + escapeHtml(record.date) + '<br>' +
            '<b>Reports:</b> ' + reports + '<br>';
    }

    function geoJsonLayer(geometry, color, popup) {
        var data;
        try {
            data = JSON.parse(geometry);
        } catch (e) {
            console.error('find-artek-map: invalid GeoJSON geometry', e);
            return null;
        }
        return L.geoJSON(data, {
            pointToLayer: function (feature, latlng) {
                return L.circleMarker(latlng, {
                    radius: 8, fillColor: color, color: '#000', weight: 1,
                    opacity: 1, fillOpacity: 0.8,
                });
            },
            style: function () {
                return {color: color, weight: 2, opacity: 1};
            },
            onEachFeature: function (feature, layer) {
                layer.bindPopup(popup);
            },
        });
    }

    // Bounding box {minX, minY, maxX, maxY} of a drawn feature in map CRS metres (EPSG:3574),
    // so the view check below needs no inverse projection. null when it has no coordinates.
    function projectedBounds(layers) {
        var box = null;
        function addLatLngs(latlngs) {
            if (Array.isArray(latlngs)) {
                latlngs.forEach(addLatLngs);
                return;
            }
            var point = polarCrs().project(latlngs);
            if (!isFinite(point.x) || !isFinite(point.y)) {
                return;
            }
            if (!box) {
                box = {minX: point.x, minY: point.y, maxX: point.x, maxY: point.y};
            } else {
                box.minX = Math.min(box.minX, point.x);
                box.maxX = Math.max(box.maxX, point.x);
                box.minY = Math.min(box.minY, point.y);
                box.maxY = Math.max(box.maxY, point.y);
            }
        }
        layers.forEach(function (layer) {
            layer.eachLayer(function (sublayer) {
                if (sublayer.getLatLng) {
                    addLatLngs(sublayer.getLatLng());
                } else if (sublayer.getLatLngs) {
                    addLatLngs(sublayer.getLatLngs());
                }
            });
        });
        return box;
    }

    // The current view in map CRS metres: pixel bounds -> CRS metres (the map isn't rotated,
    // so the view is an axis-aligned rectangle there).
    function viewBounds(map) {
        var crsObject = map.options.crs;
        var scale = crsObject.scale(map.getZoom());
        var pixels = map.getPixelBounds();
        var a = crsObject.transformation.untransform(pixels.min, scale);
        var b = crsObject.transformation.untransform(pixels.max, scale);
        return {minX: Math.min(a.x, b.x), maxX: Math.max(a.x, b.x),
                minY: Math.min(a.y, b.y), maxY: Math.max(a.y, b.y)};
    }

    function overlaps(box, view) {
        return box.minX <= view.maxX && box.maxX >= view.minX &&
            box.minY <= view.maxY && box.maxY >= view.minY;
    }

    // The mouse wheel zooms only while the user works with the map (wheelZoom 'focus').
    // Leaflet focuses the map element on a click, so 'focus' covers mouse and keyboard.
    function wheelZoomOnFocus(map, element) {
        map.scrollWheelZoom.disable();
        function enable() { map.scrollWheelZoom.enable(); }
        function disable() { map.scrollWheelZoom.disable(); }
        element.addEventListener('mousedown', enable);
        element.addEventListener('focus', enable);
        element.addEventListener('mouseleave', disable);
        element.addEventListener('blur', disable);
    }

    function FindArtekMap(options) {
        options = options || {};
        var element = typeof options.element === 'string'
            ? document.getElementById(options.element) : options.element;
        if (!element) {
            throw new Error('FindArtekMap: map element not found');
        }
        var data = element.dataset || {};

        this.element = element;
        this.mode = options.mode || data.mapMode || 'overview';
        this.publicationId = options.publicationId != null
            ? intOrNull(options.publicationId) : intOrNull(data.publicationId);
        this.featureId = options.featureId != null
            ? intOrNull(options.featureId) : intOrNull(data.featureId);
        this.token = options.token != null ? options.token : (data.dataforsyningenToken || '');
        this.syncUrl = options.syncUrl != null ? !!options.syncUrl : this.mode === 'overview';
        this.fitMaxZoom = options.fitMaxZoom || DEFAULT_FIT_MAX_ZOOM;
        this.editable = !!options.editable;
        this.wheelZoom = options.wheelZoom || (this.mode === 'overview' ? 'always' : 'focus');
        this.typeFilter = null;     // null: every type shown
        this.entries = [];          // {record, layers, box, shown} per drawn record

        var view = (this.syncUrl && viewFromUrl()) || DEFAULT_VIEW;
        this.map = L.map(element, {crs: polarCrs(), maxZoom: MAX_ZOOM})
            .setView([view.lat, view.lng], view.zoom);
        if (this.wheelZoom === 'focus') {
            wheelZoomOnFocus(this.map, element);
        }

        this.layers = window.FindArtekMapLayers.addTo(this.map, {
            token: this.token, tileSize: TILE_SIZE, maxZoom: MAX_ZOOM,
        });
        if (!this.layers.active) {
            // No background layer (no token): a plain background behind the features.
            element.style.background = NO_BACKGROUND_COLOR;
        }
        this.featureLayer = L.featureGroup().addTo(this.map);

        if (this.syncUrl) {
            this._syncUrl();
        }

        var self = this;
        initHooks.forEach(function (hook) { hook(self); });

        if (this.editable) {
            this.enableEditing();
        }
    }

    FindArtekMap.TILE_SIZE = TILE_SIZE;
    FindArtekMap.MAX_ZOOM = MAX_ZOOM;
    FindArtekMap.polarCrs = polarCrs;

    FindArtekMap.addInitHook = function (hook) {
        initHooks.push(hook);
    };

    FindArtekMap.typeColors = function () {
        if (typeColors === null) {
            typeColors = {};
            var block = document.getElementById(TYPE_COLORS_ID);
            if (!block) {
                console.error('find-artek-map: #' + TYPE_COLORS_ID + ' is missing on this page');
            } else {
                try {
                    typeColors = JSON.parse(block.textContent) || {};
                } catch (e) {
                    console.error('find-artek-map: invalid #' + TYPE_COLORS_ID, e);
                }
            }
        }
        return typeColors;
    };

    FindArtekMap.colorForType = function (type) {
        return FindArtekMap.typeColors()[type] || UNKNOWN_TYPE_COLOR;
    };

    FindArtekMap.reportUrl = reportUrl;

    // Features from the API, always fresh (no browser cache, FA-R89). `featureId`: that one
    // feature ([] when it is not visible); `publicationId`: the features of that report;
    // neither: every feature the user may see.
    FindArtekMap.fetchFeatures = async function (filters) {
        filters = filters || {};
        var url = prefix() + '/api/feature/';
        if (filters.featureId != null) {
            url += encodeURIComponent(filters.featureId) + '/';
        } else if (filters.publicationId != null) {
            url += '?' + new URLSearchParams({publication_id: filters.publicationId}).toString();
        }
        var response = await fetch(url, {headers: {'Accept': 'application/json'}});
        if (filters.featureId != null && response.status === 404) {
            return [];
        }
        if (!response.ok) {
            throw new Error('find-artek-map: HTTP ' + response.status + ' for ' + url);
        }
        var body = await response.json();
        return Array.isArray(body) ? body : [body];
    };

    FindArtekMap.prototype.loadFeatures = async function () {
        var filters = {};
        if (this.mode === 'feature') {
            if (this.featureId == null) {
                return [];
            }
            filters.featureId = this.featureId;
        } else if (this.mode === 'report') {
            if (this.publicationId == null) {
                return [];
            }
            filters.publicationId = this.publicationId;
        }
        var records = await FindArtekMap.fetchFeatures(filters);
        this.addFeatures(records, {fit: this.mode !== 'overview'});
        return records;
    };

    FindArtekMap.prototype.addFeatures = function (records, options) {
        var self = this;
        (records || []).forEach(function (record) {
            var color = FindArtekMap.colorForType(record.type);
            var popup = popupContent(record);
            var layers = [];
            ['points', 'lines', 'polys'].forEach(function (kind) {
                if (record[kind]) {
                    var layer = geoJsonLayer(record[kind], color, popup);
                    if (layer) {
                        layers.push(layer);
                    }
                }
            });
            var entry = {record: record, layers: layers, box: projectedBounds(layers),
                         shown: false};
            self.entries.push(entry);
            self._showEntry(entry, self._typeShown(record.type));
        });
        if (options && options.fit) {
            this.fitToFeatures();
        }
    };

    FindArtekMap.prototype.fitToFeatures = function () {
        var bounds = this.featureLayer.getBounds();
        if (bounds.isValid()) {
            this.map.fitBounds(bounds, {maxZoom: this.fitMaxZoom, padding: [20, 20]});
        }
    };

    FindArtekMap.prototype._typeShown = function (type) {
        return this.typeFilter === null || this.typeFilter.indexOf(type) !== -1;
    };

    FindArtekMap.prototype._showEntry = function (entry, show) {
        var featureLayer = this.featureLayer;
        if (show && !entry.shown) {
            entry.layers.forEach(function (layer) { featureLayer.addLayer(layer); });
        } else if (!show && entry.shown) {
            entry.layers.forEach(function (layer) { featureLayer.removeLayer(layer); });
        }
        entry.shown = show;
    };

    FindArtekMap.prototype.setTypeFilter = function (types) {
        var self = this;
        this.typeFilter = types == null ? null : types.slice();
        this.entries.forEach(function (entry) {
            self._showEntry(entry, self._typeShown(entry.record.type));
        });
    };

    FindArtekMap.prototype.recordsInView = function () {
        var view = viewBounds(this.map);
        return this.entries
            .filter(function (entry) {
                return entry.shown && entry.box && overlaps(entry.box, view);
            })
            .map(function (entry) { return entry.record; });
    };

    // Edit mode hook: replaced by T5's leaflet-draw implementation.
    FindArtekMap.prototype.enableEditing = function () {
        console.error('find-artek-map: edit mode is not available on this page');
    };

    FindArtekMap.prototype._syncUrl = function () {
        var map = this.map;
        map.on('moveend zoomend', function () {
            var center = map.getCenter();
            var params = new URLSearchParams(window.location.search);
            params.set('lat', center.lat.toFixed(2));
            params.set('lng', center.lng.toFixed(2));
            params.set('zoom', map.getZoom().toFixed(2));
            window.history.replaceState(window.history.state, '',
                window.location.pathname + '?' + params.toString() + window.location.hash);
        });
    };

    window.FindArtekMap = FindArtekMap;
})();
