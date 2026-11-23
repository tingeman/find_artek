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
 * To add another provider, add an entry to BASE_LAYERS or OVERLAYS:
 * {id, name, needsToken, create(options) -> L.Layer}. Entries with needsToken are left out
 * (and nothing is requested from them) when the page has no token. The first available base
 * layer is the default.
 *
 * Exposes window.FindArtekMapLayers:
 *   BASE_LAYERS, OVERLAYS        the configuration below
 *   create(options) -> {baseLayers: [{id, name, layer}], overlays: [...]}
 *       options.token      Dataforsyningen token ('' or undefined: no Dataforsyningen layer)
 *       options.tileSize   tile size of the map grid (256)
 *       options.maxZoom    highest zoom level of the map CRS
 *   addTo(map, options) -> {baseLayers, overlays, control, active}
 *       Adds the remembered (or default) base layer and, when there is something to choose,
 *       an L.control.layers switcher. Remembers the chosen base layer in localStorage (only
 *       its id, never the token). Without a token the attribution says that more layers need
 *       the token; without any base layer the map keeps a plain background.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'findArtekMap.baseLayer';
    var NO_TOKEN_NOTE = 'More map layers need FA_DATAFORSYNINGEN_TOKEN';

    // WMS tiles may have any size; 512 px means fewer requests than the grid's 256 px.
    var WMS_TILE_SIZE = 512;

    var SATELLITE_WMS = 'https://api.dataforsyningen.dk/wms/gl_satellitfoto';
    var TOPO_WMS = 'https://api.dataforsyningen.dk/wms/gl_aabent_land';
    var DATAFORSYNINGEN_ATTRIBUTION =
        '&copy; Styrelsen for Dataforsyning og Infrastruktur / Klimadatastyrelsen';

    var ARCTIC_SDI_URL =
        'https://basemap.arctic-sdi.org/mapcache/wmts/1.0.0/arctic_cascading/default/3574/{z}/{y}/{x}.png';
    var ARCTIC_SDI_MAX_NATIVE_ZOOM = 10;

    function dataforsyningenWms(url, layerName, transparent) {
        return function (options) {
            return L.tileLayer.wms(url, {
                layers: layerName,
                styles: '',
                format: 'image/png',
                transparent: transparent,
                version: '1.3.0',
                // No `crs`: Leaflet requests the map CRS (EPSG:3574).
                tileSize: WMS_TILE_SIZE,
                maxZoom: options.maxZoom,
                attribution: DATAFORSYNINGEN_ATTRIBUTION,
                zIndex: transparent ? 10 : 1,
                // Unknown options become WMS query parameters: `token=<value>`.
                token: options.token,
            });
        };
    }

    function arcticSdi(options) {
        // WMTS REST: TileMatrix={z}, TileRow={y}, TileCol={x}; the map grid is this grid.
        return L.tileLayer(ARCTIC_SDI_URL, {
            tileSize: options.tileSize,
            minZoom: 0,
            maxNativeZoom: ARCTIC_SDI_MAX_NATIVE_ZOOM,   // scaled up beyond level 10
            maxZoom: options.maxZoom,
            attribution: 'Arctic SDI basemap',
            zIndex: 1,
        });
    }

    // Base layers; the first available one is the default.
    var BASE_LAYERS = [
        {id: 'topographic', name: 'Topographic map (Dataforsyningen)', needsToken: true,
         create: dataforsyningenWms(TOPO_WMS, 'gl_aabent_land', false)},
        {id: 'satellite', name: 'Satellite (Dataforsyningen)', needsToken: true,
         create: dataforsyningenWms(SATELLITE_WMS, 'ortofoto', false)},
        {id: 'sentinel2-2022', name: 'Sentinel-2 2022 (Dataforsyningen)', needsToken: true,
         create: dataforsyningenWms(SATELLITE_WMS, 'sentinel2_10m_2022', false)},
        {id: 'arctic-sdi', name: 'Arctic basemap (Arctic SDI)', needsToken: false,
         create: arcticSdi},
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
                overlays: build(OVERLAYS, layerOptions)};
    }

    function rememberedBaseLayer() {
        try {
            return window.localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return null;    // storage disabled
        }
    }

    function rememberBaseLayer(id) {
        try {
            window.localStorage.setItem(STORAGE_KEY, id);
        } catch (e) {
            // storage disabled or full: the default is used next time
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
                    }
                });
            });
        }

        return {baseLayers: layers.baseLayers, overlays: layers.overlays,
                control: control, active: active};
    }

    window.FindArtekMapLayers = {
        STORAGE_KEY: STORAGE_KEY,
        NO_TOKEN_NOTE: NO_TOKEN_NOTE,
        BASE_LAYERS: BASE_LAYERS,
        OVERLAYS: OVERLAYS,
        create: create,
        addTo: addTo,
    };
})();
