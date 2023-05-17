window.onload = function () {
    initMap();

};










// ----------------- encapsulated code that do it's own thing (not part of the main). Starts here ----------------- //

// This block toggles the abstract between collapsed and expanded
(function () {
    // get button, and 
    const abstractExpandBtn = document.getElementById("abstract-expand-btn");
    const abstractCollapseBtn = document.getElementById("abstract-collapse-btn");


    function toggleAbstract() {
        const collapsed = document.getElementById("abstract-collapsed");
        const expanded = document.getElementById("abstract-expanded");

        if (collapsed.className === "visible") {
            collapsed.className = "hidden";
            expanded.className = "visible";
        } else {
            collapsed.className = "visible";
            expanded.className = "hidden";
        }
    }

    // Execution starts here
    abstractExpandBtn.addEventListener("click", toggleAbstract);
    abstractCollapseBtn.addEventListener("click", toggleAbstract);

})();


// create feature map
function initMap() {

    function getURLParameters(url) {
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



    const createMap = (id, lat, lng, zoom) => {
        return L.map(id).setView([lat, lng], zoom);
    };


    const addTileLayer = (map, url, options) => {
        L.tileLayer(url, options).addTo(map);
    };










    // Execution starts here
    var params = getURLParameters(window.location.href)
    var lat = params.lat;
    var lng = params.lng;
    var zoom = params.zoom;

    // if lat lng or zsom are not defined, use default values
    if (!lat || !lng || !zoom) {
        lat = 76.31;
        lng = -40.43;
        zoom = 3;
    }
    
    const map = createMap('map', lat, lng, zoom);
    
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

    addTileLayer(map, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 29,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    });

    




};

// ----------------- encapsulated code that do it's own thing (not part of the main). Ends here ----------------- //