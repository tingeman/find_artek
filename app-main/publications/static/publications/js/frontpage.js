// ============
// Initialization
// ============
document.addEventListener("DOMContentLoaded", function (event) {
    // This block will run when the DOM is loaded.
    console.log("DOM fully loaded and parsed - frontpage.js");
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
    const myReportsClass = new MyReportsClass();

    try {

        // load and cache feature data in background
        await myMapClass.getFeatureData()

        // load and cache reports data in background
        const topics = [
            null, // all
            'Infrastruktur',
            'Miljø',
            'Energi',
            'Byggeri',
            'Geoteknik',
            'Samfund',
            'Råstoffer',
        ]

        for (let i = 0; i < topics.length; i++) {
            const topic = topics[i];
            await myReportsClass.getReportsData(JS_URL_PREFIX + '/api/report/', topic);
        }



    } catch (error) {
        console.error("Error: ", error);
    }

}