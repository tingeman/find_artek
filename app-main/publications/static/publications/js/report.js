// =============================================================================
// Initialization
// =============================================================================
document.addEventListener("DOMContentLoaded", function (event) {
    // This block will run when the DOM is loaded.
    console.log('Testing console log from report.js');
    main().catch(error => {
        console.error("Error: ", error);
        // handle error, for example by showing an error message to the user
    });
});



// // ============
// // Main
// // ============
async function main() {
    const mapDiv = document.getElementById('map');

    // from https://arctic.sustain.dtu.dk/find/publications/report/274/ extract 274 after removing any trailing slashes
    const path = window.location.pathname.replace(/\/$/, ''); // remove any trailing slashes
    const parts = path.split('/');
    const reportId = parts[parts.length - 1]; 
    
    console.log('reportId:', reportId);


    const myMapClass = new MyMapClass(mapDiv);

    
    // try {
    map = await myMapClass.initialize();
    
    // Fetch the JSON data from /publications/api/feature/
    const featureData = await myMapClass.getFeatures({report: reportId});

    // console.log('featureData:', featureData); 

    // add the feature data to the map
    myMapClass.addFeatureDataToMap(featureData, true);

    // q: get the url the path from the url without the domain name or parameters or protocol
    // a: window.location.pathname
    // const path = window.location.pathname;
    // const parts = path.split('/');
    // const id = parts[parts.length - 2]; // -1 for the last element (which is an empty string after the trailing slash), -2 for the second to last element

    // const params = new URLSearchParams({
    //     publication_id: id // Replace with actual value or variable
    // });


    // const response = await fetch(URL_PREFIX + `/api/feature/?${params}`);
    // const featureData = await response.json();

    // myMapClass.addFeatureDataToMap(map, featureData, true);

    // // } catch (error) {
    // //     console.error("Error initializing map or fetching feature data: ", error);
    // // }

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