// ============
// Initialization
// ============
document.addEventListener("DOMContentLoaded", function (event) {
  // This block will run when the DOM is loaded.
  main().catch(error => {
    console.error("Error initializing map or fetching feature data: ", error);
    // handle error, for example by showing an error message to the user
  });
});



// // ============
// // Functions
// // ============
// async function getFeatureData() {
//   // Try to get the data from session storage first
//   let featureData = sessionStorage.getItem('featureData');
  
//   if (featureData) {
//     // If data exists in storage, parse it from the string and return
//     return JSON.parse(featureData);
//   } else {
//     // If not, fetch the data from the endpoint
//     const response = await fetch('/api/feature/');
//     if (!response.ok) {
//       throw new Error(`HTTP error! status: ${response.status}`);
//     }
//     featureData = await response.json();
    
//     // Store the data in session storage as a string
//     sessionStorage.setItem('featureData', JSON.stringify(featureData));
    
//     // Return the fetched data
//     return featureData;
//   }
// }

















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
