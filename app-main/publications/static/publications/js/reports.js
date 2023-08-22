document.addEventListener("DOMContentLoaded", function (event) {



    // Here we are getting the elements from the DOM
    const loadingOverlay = document.getElementById('loading-overlay');
    const reportsTableList = document.getElementById('reports-table-list');
    const totalReportsNumber = document.getElementById('total-reports-number');
    

    const apiEndpoint = '/api/reports/';

    // check if get paramete 'topic' is present
    const urlParams = new URLSearchParams(window.location.search);
    let topic = urlParams.get('topic');
    // if topic is null or undefined, set it to 'all'
    if (topic === null || topic === undefined || topic.toLowerCase() === 'all') {
        topic = 'All';
    }
    

    // Global variables
    let $my = {
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
    main($my).then((finished) => {
        if (finished) {
            console.log("main() is done executing.");
        }
    });

});






// ============
// Main
// ============
async function main($my) {
    $my.myReportsClass.getReports($my.filter)
}

// ============
// Classes
// ============