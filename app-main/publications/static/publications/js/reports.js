// ============
// Initialization
// ============
document.addEventListener("DOMContentLoaded", function (event) {
  // This block will run when the DOM is loaded.
  main().catch(error => {
    console.error("Error: ", error);
    // handle error, for example by showing an error message to the user
  });
});





// // ============
// // Main
// // ============
async function main() {
    // Here we are getting the elements from the DOM
    const loadingOverlay = document.getElementById('loading-overlay');
    const reportsTableList = document.getElementById('reports-table-list');
    const totalReportsNumber = document.getElementById('total-reports-number');


    const apiEndpoint = '/api/report/';

    // check if get paramete 'topic' is present
    const urlParams = new URLSearchParams(window.location.search);
    let topic = urlParams.get('topic');
    // if topic is null or undefined, set it to 'all'
    if (topic === null || topic === undefined || topic.toLowerCase() === 'all') {
        topic = null;
    }

    const myReportsClass = new MyReportsClass(
        reportsTableList,
        totalReportsNumber,
        apiEndpoint
        );


    // To show the overlay
    loadingOverlay.style.display = 'flex';

    await myReportsClass.getReports({topic: topic});

    // To hide the overlay
    loadingOverlay.style.display = 'none';

    // // Global variables
    // let $my = {
    //     reportsTableList: reportsTableList,
    //     myReportsClass: new MyReportsClass(
    //         loadingOverlay,
    //         reportsTableList,
    //         totalReportsNumber,
    //         apiEndpoint
    //         ),
    //     filter: {topic: topic}
    // }




    // This block will run when the DOM is loaded.
    // main($my).then((finished) => {
    //     if (finished) {
    //         console.log("main() is done executing.");
    //     }
    // });
}

// async function main($my) {
//     $my.myReportsClass.getReports()
// }

// ============
// Classes
// ============