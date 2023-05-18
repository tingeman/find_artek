document.addEventListener("DOMContentLoaded", function (event) {
    // This block will run when the DOM is loaded.
    main().then((finished) => {
        if (finished) {
            console.log("main() is done executing.");
        }
    });
        
});






// // ============
// // Main
// // ============
async function main() {

    const loadingOverlay = document.getElementById('loading-overlay');

    // To show the overlay
    loadingOverlay.style.display = 'flex';

    const response = await fetch('/publications/api/reports/');

    const reportData = await response.json();
   
    const reportsTableList = document.getElementById('reports-table-list');

    reportData.forEach((report) => {
        const reportRow = document.createElement('tr');
        
        const reportId = document.createElement('td');
        
        // title
        const reportLink = document.createElement('a');
        reportLink.href = report.url;
        report.authors.forEach((author) => {
            reportLink.innerText = reportLink.innerText + author.first + ' & ' + author.last + ', ';
        });
        const reportTitle = document.createElement('td');



        
        const reportFile = document.createElement('td');

        
        const reportType = document.createElement('td');
        const reportDownloadCount = document.createElement('td');


        reportId.innerText = report.number;

        reportTitle.innerText = report.title;

        reportTitle.appendChild(document.createElement('br'));
        reportTitle.appendChild(reportLink);
        reportFile.innerText = report.file;
        reportType.innerText = report.type;
        reportDownloadCount.innerText = report.feature_count;

        reportRow.appendChild(reportId);
        reportRow.appendChild(reportTitle);
        reportRow.appendChild(reportFile);
        reportRow.appendChild(reportType);
        reportRow.appendChild(reportDownloadCount);

        reportsTableList.appendChild(reportRow);
    });

    // To hide the overlay
    loadingOverlay.style.display = 'none';

    return true;
}

// ============
// Classes
// ============