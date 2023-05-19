document.addEventListener("DOMContentLoaded", function (event) {
    // This block will run when the DOM is loaded.
    main().then((finished) => {
        if (finished) {
            console.log("main() is done executing.");
        }
    });

});






// ============
// Main
// ============
async function main() {



    // Complete structure that needs to be build
    // <tr>
    //     <td>17-02</td> // DONE
    //     <td>
    //         <div class="report-title">
    //             <a href="#" >Analyse af nytteværdien og udviklingspotentialet for en grønlandsk bygd</a>
    //         </div>
    //         <div class="report-authors">
    //             <a href="#" >Andersen, N. P.</a>
    //             <a href="#">Christensen, M. T.</a>
    //         </div>
    //     </td>
    //     <td>
    //         <a href="#">
    //             <img src="/static/publications/img/pdf_16x16.png" alt="pdf-logo">
    //         </a>
    //     </td>
    //     <td>DIPLOMPROJEKT</td>
    //     <td>0</td>
    // </tr>






    // Show the loading overlay, until tha data is present
    const loadingOverlay = document.getElementById('loading-overlay');
    loadingOverlay.style.display = 'flex';

    // Fetch the data from the api
    const response = await fetch('/publications/api/reports/');

    // Convert the response to json
    const reportData = await response.json();

    const reportsTableList = document.getElementById('reports-table-list');

    // Create a table row for each report
    reportData.forEach((report) => {
        // Create table row
        const reportRow = document.createElement('tr');

        // Create cells for the row
        const reportNumber = document.createElement('td');
        const reportTitleCell = document.createElement('td');
        const reportDownloadLink = document.createElement('td');
        const reportType = document.createElement('td');
        const reportDownloadCount = document.createElement('td');









        // ----------------- Handle reportNumber starts here ----------------- //
        // Add innertext to reportNumber
        reportNumber.innerText = report.number;

        // Report number is ready to be appended to the reportRow
        reportRow.appendChild(reportNumber);
        // ----------------- Handle reportNumber ends here ----------------- //























        // ----------------- Handle reportTitleCell starts here ----------------- //


        //     <td>
        //         <div class="report-title">
        //             <a href="#" >Analyse af nytteværdien og udviklingspotentialet for en grønlandsk bygd</a>
        //         </div>
        //         <div class="report-authors">
        //             <a href="#" >Andersen, N. P.</a>
        //             <a href="#">Christensen, M. T.</a>
        //         </div>
        //     </td>

        // create <div class="report-title">
        const reportTitleDiv = document.createElement('div');
        reportTitleDiv.classList.add('report-title');

        // create <a href="#" >Analyse af nytteværdien og udviklingspotentialet for en grønlandsk bygd</a>
        const reportTitleLink = document.createElement('a');
        reportTitleLink.href = `/publications/report/${report.id}/`; // TODO: use debugger to find out what to put here
        reportTitleLink.innerText = report.title;
        reportTitleDiv.appendChild(reportTitleLink);

        // THIS PART IS NOW DONE
        //         <div class="report-title">
        //             <a href="#" >Analyse af nytteværdien og udviklingspotentialet for en grønlandsk bygd</a>
        //         </div>


        // create <div class="report-authors">
        const authorTitleDiv = document.createElement('div');
        authorTitleDiv.classList.add('report-authors');
        authorTempLink = document.createElement('a');
        authorTempLink.innerText = 'Temp author';
        authorTitleDiv.appendChild(authorTempLink);

        // THIS PART IS NOW DONE
        //         <div class="report-authors">
        //             <a href="#" >Andersen, N. P.</a>
        //             <a href="#">Christensen, M. T.</a>
        //         </div>


        // Append the divs to the reportTitleCell
        reportTitleCell.appendChild(reportTitleDiv);
        reportTitleCell.appendChild(authorTitleDiv);

        // Append reportTitleCell to the reportRow
        reportRow.appendChild(reportTitleCell);
        // ----------------- Handle reportTitleCell ends here ----------------- //
















        // ----------------- Handle reportDownloadLink starts here ----------------- //


        // Creates:
        //         <a href="#">
        //             <img src="/static/publications/img/pdf_16x16.png" alt="pdf-logo">
        //         </a>
        const pdfLogoLink = document.createElement('a');
        pdfLogoLink.href = report.link_to_pdf_associated_with_this_publication;
        pdfLogoLink.download = ''
        const pdfLogo = document.createElement('img');
        pdfLogo.src = '/static/publications/img/pdf_16x16.png';
        pdfLogo.alt = 'pdf-logo';
        pdfLogoLink.appendChild(pdfLogo);

        // Append pdfLogoLink to reportDownloadLink
        reportDownloadLink.appendChild(pdfLogoLink);


        // Append reportDownloadLink to reportRow
        reportRow.appendChild(reportDownloadLink);
        // ----------------- Handle reportDownloadLink ends here ----------------- //


        // ----------------- Handle reportType starts here ----------------- //

        // Creates:
        // <td>DIPLOMPROJEKT</td>
        reportType.innerText = report.type;

        // Append reportType to reportRow
        reportRow.appendChild(reportType);
        // ----------------- Handle reportType ends here ----------------- //









        // ----------------- Handle reportDownloadCount starts here ----------------- //

        // Creates:
        //     <td>0</td>

        // Add innertext to reportDownloadCount
        reportDownloadCount.innerText = report.feature_count.toString();

        // Append reportDownloadCount to reportRow
        reportRow.appendChild(reportDownloadCount);
        
        // ----------------- Handle reportDownloadCount ends here ----------------- //



        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        // // Create a link for the report title
        // const reportTitleLink = document.createElement('a');

        // // Add href to to reportTitleLink
        // reportTitleLink.href = `#`;

        // // Add innertext to reportTitleLink
        // reportTitleLink.innerText = report.title;

        // // Append reportTitleLink to reportTitleDiv
        // reportTitleDiv.appendChild(reportTitleLink);

        // // -------
        // Handle content for reportTitleDiv ends here //
        // -------

        // -------
        // // Handle content for authorTitleDiv starts here //
        // // -------

        // // Create a link for the report authors
        // const reportAuthorsLink = document.createElement('a');

        // // Add href to to reportAuthorsLink
        // reportAuthorsLink.href = `#`;

        // // Add innertext to reportAuthorsLink




        // // ----------------- Handle reportTitleCell ----------------- //




        // // ----------------- Append row to the table ----------------- //


        // // Append reportNumber to the reportRow
        // reportRow.appendChild(reportNumber);

        // // Append reportTitleCell to the reportRow
        // reportRow.appendChild(reportTitleCell);

        // // Append reportFile to the reportRow



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