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
 * Topographic map over the underlay (T19, again since T23): the topographic WMS (gl_aabent_land)
 * returns opaque white outside its coverage (Greenland's land and a blue sea band of roughly
 * 15-40 km along the coast) despite TRANSPARENT=TRUE, which would hide the underlay there. Its
 * layer gets the class BLEND_UNDERLAY_CLASS, and css/find-artek-map.css gives that layer
 * `mix-blend-mode: multiply`: white x underlay = underlay, so the white areas show the Arctic
 * basemap. All tile layers are in Leaflet's tile pane, which is positioned with a z-index and
 * therefore its own stacking context (an isolated blending group): the topographic layer blends
 * only with what the tile pane has drawn below it (the underlay), never with the map background
 * or the page. The topographic layer itself is drawn whole (no clip), so town names that run
 * into the sea, offshore islands and Dataforsyningen's own coastline are all kept.
 *
 * Underlay cut out inside the coverage (T23): multiplying alone lets the underlay show through
 * inside Greenland too (double coastlines, ghost place names and airport icons; T22's finding).
 * So while the topographic map is the chosen base layer, the underlay is clipped to the OUTSIDE
 * of a coverage outline: Greenland from Natural Earth 10m land (public domain) with fjords and
 * bays up to about 80 km wide filled, buffered 12 km seaward, other large landmasses cut out
 * (data/greenland_topo_coverage.geojson, made by `manage.py make_greenland_coverage`). Inside
 * the outline nothing of the Arctic basemap is drawn and the topographic map has no backdrop;
 * outside, the underlay shows (through the topographic map's white border). The outline stays
 * inside the topographic map's blue sea band, so no white strip is left between the two. With
 * satellite or Sentinel-2 the underlay is not clipped (their areas without data are transparent,
 * owner's check after T16); with the Arctic SDI basemap there is no underlay.
 *
 * How (coverageClip): Leaflet draws a tile layer's tiles in one container per zoom level
 * ("level"). A level's coordinates never change while it exists: map pixels at the level's zoom
 * minus level.origin; Leaflet moves it on pan and scales it during the zoom animation with a CSS
 * transform. GridLayer calls _onCreateLevel(level) for every new level, and there the level gets
 * a CSS `clip-path: path(evenodd, "<rectangle> <outline rings>")` in those coordinates: a
 * rectangle larger than the whole tile grid at that zoom, minus the outline (even-odd). The clip
 * moves and scales together with the tiles, so it stays aligned on pan and during zoom
 * animations, and nothing runs on pan or zoom except one projection of the outline (a few
 * hundred points) when a new level is made. On a base layer change the clip of the existing
 * levels is set again. The outline is fetched once per page (the versioned static URL next to
 * this script, so it is cached like the script), and only when the topographic map is first
 * chosen. Until it has arrived the underlay is hidden completely (CLIP_NOTHING); if it can't be
 * loaded the underlay is drawn unclipped (ghost names inside Greenland, as in T19) and an error
 * is logged once. No extra tile requests.
 *
 * To add another provider, add an entry to BASE_LAYERS or OVERLAYS:
 * {id, name, needsToken, create(options) -> L.Layer}. Entries with needsToken are left out
 * (and nothing is requested from them) when the page has no token. The first available base
 * layer is the default.
 *
 * Exposes window.FindArtekMapLayers:
 *   BASE_LAYERS, OVERLAYS        the configuration below
 *   create(options) -> {baseLayers: [{id, name, layer}], overlays: [...], underlay: L.Layer,
 *                       coverageClip: {setActive(bool), isActive()}}
 *       options.token      Dataforsyningen token ('' or undefined: no Dataforsyningen layer)
 *       options.tileSize   tile size of the map grid (256)
 *       options.maxZoom    highest zoom level of the map CRS
 *   addTo(map, options) -> {baseLayers, overlays, control, active, underlay, coverageClip}
 *       Adds the remembered (or default) base layer, the Arctic SDI underlay below it (unless
 *       the base layer is the Arctic SDI basemap; clipped to the outside of the coverage
 *       outline while the topographic map is chosen, T23) and, when there is something to
 *       choose, an L.control.layers switcher. Remembers the base layer the user picks in the
 *       switcher in sessionStorage (only its id, never the token): it is kept while the user
 *       moves between map pages in the same browser tab, and a new visit starts with the
 *       default again (T11). Until T11 the choice was kept in localStorage for good, so a
 *       layer once picked (e.g. the Arctic SDI basemap) came back on every page and every
 *       later visit, which looked like a wrong default. Without a token the attribution says
 *       that more layers need the token; without any base layer the map keeps a plain
 *       background.
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

    var TOPOGRAPHIC_ID = 'topographic';

    // Class of the base layer whose white areas let the underlay show through (T19, T23; see
    // above; the rule is in css/find-artek-map.css). Only the topographic map has it.
    var BLEND_UNDERLAY_CLASS = 'fa-blend-underlay';

    // Coverage outline of the topographic map (T22, T23; see above): a static file next to this
    // script; the URL is taken from this script's own URL, so it has the same prefix and the same
    // ?v= version. null when the script URL is unknown (the underlay is then not clipped).
    var SCRIPT_PATH = 'js/map/find-artek-map-layers.js';
    var COVERAGE_PATH = 'data/greenland_topo_coverage.geojson';
    var COVERAGE_URL = coverageUrl(document.currentScript);
    // Clip of an underlay level while the outline is loading: nothing visible (an empty path).
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

    // The CSS clip-path of an underlay level (T23): everything except the outline. A rectangle
    // one world wider than the tile grid at level.zoom on every side (the grid is `worldSize`
    // pixels square from map pixel 0, 0), then the outline rings, in the level's coordinates
    // (map pixels at level.zoom minus level.origin); even-odd, so the inside of the outline is
    // cut out. The underlay's levels go up to its maxNativeZoom (10), so the numbers stay below
    // a million pixels.
    function levelClipPath(crs, rings, level, worldSize) {
        function move(x, y) {
            var point = L.point(x, y).subtract(level.origin);
            return point.x.toFixed(1) + ' ' + point.y.toFixed(1);
        }
        var low = -worldSize;
        var high = 2 * worldSize;
        var path = 'M' + move(low, low) + 'L' + move(high, low) + 'L' + move(high, high) +
            'L' + move(low, high) + 'Z';
        path += rings.map(function (ring) {
            return ring.map(function (latlng, index) {
                var point = crs.latLngToPoint(latlng, level.zoom).subtract(level.origin);
                return (index ? 'L' : 'M') + point.x.toFixed(1) + ' ' + point.y.toFixed(1);
            }).join('') + 'Z';
        }).join('');
        return 'path(evenodd, "' + path + '")';
    }

    // Width in map pixels of the whole tile grid at `zoom`: level 0 is one tile over the grid
    // extent (find-artek-map.js), and each zoom level doubles it.
    function worldPixelSize(crs, tileSize, zoom) {
        return tileSize * crs.scale(zoom) / crs.scale(0);
    }

    // Clip a tile layer (the underlay) to the outside of the coverage outline while active
    // (T23, see the top of this file). Returns {setActive(bool), isActive()}, also kept as
    // layer.coverageClip; inactive (the default) leaves the layer unclipped.
    function coverageClip(layer) {
        var state = {active: false, requested: false, rings: null, failed: false};
        function clipLevel(level) {
            if (!layer._map || !level || !level.el) {
                return;
            }
            if (!state.active || state.failed) {
                level.el.style.clipPath = '';
            } else if (!state.rings) {
                level.el.style.clipPath = CLIP_NOTHING;
            } else {
                var crs = layer._map.options.crs;
                level.el.style.clipPath = levelClipPath(
                    crs, state.rings, level,
                    worldPixelSize(crs, layer.getTileSize().x, level.zoom));
            }
        }
        function clipAllLevels() {
            Object.keys(layer._levels || {}).forEach(function (zoom) {
                clipLevel(layer._levels[zoom]);
            });
        }
        function load() {
            state.requested = true;
            loadCoverage().then(function (rings) {
                state.rings = rings;
                clipAllLevels();
            }, function (error) {
                console.error('find-artek-map-layers: coverage outline not loaded, ' +
                              'Arctic SDI underlay not clipped', error);
                state.failed = true;
                clipAllLevels();
            });
        }
        // GridLayer's hook, called with every new level (a no-op in Leaflet 1.9.4).
        layer._onCreateLevel = clipLevel;
        layer.coverageClip = {
            setActive: function (active) {
                state.active = !!active;
                if (state.active && !state.requested) {
                    load();
                }
                clipAllLevels();
            },
            isActive: function () { return state.active; },
        };
        return layer.coverageClip;
    }

    // `overlay`: false for a base layer, true for an overlay (drawn above the base layer).
    // `className`: CSS class of the layer's container (Leaflet's GridLayer option, not sent to
    // the WMS server); '' or left out for none.
    function dataforsyningenWms(url, layerName, overlay, className) {
        return function (options) {
            return L.tileLayer.wms(url, {
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
                className: className || '',
                // Unknown options become WMS query parameters: `token=<value>`.
                token: options.token,
            });
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
         create: dataforsyningenWms(TOPO_WMS, 'gl_aabent_land', false, BLEND_UNDERLAY_CLASS)},
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
        var result = {baseLayers: build(BASE_LAYERS, layerOptions),
                      overlays: build(OVERLAYS, layerOptions),
                      // Its own layer object, not the one in baseLayers: the layer control would
                      // otherwise show Arctic SDI as chosen whenever it is on the map as the
                      // underlay.
                      underlay: arcticSdi(layerOptions, UNDERLAY_Z_INDEX)};
        result.coverageClip = coverageClip(result.underlay);
        return result;
    }

    // The Arctic SDI underlay is on the map exactly when there is a base layer and it is not
    // the Arctic SDI basemap. It is clipped to the outside of the coverage outline exactly when
    // the base layer is the topographic map (T23); the clip is set before the underlay is
    // added, so its first level is made with the right clip, and set again on the existing
    // levels when the base layer changes.
    function updateUnderlay(map, underlay, baseEntry) {
        var wanted = !!baseEntry && baseEntry.id !== ARCTIC_SDI_ID;
        if (underlay.coverageClip) {
            underlay.coverageClip.setActive(!!baseEntry && baseEntry.id === TOPOGRAPHIC_ID);
        }
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
                control: control, active: active, underlay: layers.underlay,
                coverageClip: layers.coverageClip};
    }

    window.FindArtekMapLayers = {
        STORAGE_KEY: STORAGE_KEY,
        ARCTIC_SDI_ID: ARCTIC_SDI_ID,
        TOPOGRAPHIC_ID: TOPOGRAPHIC_ID,
        BLEND_UNDERLAY_CLASS: BLEND_UNDERLAY_CLASS,
        COVERAGE_PATH: COVERAGE_PATH,
        coverageUrl: function () { return COVERAGE_URL; },
        coverageRings: coverageRings,
        levelClipPath: levelClipPath,
        worldPixelSize: worldPixelSize,
        NO_TOKEN_NOTE: NO_TOKEN_NOTE,
        BASE_LAYERS: BASE_LAYERS,
        OVERLAYS: OVERLAYS,
        create: create,
        addTo: addTo,
    };
})();
