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
        // Create table row
        const reportRow = document.createElement('tr');

        // Create cells for the row
        const reportNumber = document.createElement('td');
        const reportTitleCell = document.createElement('td');
        const reportFile = document.createElement('td');
        const reportType = document.createElement('td');
        const reportDownloadCount = document.createElement('td');


        // ----------------- Handle reportNumber ----------------- //
        // Add innertext to reportNumber
        reportNumber.innerText = report.number;
        // ----------------- Handle reportNumber ----------------- //


        // ----------------- Handle reportTitleCell ----------------- //
        // Create divs and add classes to them. Then append them to the reportTitleCell
        // Create divs for reportTitleCell, "report-title" and "report-aurthors"
        const reportTitleDiv = document.createElement('div');
        const authorTitleDiv = document.createElement('div');

        // Add classes to the divs 
        reportTitleDiv.classList.add('report-title');
        authorTitleDiv.classList.add('report-authors');

        // Append the divs to the reportTitleCell
        reportTitleCell.appendChild(reportTitleDiv);
        reportTitleCell.appendChild(authorTitleDiv);

        // -------
        // Handle content for reportTitleDiv starts here //
        // -------

        // Create a link for the report title
        const reportTitleLink = document.createElement('a');

        // Add href to to reportTitleLink
        reportTitleLink.href = `#`;

        // Add innertext to reportTitleLink
        reportTitleLink.innerText = report.title;

        // Append reportTitleLink to reportTitleDiv
        reportTitleDiv.appendChild(reportTitleLink);

        // -------
        // Handle content for reportTitleDiv ends here //
        // -------

        // -------
        // Handle content for authorTitleDiv starts here //
        // -------

        // Create a link for the report authors
        const reportAuthorsLink = document.createElement('a');

        // Add href to to reportAuthorsLink
        reportAuthorsLink.href = `#`;

        // Add innertext to reportAuthorsLink




        // ----------------- Handle reportTitleCell ----------------- //


        

        // ----------------- Append row to the table ----------------- //


        // Append reportNumber to the reportRow
        reportRow.appendChild(reportNumber);

        // Append reportTitleCell to the reportRow
        reportRow.appendChild(reportTitleCell);

        // Append reportFile to the reportRow
        
        
        
        // Append reportRow to the reportsTableList
        reportsTableList.appendChild(reportRow);

        // ----------------- Append row to the table ----------------- //

    });

    // To hide the overlay
    loadingOverlay.style.display = 'none';

    return true;
}

// ============
// Classes
// ============