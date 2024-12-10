class MyReportsClass {
    constructor(
        reportsTableList,
        totalReportsNumber = null,
        defaultUrl
    ) {
        this.reportsTableList = reportsTableList
        this.totalReportsNumber = totalReportsNumber;
        this.defaultUrl = defaultUrl;
    }


    async getReports(filter = { topic: null, personId: null }) {



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



        // Show the loading overlay, until tha data is present
        // this.loadingOverlay.style.display = 'flex';


        let url = this.defaultUrl;
        let topic = null;

        // Check if a filter was provided
        if (filter) {
            // If 'topic' is in filter, append it to the url
            if (filter.topic) {

                if (filter.topic === null) {
                    url = `${this.defaultUrl}`;
                }
                else {
                    url = `${this.defaultUrl}?topic=${filter.topic}`;
                }
                
            }

            // If 'personID' is in filter, append it to the url
            if (filter.personId) {
                url = `${this.defaultUrl}?person_id=${filter.personId}`;
            }
        }

        // Fetch the data from the api
        // const response = await fetch(url);


        // check of ?topic exist in url
        if (url.includes('?topic=')) {
            // get the topic from the url
            topic = url.split('?topic=')[1];
            url = url.split('?topic=')[0];
        } else {
            topic = null;
            url = url;
        }

        

        // Convert the response to json
        const reportData = await this.getReportsData(url, topic);

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
            reportTitleLink.innerText = report.title;
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
                const authorLink = document.createElement('a');
                authorLink.href = URL_PREFIX + `/publications/author/#/`;
                authorLink.innerText = `${author.first} ${author.last}`;
                return authorLink.outerHTML;
            });

            let formattedAuthorNames;

            switch (authorNames.length) {
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


            // Creates:
            //         <a href="#">
            //             <img src="/static/find_artek_static/staticfiles/publications/img/pdf_16x16.png" alt="pdf-logo">
            //         </a>
            const pdfLogoLink = document.createElement('a');
            pdfLogoLink.href = report.link_to_pdf_associated_with_this_publication;
            pdfLogoLink.download = ''
            const pdfLogo = document.createElement('img');
            pdfLogo.src = URL_PREFIX + '/static/publications/img/pdf_16x16.png';
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




            // Append reportRow to the reportsTableList
            this.reportsTableList.appendChild(reportRow);

            // ----------------- Append row to the table ----------------- //

        });




    }


    async getReportsData(url = URL_PREFIX + '/api/report/', filter = null) {

        // // replace æøå with ae oe aa
        // filter = (null == filter) ? null : filter.toLowerCase().replace(/æ/g, 'ae').replace(/ø/g, 'oe').replace(/å/g, 'aa');

        // Try to get the data from session storage first - replace æøå with ae oe aa
        const sessionPointer =  (null == filter) ? 'reportData' : `reportData_${filter.toLowerCase().replace(/æ/g, 'ae').replace(/ø/g, 'oe').replace(/å/g, 'aa')}`;

        let reportData = sessionStorage.getItem(sessionPointer);

        if (!reportData) {
            // If not, fetch the data from the endpoint
            const response = await fetch(url + (null == filter ? '' : `?topic=${filter}`));
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            
            try {
                reportData = await response.json();
            } catch (error) {
                console.error('Error occurred while parsing response:', error);
            }

            // Store the data in session storage as a string
            sessionStorage.setItem(sessionPointer, JSON.stringify(reportData));
            
            return reportData;
        }

        // If data exists in storage, parse it from the string and return
        return JSON.parse(reportData);



        // const topics = [
        //     'Infrastruktur',
        //     'Miljø',
        //     'Energi',
        //     'Byggeri',
        //     'Geoteknik',
        //     'Samfund',
        //     'Råstoffer',
        // ]


        // // foreach topic in topics
        // topics.forEach((topic) => {
        //     let sessionData = sessionStorage.getItem(`reportData_${topic}`);

        //     if (!sessionData) {
        //     // If not, fetch the data from the endpoint
        //     const response = fetch('/api/report/?topic=' + topic);
        //     }

        //     if (!response.ok) {
        //         throw new Error(`HTTP error! status: ${response.status}`);
        //     }
        //     reportData = response.json();

        //     // Store the data in session storage as a string
        //     sessionStorage.setItem(`reportData_${topic}`, JSON.stringify(reportData));

        // });




        // hande url topic here


    }

}