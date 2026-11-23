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
 *
 * Public members and methods:
 *   map                   the L.Map
 *   featureLayer          L.FeatureGroup with every feature drawn by addFeatures()
 *   layers                {baseLayers, overlays, control, active} from FindArtekMapLayers
 *   loadFeatures()        fetch the features for the mode and draw them; resolves to the
 *                         feature records (an array; empty when nothing is visible)
 *   addFeatures(records, {fit})  draw API feature records; fit = fit the map to them
 *   fitToFeatures()       fit the map to featureLayer (no change when it is empty)
 *   enableEditing(opts)   edit mode hook, see below
 *   FindArtekMap.fetchFeatures({publicationId, featureId})  the API call alone
 *   FindArtekMap.TYPE_COLORS  colour per feature type (for legends)
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

    var TYPE_COLORS = {
        'PHOTO': 'red',
        'SAMPLE': 'green',
        'BOREHOLE': 'yellow',
        'GEOPHYSICAL DATA': 'blue',
        'FIELD MEASUREMENT': 'purple',
        'LAB MEASUREMENT': 'pink',
        'RESOURCE': 'brown',
        'OTHER': 'white',
    };

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

    function popupContent(record) {
        var featureUrl = prefix() + '/publications/feature/' + encodeURIComponent(record.feature_pk) + '/';
        var reports = (record.related_publications || []).map(function (pub) {
            return '<a style="text-decoration:underline" href="' + prefix() + '/publications/report/' +
                encodeURIComponent(pub.id) + '/">' + escapeHtml(pub.number) + '</a>';
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

        var view = (this.syncUrl && viewFromUrl()) || DEFAULT_VIEW;
        this.map = L.map(element, {crs: polarCrs(), maxZoom: MAX_ZOOM})
            .setView([view.lat, view.lng], view.zoom);

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

    FindArtekMap.TYPE_COLORS = TYPE_COLORS;
    FindArtekMap.TILE_SIZE = TILE_SIZE;
    FindArtekMap.MAX_ZOOM = MAX_ZOOM;
    FindArtekMap.polarCrs = polarCrs;

    FindArtekMap.addInitHook = function (hook) {
        initHooks.push(hook);
    };

    FindArtekMap.colorForType = function (type) {
        return TYPE_COLORS[type] || 'white';
    };

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
            ['points', 'lines', 'polys'].forEach(function (kind) {
                if (record[kind]) {
                    var layer = geoJsonLayer(record[kind], color, popup);
                    if (layer) {
                        layer.addTo(self.featureLayer);
                    }
                }
            });
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
