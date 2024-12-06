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
// ----------------- encapsulated code that do it's own thing (not part of the main). Starts here ----------------- //
// ============

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

// ============
// ----------------- encapsulated code that do it's own thing (not part of the main). Ends here ----------------- //
// ============









// ============
// ----------------- classes and functions that are part of the main. Starts here ----------------- //
// ============


// ============
// ----------------- classes and functions that are part of the main. Ends here ----------------- //
// ============