










// ----------------- encapsulated code that do it's own thing (not part of the main). Starts here ----------------- //

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


// ----------------- encapsulated code that do it's own thing (not part of the main). Ends here ----------------- //