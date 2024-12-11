document.addEventListener("DOMContentLoaded", function (event) {

    // In this block I want all DOM variables specified, it gives me a better overview.
    const loadingOverlay = document.getElementById('loading-overlay')
    const personsTableList = document.getElementById('persons-table-list');
    // Here we are getting the elements from the DOM


    const $ = {
        loadingOverlay: loadingOverlay,
        personsTableList: personsTableList,
        apiPersonEndpoint: URL_PREFIX + '/api/person/',   
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
    // Complete structure that needs to be build
    // 
    // <tr><td>Victor</td></tr>
    // <tr><td>Alex</td></tr>

    // Show the loading overlay, until the data is present
    $.loadingOverlay.style.display = 'flex';

    // Fetch the data from the api
    const response =  await fetch($.apiPersonEndpoint);

    // Convert the response to json
    const personData = await response.json();

    

// Create a table row for each person
personData.forEach((person) => {
    // Create table row
    const personRow = document.createElement('tr');

    // Create cell for the row
    const personCell = document.createElement('td');

    // Create a link for the person
    const personLink = document.createElement('a');
    personLink.href = URL_PREFIX + `/publications/person/${person.id}/`; // replace with the actual link

    // If prelast is not empty, add it before the last name
    if (person.prelast) {
        personLink.innerText = `${person.prelast} ${person.last}, ${person.first} ${person.middle}`;
    } else {
        personLink.innerText = `${person.last}, ${person.first} ${person.middle}`;
    }

    // Append the link to the cell
    personCell.appendChild(personLink);

    // Append the cell to the row
    personRow.appendChild(personCell);

    // Create cell for the row
    const idCell = document.createElement('td');
    idCell.innerText = person.id_number;
    personRow.appendChild(idCell);

    // Create cell for the row
    positionCell = document.createElement('td');
    positionCell.innerText = person.position;
    personRow.appendChild(positionCell);

    // Append the row to the table
    $.personsTableList.appendChild(personRow);
});


    // To hide the overlay
    $.loadingOverlay.style.display = 'none';

    return true;
}
