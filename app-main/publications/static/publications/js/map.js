// ============
// Initialization
// ============
document.addEventListener("DOMContentLoaded", function (event) {
    // This block will run when the DOM is loaded.
    console.log("DOM fully loaded and parsed - map.js");
    main().catch(error => {
        console.error("Error initializing map or fetching feature data: ", error);
        // handle error, for example by showing an error message to the user
    });
});




// // ============
// // Main
// // ============
async function main() {
    const mapDiv = document.getElementById('map');

    const myMapClass = new MyMapClass(mapDiv);

    // try {

    map = await myMapClass.initialize();

    // Fetch the JSON data from /publications/api/feature/
    const loadingOverlay = document.getElementById('loading-overlay');

    // To show the overlay
    loadingOverlay.style.display = 'flex';

    // Fetch the JSON data from /publications/api/feature/
    const featureData = await myMapClass.getFeatures();

    // To hide the overlay
    loadingOverlay.style.display = 'none';

    // add the feature data to the map
    myMapClass.addFeatureDataToMap(featureData, false);

    // } catch (error) {
    //   console.error("Error initializing map or fetching feature data: ", error);
    // }

}
