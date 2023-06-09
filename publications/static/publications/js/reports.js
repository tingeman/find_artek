document.addEventListener("DOMContentLoaded", function (event) {



    // Here we are getting the elements from the DOM
    const loadingOverlay = document.getElementById('loading-overlay');
    const reportsTableList = document.getElementById('reports-table-list');
    const totalReportsNumber = document.getElementById('total-reports-number');

    // Get topic get parameter from url
    const urlParams = new URLSearchParams(window.location.search);
    const topic = urlParams.get('topic');
    if (!topic) {
        throw new Error('Topic parameter not found in URL');
    }

    // from http://localhost/publications/person/2/ extract 2
    const personId = window.location.pathname.split('/')[3];

    const apiEndpoint = '/publications/api/reports/';

    // Globaæl variables
    let $ = {
        reportsTableList: reportsTableList,
        myReportsClass: new MyReportsClass(
            loadingOverlay, 
            reportsTableList, 
            totalReportsNumber, 
            apiEndpoint
            ),
        filter: {topic: topic}
    }





    // This block will run when the DOM is loaded.
    main($).then((finished) => {
        if (finished) {
            console.log("main() is done executing.");
        }
    });

});






// ============
// Main
// ============
async function main($) {
    $.myReportsClass.getReports($.filter)
}

// ============
// Classes
// ============