// ============
// Initialization
// ============
document.addEventListener("DOMContentLoaded", function (event) {
  // This block will run when the DOM is loaded.
  main();
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

    const response = await fetch('/publications/api/feature/');
    const featureData = await response.json();

    // To hide the overlay
    loadingOverlay.style.display = 'none';

    myMapClass.addFeatureDataToMap(map, featureData);

  } catch (error) {
    console.error("Error initializing map or fetching feature data: ", error);
  }

}
