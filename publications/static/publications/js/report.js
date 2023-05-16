










// ----------------- encapsulated code (not part of the main) starts here ----------------- //

// This block toggles the abstract between collapsed and expanded
(function () {
    // get button, and 
    const abstractExpandBtn = document.getElementById("abstract-expand-btn");
    const abstractCollapseBtn = document.getElementById("abstract-collapse-btn");


    // add event listener
    abstractExpandBtn.addEventListener("click", toggleAbstract);
    abstractCollapseBtn.addEventListener("click", toggleAbstract);


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
})();


// ----------------- encapsulated code (not part of the main) ends here ----------------- //