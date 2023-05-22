document.addEventListener("DOMContentLoaded", function (event) {


    const loadingOverlay = document.getElementById('loading-overlay');
    const reportsTableList = document.getElementById('reports-table-list');


    // from http://localhost/publications/person/2/ extract 2
    const personId = window.location.pathname.split('/')[3];


    // Gloval variables
    let $ = {
        reportsTableList: reportsTableList,
        myReportsClass: new MyReportsClass(loadingOverlay, reportsTableList, '/publications/api/reports/'),
        filter: { personId: personId }
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