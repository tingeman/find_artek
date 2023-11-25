// ============
// Initialization
// ============
document.addEventListener("DOMContentLoaded", function (event) {
    // This block will run when the DOM is loaded.
    console.log("DOM fully loaded and parsed - base.js");

    base().catch(error => {
      console.error("Error initializing map or fetching feature data: ", error);
      // handle error, for example by showing an error message to the user
    });
});
  
  
  
  








// ============
// Main - base
// ============
async function base() {

    // expands and collapses the mobile menu starts here
    const mobileMenuExpanded = document.getElementById("mobile-menu-expanded");
    const mobileMenuCollapsed = document.getElementById("mobile-menu-collapsed");
    const main = document.getElementById("main");
    const body = document.body;
    mobileMenuExpanded.style.display = "none";

    // handle the mobile menu starts here //
    // close the mobile menu when clicking outside of it
    body.addEventListener('click', function(event) {

        // check if the click what inside the mobile menu icon - mobile-menu-collapsed
        if (mobileMenuCollapsed.contains(event.target)) {
            console.log("clicked inside the mobile menu icon");

            // if the mobile menu is collapsed then
            // blur the main content - background content
            // and 
            // change the mobile menu icon to close icon
            // and 
            // display the mobile menu
            // else
            // hide the mobile menu
            if (mobileMenuExpanded.style.display === "none") {
                main.classList.add("blur");
                mobileMenuCollapsed.classList.add("change");
                mobileMenuExpanded.style.display = "block";

            } else {
                mobileMenuExpanded.style.display = "none";
                mobileMenuCollapsed.classList.remove("change"); // change the mobile menu icon to close icon
                main.classList.remove("blur");
            }

        } 
        else if (mobileMenuExpanded.contains(event.target)) {
            console.log("clicked inside the mobile menu");

            // if the mobile menu is collapsed then
        }
        else {
            console.log("clicked outside the mobile menu");

            // if the mobile menu is expanded then
            // remove the blur effect
            // and 
            // change the mobile menu icon to hamburger icon
            // and 
            // collapse the mobile menu          
            if (mobileMenuExpanded.style.display === "block") {
                main.classList.remove("blur");
                mobileMenuCollapsed.classList.remove("change");
                mobileMenuExpanded.style.display = "none";
            }

        }
        
        
        // if (!mobileMenuExpanded.contains(event.target) && (mobileMenuExpanded.style.display === "block")) {
            
        //     mobileMenuExpanded.classList.toggle("change");
        //     mobileMenuExpanded.style.display = "none";
        //     main.classList.remove("blur");

        // }
    });

    
    // mobileMenuCollapsed.addEventListener("click", function () {
    //     this.classList.toggle("change");


    //     if (mobileMenuExpanded.style.display === "none") {
    //         main.classList.add("blur");

    //         // mobileMenuExpanded.style.display = "block";
    //         // sleep for 0.5 seconds
    //         setTimeout(function () {
    //         mobileMenuExpanded.style.display = "block";
    //         }, 1);
            
    //     } else {
    //         mobileMenuExpanded.style.display = "none";
    //         main.classList.remove("blur");
    //     }

    // });

    // handle the mobile menu starts here //
}
