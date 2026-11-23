/*
 * Base layers and overlays of the find_artek map (plan "features" T3).
 *
 * The map is in EPSG:3574 (North Pole LAEA Atlantic) on the Arctic SDI tile grid
 * (find-artek-map.js). Providers:
 * - Dataforsyningen WMS (Greenland, needs the token): both services list EPSG:3574 in their
 *   capabilities (T1), so the layers are requested in the map CRS. Browsers can't set headers
 *   on tile requests, so the token goes into the query string as `token=<value>`.
 * - Arctic SDI basemap (WMTS, tile matrix set 3574, levels 0-10, no token): the background
 *   outside Greenland and the only background without a token.
 *
 * Underlay (T16): the Dataforsyningen layers cover Greenland only. Whenever another base layer
 * is chosen, a second Arctic SDI layer (not in the layer control) lies underneath it
 * (UNDERLAY_Z_INDEX below BASE_Z_INDEX), so the map outside Greenland shows the Arctic basemap
 * instead of a blank area. All Dataforsyningen layers, base layers included, are requested with
 * TRANSPARENT=TRUE: with TRANSPARENT=FALSE a WMS server fills the area without data with its
 * background colour (white by default), which would hide the underlay. When the Arctic SDI
 * basemap itself is chosen, the underlay is removed, so it is never on the map twice.
 *
 * Topographic map clipped to its coverage (T22): the topographic WMS (gl_aabent_land) returns
 * opaque white outside its coverage (Greenland's land and a sea band of roughly 15-40 km along
 * the coast) despite TRANSPARENT=TRUE, which hid the underlay there. T19 multiplied the layer
 * with the underlay (mix-blend-mode), but that also let the underlay show through inside
 * Greenland (double coastlines, ghost place names). Since T22 the layer is cut to an outline
 * instead: Greenland from Natural Earth 10m land (public domain) buffered 12 km seaward
 * (data/greenland_topo_coverage.geojson, made by `manage.py make_greenland_coverage`, about
 * 10 kB). Inside the outline the topographic map is drawn as it is; outside, the underlay shows.
 *
 * How (clipToCoverage): Leaflet draws a tile layer's tiles in one container per zoom level
 * ("level"). A level's coordinates never change while it exists: map pixels at the level's zoom
 * minus level.origin; Leaflet moves it on pan and scales it during the zoom animation with a CSS
 * transform. GridLayer calls _onCreateLevel(level) for every new level, and there the level gets
 * a CSS `clip-path: path(evenodd, "...")` with the outline in those coordinates. The clip moves
 * and scales together with the tiles, so it stays aligned on pan and during zoom animations,
 * and nothing runs on pan or zoom except one projection of the outline (about 530 points) when
 * a new level is made. The outline is fetched once per page (the versioned static URL next to
 * this script, so it is cached like the script), and only when the topographic layer is first
 * shown. Until it has arrived the levels are fully clipped (the underlay shows); if it can't be
 * loaded the layer is drawn unclipped (white border, as before T19) and an error is logged.
 * No extra tile requests. Satellite and Sentinel-2 are not clipped: their areas without data
 * are transparent (owner's check after T16), so the underlay already shows there.
 *
 * To add another provider, add an entry to BASE_LAYERS or OVERLAYS:
 * {id, name, needsToken, create(options) -> L.Layer}. Entries with needsToken are left out
 * (and nothing is requested from them) when the page has no token. The first available base
 * layer is the default.
 *
 * Exposes window.FindArtekMapLayers:
 *   BASE_LAYERS, OVERLAYS        the configuration below
 *   create(options) -> {baseLayers: [{id, name, layer}], overlays: [...], underlay: L.Layer}
 *       options.token      Dataforsyningen token ('' or undefined: no Dataforsyningen layer)
 *       options.tileSize   tile size of the map grid (256)
 *       options.maxZoom    highest zoom level of the map CRS
 *   addTo(map, options) -> {baseLayers, overlays, control, active, underlay}
 *       Adds the remembered (or default) base layer, the Arctic SDI underlay below it (unless
 *       the base layer is the Arctic SDI basemap) and, when there is something to choose,
 *       an L.control.layers switcher. Remembers the base layer the user picks in the switcher
 *       in sessionStorage (only its id, never the token): it is kept while the user moves
 *       between map pages in the same browser tab, and a new visit starts with the default
 *       again (T11). Until T11 the choice was kept in localStorage for good, so a layer once
 *       picked (e.g. the Arctic SDI basemap) came back on every page and every later visit,
 *       which looked like a wrong default. Without a token the attribution says that more
 *       layers need the token; without any base layer the map keeps a plain background.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'findArtekMap.baseLayer';
    var NO_TOKEN_NOTE = 'More map layers need FA_DATAFORSYNINGEN_TOKEN';

    // WMS tiles may have any size; 512 px means fewer requests than the grid's 256 px.
    var WMS_TILE_SIZE = 512;

    // Stacking order in Leaflet's tile pane (T16): underlay < base layer < overlays.
    var UNDERLAY_Z_INDEX = 0;
    var BASE_Z_INDEX = 1;
    var OVERLAY_Z_INDEX = 10;
    var ARCTIC_SDI_ID = 'arctic-sdi';

    // Coverage outline of the topographic map (T22, see above): a static file next to this
    // script; the URL is taken from this script's own URL, so it has the same prefix and the same
    // ?v= version. null when the script URL is unknown (the layer is then not clipped).
    var SCRIPT_PATH = 'js/map/find-artek-map-layers.js';
    var COVERAGE_PATH = 'data/greenland_topo_coverage.geojson';
    var COVERAGE_URL = coverageUrl(document.currentScript);
    // Clip of a level while the outline is loading: nothing visible (an empty path).
    var CLIP_NOTHING = 'path("M0 0Z")';
    var coverage = null;    // promise of the outline rings ([[L.LatLng]]), fetched once

    var SATELLITE_WMS = 'https://api.dataforsyningen.dk/wms/gl_satellitfoto';
    var TOPO_WMS = 'https://api.dataforsyningen.dk/wms/gl_aabent_land';
    var DATAFORSYNINGEN_ATTRIBUTION =
        '&copy; Styrelsen for Dataforsyning og Infrastruktur / Klimadatastyrelsen';

    var ARCTIC_SDI_URL =
        'https://basemap.arctic-sdi.org/mapcache/wmts/1.0.0/arctic_cascading/default/3574/{z}/{y}/{x}.png';
    var ARCTIC_SDI_MAX_NATIVE_ZOOM = 10;

    function coverageUrl(script) {
        var src = script && script.src;
        if (!src || src.indexOf(SCRIPT_PATH) === -1) {
            return null;
        }
        return src.replace(SCRIPT_PATH, COVERAGE_PATH);
    }

    // Every ring (outer rings and holes) of the Polygons and MultiPolygons in a GeoJSON object,
    // as arrays of L.LatLng.
    function coverageRings(data) {
        var rings = [];
        function addPolygon(polygon) {
            polygon.forEach(function (ring) {
                rings.push(ring.map(function (position) {
                    return L.latLng(position[1], position[0]);
                }));
            });
        }
        function add(object) {
            if (!object) {
                return;
            }
            if (object.type === 'FeatureCollection') {
                (object.features || []).forEach(add);
            } else if (object.type === 'Feature') {
                add(object.geometry);
            } else if (object.type === 'Polygon') {
                addPolygon(object.coordinates);
            } else if (object.type === 'MultiPolygon') {
                object.coordinates.forEach(addPolygon);
            }
        }
        add(data);
        return rings;
    }

    function loadCoverage() {
        if (!coverage) {
            coverage = !COVERAGE_URL
                ? Promise.reject(new Error('URL of the coverage outline unknown'))
                : fetch(COVERAGE_URL, {credentials: 'same-origin'}).then(function (response) {
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status + ' for ' + COVERAGE_URL);
                    }
                    return response.json();
                }).then(coverageRings);
        }
        return coverage;
    }

    // The CSS clip-path of a level: the outline in the level's coordinates (map pixels at
    // level.zoom minus level.origin), even-odd so holes stay holes.
    function levelClipPath(crs, rings, level) {
        var path = rings.map(function (ring) {
            return ring.map(function (latlng, index) {
                var point = crs.latLngToPoint(latlng, level.zoom).subtract(level.origin);
                return (index ? 'L' : 'M') + point.x.toFixed(1) + ' ' + point.y.toFixed(1);
            }).join('') + 'Z';
        }).join('');
        return path ? 'path(evenodd, "' + path + '")' : CLIP_NOTHING;
    }

    // Cut a tile layer to the coverage outline (T22, see the top of this file).
    function clipToCoverage(layer) {
        var state = {rings: null, failed: false};
        function clipLevel(level) {
            if (!layer._map || !level || !level.el) {
                return;
            }
            if (state.failed) {
                level.el.style.clipPath = '';
            } else if (!state.rings) {
                level.el.style.clipPath = CLIP_NOTHING;
            } else {
                level.el.style.clipPath = levelClipPath(layer._map.options.crs, state.rings,
                                                        level);
            }
        }
        function clipAllLevels() {
            Object.keys(layer._levels || {}).forEach(function (zoom) {
                clipLevel(layer._levels[zoom]);
            });
        }
        // GridLayer's hook, called with every new level (a no-op in Leaflet 1.9.4).
        layer._onCreateLevel = clipLevel;
        layer.on('add', function () {
            loadCoverage().then(function (rings) {
                state.rings = rings;
                clipAllLevels();
            }, function (error) {
                if (!state.failed) {
                    console.error('find-artek-map-layers: coverage outline not loaded, ' +
                                  'topographic map not clipped', error);
                }
                state.failed = true;
                clipAllLevels();
            });
        });
        return layer;
    }

    // `overlay`: false for a base layer, true for an overlay (drawn above the base layer).
    // `clip`: true cuts the layer to the coverage outline (clipToCoverage).
    function dataforsyningenWms(url, layerName, overlay, clip) {
        return function (options) {
            var layer = L.tileLayer.wms(url, {
                layers: layerName,
                styles: '',
                format: 'image/png',
                // Always transparent (T16): base layers too, so the Arctic SDI underlay shows
                // where the service has no data (outside Greenland).
                transparent: true,
                version: '1.3.0',
                // No `crs`: Leaflet requests the map CRS (EPSG:3574).
                tileSize: WMS_TILE_SIZE,
                maxZoom: options.maxZoom,
                attribution: DATAFORSYNINGEN_ATTRIBUTION,
                zIndex: overlay ? OVERLAY_Z_INDEX : BASE_Z_INDEX,
                // Unknown options become WMS query parameters: `token=<value>`.
                token: options.token,
            });
            return clip ? clipToCoverage(layer) : layer;
        };
    }

    // zIndex: BASE_Z_INDEX as a chosen base layer, UNDERLAY_Z_INDEX as the underlay.
    function arcticSdi(options, zIndex) {
        // WMTS REST: TileMatrix={z}, TileRow={y}, TileCol={x}; the map grid is this grid.
        return L.tileLayer(ARCTIC_SDI_URL, {
            tileSize: options.tileSize,
            minZoom: 0,
            maxNativeZoom: ARCTIC_SDI_MAX_NATIVE_ZOOM,   // scaled up beyond level 10
            maxZoom: options.maxZoom,
            attribution: 'Arctic SDI basemap',
            zIndex: zIndex,
        });
    }

    // Base layers; the first available one is the default.
    var BASE_LAYERS = [
        {id: 'topographic', name: 'Topographic map (Dataforsyningen)', needsToken: true,
         create: dataforsyningenWms(TOPO_WMS, 'gl_aabent_land', false, true)},
        {id: 'satellite', name: 'Satellite (Dataforsyningen)', needsToken: true,
         create: dataforsyningenWms(SATELLITE_WMS, 'ortofoto', false)},
        {id: 'sentinel2-2022', name: 'Sentinel-2 2022 (Dataforsyningen)', needsToken: true,
         create: dataforsyningenWms(SATELLITE_WMS, 'sentinel2_10m_2022', false)},
        {id: 'arctic-sdi', name: 'Arctic basemap (Arctic SDI)', needsToken: false,
         create: function (options) { return arcticSdi(options, BASE_Z_INDEX); }},
    ];

    // Overlays (transparent), off by default.
    var OVERLAYS = [
        {id: 'place-names', name: 'Place names', needsToken: true,
         create: dataforsyningenWms(SATELLITE_WMS, 'stednavne', true)},
        {id: 'contours', name: 'Contours', needsToken: true,
         create: dataforsyningenWms(SATELLITE_WMS, 'hoejdekurver_og_koter', true)},
        {id: 'utm-grid', name: 'UTM grid', needsToken: true,
         create: dataforsyningenWms(SATELLITE_WMS, 'utm_net', true)},
    ];

    function build(entries, options) {
        return entries
            .filter(function (entry) { return options.token || !entry.needsToken; })
            .map(function (entry) {
                return {id: entry.id, name: entry.name, layer: entry.create(options)};
            });
    }

    function create(options) {
        options = options || {};
        var layerOptions = {
            token: options.token || '',
            tileSize: options.tileSize || 256,
            maxZoom: options.maxZoom || 18,
        };
        return {baseLayers: build(BASE_LAYERS, layerOptions),
                overlays: build(OVERLAYS, layerOptions),
                // Its own layer object, not the one in baseLayers: the layer control would
                // otherwise show Arctic SDI as chosen whenever it is on the map as the underlay.
                underlay: arcticSdi(layerOptions, UNDERLAY_Z_INDEX)};
    }

    // The Arctic SDI underlay is on the map exactly when there is a base layer and it is not
    // the Arctic SDI basemap.
    function updateUnderlay(map, underlay, baseEntry) {
        var wanted = !!baseEntry && baseEntry.id !== ARCTIC_SDI_ID;
        if (wanted && !map.hasLayer(underlay)) {
            underlay.addTo(map);
        } else if (!wanted && map.hasLayer(underlay)) {
            map.removeLayer(underlay);
        }
    }

    function rememberedBaseLayer() {
        try {
            return window.sessionStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return null;    // storage disabled
        }
    }

    function rememberBaseLayer(id) {
        try {
            window.sessionStorage.setItem(STORAGE_KEY, id);
        } catch (e) {
            // storage disabled or full: the default is used on the next page
        }
    }

    function addTo(map, options) {
        var layers = create(options);
        var wanted = rememberedBaseLayer();
        var active = layers.baseLayers.filter(function (entry) { return entry.id === wanted; })[0]
            || layers.baseLayers[0] || null;
        if (active) {
            active.layer.addTo(map);
        }
        updateUnderlay(map, layers.underlay, active);
        if (!(options && options.token) && map.attributionControl) {
            map.attributionControl.addAttribution(NO_TOKEN_NOTE);
        }

        var control = null;
        if (layers.baseLayers.length > 1 || layers.overlays.length > 0) {
            var bases = {};
            var overlays = {};
            layers.baseLayers.forEach(function (entry) { bases[entry.name] = entry.layer; });
            layers.overlays.forEach(function (entry) { overlays[entry.name] = entry.layer; });
            control = L.control.layers(bases, overlays, {collapsed: true}).addTo(map);

            map.on('baselayerchange', function (event) {
                layers.baseLayers.forEach(function (entry) {
                    if (entry.layer === event.layer) {
                        rememberBaseLayer(entry.id);
                        updateUnderlay(map, layers.underlay, entry);
                    }
                });
            });
        }

        return {baseLayers: layers.baseLayers, overlays: layers.overlays,
                control: control, active: active, underlay: layers.underlay};
    }

    window.FindArtekMapLayers = {
        STORAGE_KEY: STORAGE_KEY,
        ARCTIC_SDI_ID: ARCTIC_SDI_ID,
        COVERAGE_PATH: COVERAGE_PATH,
        coverageUrl: function () { return COVERAGE_URL; },
        coverageRings: coverageRings,
        levelClipPath: levelClipPath,
        NO_TOKEN_NOTE: NO_TOKEN_NOTE,
        BASE_LAYERS: BASE_LAYERS,
        OVERLAYS: OVERLAYS,
        create: create,
        addTo: addTo,
    };
})();
