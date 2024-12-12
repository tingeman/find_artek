// =============================================================================
// Initialization
// =============================================================================
document.addEventListener("DOMContentLoaded", function (event) {
  // This block will run when the DOM is loaded.
  console.log('Testing console log from person.js');
  main().catch(error => {
    console.error("Error: ", error);
    // handle error, for example by showing an error message to the user
  });
});


// =============================================================================
// Main
// =============================================================================
async function main() {
    // Here we are getting the elements from the DOM
    const loadingOverlayAuthorships = document.getElementById('loading-overlay-authorships');
    const loadingOverlaySupervisorships = document.getElementById('loading-overlay-supervisorships');
    const authorshipTableList = document.getElementById('authorship-table-list');
    const supervisorshipTableList = document.getElementById('supervisorship-table-list');
    const totalAuthorshipsNumber = document.getElementById('total-authorship-number');
    const totalSupervisorshipsNumber = document.getElementById('total-supervisorship-number');

    // from https://arctic.sustain.dtu.dk/find/publications/person/274/ extract 274 after removing any trailing slashes
    const path = window.location.pathname.replace(/\/$/, ''); // remove any trailing slashes
    const parts = path.split('/');
    const personId = parts[parts.length - 1]; 
    
    console.log('personId:', personId);
   
    const myAuthorshipsClass = new MyReportsClass(
        authorshipTableList,
        totalAuthorshipsNumber,
        url = URL_PREFIX + '/api/report/'
    );

    const mySupervisorshipsClass = new MyReportsClass(
        supervisorshipTableList,
        totalSupervisorshipsNumber,
        url = URL_PREFIX + '/api/report/'
    );

    // To show the overlay
    loadingOverlayAuthorships.style.display = 'flex';
    loadingOverlaySupervisorships.style.display = 'flex';
    
    await myAuthorshipsClass.getReports({ author: personId });
    loadingOverlayAuthorships.style.display = 'none';

    await mySupervisorshipsClass.getReports({ supervisor: personId });
    loadingOverlaySupervisorships.style.display = 'none';

};


// ============
// Classes
// ============