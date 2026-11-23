// Report page: the map shows the report's features (plan "features" T3, FindArtekMap).
// The report id comes from the map element's data-publication-id.
document.addEventListener('DOMContentLoaded', function () {
    const element = document.getElementById('map');
    if (!element) {
        return;
    }
    const findArtekMap = new FindArtekMap({element: element, mode: 'report'});
    findArtekMap.loadFeatures().catch(function (error) {
        console.error('Could not load the features of the report:', error);
    });
});


// This block toggles the abstract between collapsed and expanded
(function () {
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

    // Only add event listeners if the buttons exist
    if (abstractExpandBtn) {
        abstractExpandBtn.addEventListener("click", toggleAbstract);
    }
    if (abstractCollapseBtn) {
        abstractCollapseBtn.addEventListener("click", toggleAbstract);
    }

})();
