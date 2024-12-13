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

        // load and cache reports data in background
        const topics = [
            'Infrastruktur',
            'Miljø',
            'Energi',
            'Byggeri',
            'Geoteknik',
            'Samfund',
            'Råstoffer',
            null, // all
        ]

        for (let i = 0; i < topics.length; i++) {
            await myReportsClass.getReportsData(URL_PREFIX + '/api/report/', {topic: topics[i]});
        }

        // load and cache feature data in background
        await myMapClass.getFeatureData()

    } catch (error) {
        console.error("Error: ", error);
    }

}