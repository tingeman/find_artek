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

  const myMapClass = new MyMapClass();
  
  try {
    
    map = await myMapClass.initialize();

    // Fetch the JSON data from /publications/api/feature/
    const loadingOverlay = document.getElementById('loading-overlay');
    
    // To show the overlay
    loadingOverlay.style.display = 'flex';

    // get feature data
    const featureData = await myMapClass.getFeatureData()

    // To hide the overlay
    loadingOverlay.style.display = 'none';

    myMapClass.addFeatureDataToMap(map, featureData);

  } catch (error) {
    console.error("Error initializing map or fetching feature data: ", error);
  }

}
