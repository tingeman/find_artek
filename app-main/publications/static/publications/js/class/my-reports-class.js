class MyReportsClass {
    constructor(
        reportsTableList,
        totalReportsNumber = null,
        defaultUrl
    ) {
        this.reportsTableList = reportsTableList
        this.totalReportsNumber = totalReportsNumber;
        this.defaultUrl = defaultUrl;
        this.reportsCount = 0; 
    }


    async getReports(filter = { topic: null, authorId: null, supervisorId: null }) {
        // Populate the reportsTableList with the reports data


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
        //             <img src="/static/find_artek_static/staticfiles/publications/img/pdf_16x16.png" alt="pdf-logo">
        //         </a>
        //     </td>
        //     <td>DIPLOMPROJEKT</td>
        //     <td>0</td>
        // </tr>


        let url = this.defaultUrl;
        let topic = null;

        console.log(filter);

        // Fetch the data from the api
        const reportData = await this.getReportsData(url, filter);
        
        // Update the reportsCount instance variable
        this.reportsCount = reportData.length;

        // List total number of reports
        // If total report number element is present
        if (null !== this.totalReportsNumber) {
            this.totalReportsNumber.innerText = `Reports: ${reportData.length}`
        }

        // Create a table row for each report
        reportData.forEach((report) => {
            // Create table row
            const reportRow = document.createElement('tr');

            // Create cells for the row
            const reportNumber = document.createElement('td');
            reportNumber.classList.add('no-wrap');  // Add a class to the table cell

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
            reportTitleLink.href = URL_PREFIX + `/publications/report/${report.id}/`; // TODO: use debugger to find out what to put here
            reportTitleLink.innerText = report.title && report.title.trim() ? report.title : '[no title]';
            reportTitleDiv.appendChild(reportTitleLink);

            // THIS PART IS NOW DONE
            //         <div class="report-title">
            //             <a href="#" >Analyse af nytteværdien og udviklingspotentialet for en grønlandsk bygd</a>
            //         </div>


            // create <div class="report-authors">

            // ------ add dynamic authors starts here ------ //
            // ------
            // this code does the following when adding authors:
            //
            //if 1 
            //    <name>
            //
            //if 2
            //    <name> & <name>
            //
            //if > 2
            //    <name>; <name>; <name> & <name>



            const authorTitleDiv = document.createElement('div');
            authorTitleDiv.classList.add('report-authors');

            let authorNames = report.authors.map((author) => {
                // console.log('author:', author);
                const authorLink = document.createElement('a');
                authorLink.href = URL_PREFIX + `/publications/person/${author.pk}/`;
                authorLink.innerText = `${author.first} ${author.last}`;
                return authorLink.outerHTML + personMarkerHtml(author, 'author');
            });

            let formattedAuthorNames;

            switch (authorNames.length) {
                case 0:
                    formattedAuthorNames = '[no authors registered]';
                    break;
                case 1:
                    formattedAuthorNames = authorNames[0];
                    break;
                case 2:
                    formattedAuthorNames = authorNames.join(' & ');
                    break;
                default:
                    formattedAuthorNames = `${authorNames.slice(0, -1).join('; ')} & ${authorNames.slice(-1)}`;
                    break;
            }

            authorTitleDiv.innerHTML = formattedAuthorNames;

            // THIS PART IS NOW DONE
            //         <div class="report-authors">
            //             <a href="#" >Andersen, N. P.</a>
            // ;
            //             <a href="#">Christensen, M. T.</a>
            //         </div>

            // ------ add dynamic authors ends here ------ //





            // Append the divs to the reportTitleCell
            reportTitleCell.appendChild(reportTitleDiv);
            reportTitleCell.appendChild(authorTitleDiv);

            // Append reportTitleCell to the reportRow
            reportRow.appendChild(reportTitleCell);
            // ----------------- Handle reportTitleCell ends here ----------------- //



            // ----------------- Handle reportDownloadLink starts here ----------------- //


            // Only add PDF logo if there is a file to download
            if (report.link_to_pdf_associated_with_this_publication) {
                const pdfLogoLink = document.createElement('a');
                pdfLogoLink.href = report.link_to_pdf_associated_with_this_publication;
                pdfLogoLink.download = '';
                const pdfLogo = document.createElement('img');
                pdfLogo.src = URL_PREFIX + '/static/publications/img/pdf_16x16.png';
                pdfLogo.alt = 'pdf-logo';
                pdfLogoLink.appendChild(pdfLogo);
                // Append pdfLogoLink to reportDownloadLink
                reportDownloadLink.appendChild(pdfLogoLink);
            }


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




            // Append reportRow to the reportsTableList
            this.reportsTableList.appendChild(reportRow);

            // ----------------- Append row to the table ----------------- //

        });


    }

    async getReportsData(url = URL_PREFIX + '/api/report/', filters = {}) {
        // Always fetch from the API: the list is not cached in the browser, so added,
        // edited, deleted or verified reports show on the next page load (FA-R89).
        const queryParams = new URLSearchParams();

        // Drop the filter keys that are not set
        filters = Object.fromEntries(
            Object.entries(filters).filter(([key, value]) => value != null)
        );

        // Construct query parameters from filters
        if (filters.topic) {
            queryParams.append('topic', filters.topic);
        }
        if (filters.author) {
            queryParams.append('author_id', filters.author);
        }
        if (filters.supervisor) {
            queryParams.append('supervisor_id', filters.supervisor);
        }
        if (filters.q) {
            queryParams.append('q', filters.q);
        }

        console.log('queryParams:', queryParams.toString());

        // Construct the full URL
        const fullUrl = `${url}?${queryParams.toString()}`;

        // Fetch data from the constructed URL
        const response = await fetch(fullUrl);

        // If the response is not ok, throw an error
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Parse the response to JSON
        let reportData;
        try {
            reportData = await response.json();
        } catch (error) {
            console.error('Error occurred while parsing response:', error);
        }

        return reportData;
    };

}


// Duplicate marker after a person's name (FA-R66), the same as the template
// shared_snippets/person_marker.html. The API sends `match` ("exact" or "relaxed") and
// `multiple` only to users with merge_person; without them this returns ''.
// The link goes to the person page's confirm section; T8 changes it to the merge page
// (here and in person_marker.html).
function personMarkerHtml(person, role) {
    if (!person.match) {
        return '';
    }
    const marker = document.createElement('a');
    marker.href = URL_PREFIX + `/publications/person/${person.pk}/#confirm-person`;
    marker.style.color = 'red';
    marker.style.fontWeight = 'bold';
    marker.classList.add('person-marker');
    let title;
    if (person.match === 'exact') {
        marker.classList.add('person-marker-exact');
        marker.innerText = '!';
        title = `Multiple ${role} instances in database with this exact name!`;
    } else {
        marker.classList.add('person-marker-relaxed');
        marker.innerText = '?';
        title = `This ${role} instance is possibly similar to another instance in the database (relaxed match of initial and lastname).`;
    }
    if (person.multiple) {
        title += ' Several candidates.';
    }
    marker.title = title;
    return ` (${marker.outerHTML})`;
}
