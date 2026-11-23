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
 * Topographic map over the underlay (T19): the topographic WMS (gl_aabent_land) returns opaque
 * white around Greenland despite TRANSPARENT=TRUE, which hid the underlay there. Its layer gets
 * the class BLEND_UNDERLAY_CLASS, and css/find-artek-map.css gives that layer
 * `mix-blend-mode: multiply`: white x underlay = underlay, so the white areas show the Arctic
 * basemap. This works because all tile layers are in Leaflet's tile pane, which is positioned
 * with a z-index and therefore its own stacking context, i.e. an isolated blending group: the
 * topographic layer blends only with what the tile pane has drawn below it (the underlay),
 * never with the map background or the page. Overlays (above) and the features (other panes)
 * are not blended. Satellite and Sentinel-2 have no class and are drawn normally; with the
 * Arctic SDI basemap chosen there is no underlay and no topographic layer, so nothing changes.
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

    // Class of a base layer whose white areas let the underlay show through (T19, see above;
    // the rule is in css/find-artek-map.css). Only the topographic map has it.
    var BLEND_UNDERLAY_CLASS = 'fa-blend-underlay';

    var SATELLITE_WMS = 'https://api.dataforsyningen.dk/wms/gl_satellitfoto';
    var TOPO_WMS = 'https://api.dataforsyningen.dk/wms/gl_aabent_land';
    var DATAFORSYNINGEN_ATTRIBUTION =
        '&copy; Styrelsen for Dataforsyning og Infrastruktur / Klimadatastyrelsen';

    var ARCTIC_SDI_URL =
        'https://basemap.arctic-sdi.org/mapcache/wmts/1.0.0/arctic_cascading/default/3574/{z}/{y}/{x}.png';
    var ARCTIC_SDI_MAX_NATIVE_ZOOM = 10;

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
        BLEND_UNDERLAY_CLASS: BLEND_UNDERLAY_CLASS,
        NO_TOKEN_NOTE: NO_TOKEN_NOTE,
        BASE_LAYERS: BASE_LAYERS,
        OVERLAYS: OVERLAYS,
        create: create,
        addTo: addTo,
    };
})();
