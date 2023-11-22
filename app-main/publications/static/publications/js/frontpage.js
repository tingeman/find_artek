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
// // Main
// // ============
async function main() {

    const myMapClass = new MyMapClass();

    try {

        // load and cache feature data in background
        const featureData = await myMapClass.getFeatureData()



    } catch (error) {
        console.error("Error: ", error);
    }

}