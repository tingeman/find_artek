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

        // q: get the url the path from the url without the domain name or parameters or protocol
        // a: window.location.pathname
        const path = window.location.pathname;
        const parts = path.split('/');
        const id = parts[parts.length - 2]; // -1 for the last element (which is an empty string after the trailing slash), -2 for the second to last element

        const params = new URLSearchParams({
            publication_id: id // Replace with actual value or variable
        });


        const response = await fetch(`/publications/api/feature/?${params}`);
        const featureData = await response.json();

        myMapClass.addFeatureDataToMap(map, featureData, true);

    } catch (error) {
        console.error("Error initializing map or fetching feature data: ", error);
    }
}

// ============
// Classes
// ============