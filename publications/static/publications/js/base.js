// fires when the DOM is loaded
document.addEventListener("DOMContentLoaded", function (event) {



    // expands and collapses the mobile menu starts here
    const mobileMenuExpanded = document.getElementById("mobile-menu-expanded");
    mobileMenuExpanded.style.display = "none";

    

    
    // Attach a click event listener to the body
    document.body.addEventListener('click', function(event) {
        // Check if the click was outside of the box
        if (!mobileMenuExpanded.contains(event.target) && (mobileMenuExpanded.style.display === "block")) {
            
            document.getElementById("mobile-menu").classList.toggle("change");
            mobileMenuExpanded.style.display = "none";
            main.classList.remove("blur");

        }
    });





    document.getElementById("mobile-menu").addEventListener("click", function () {
        this.classList.toggle("change");


        if (mobileMenuExpanded.style.display === "none") {
            main.classList.add("blur");


            // sleep for 0.5 seconds
            setTimeout(function () {
            mobileMenuExpanded.style.display = "block";
            }, 1);
            
        } else {
            mobileMenuExpanded.style.display = "none";
            main.classList.remove("blur");
        }

    });


    // expands and collapses the mobile menu ends here
});

