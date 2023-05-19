// ============
// Initialization
// ============
document.addEventListener("DOMContentLoaded", function (event) {
    // This block will run when the DOM is loaded.
    main();
  });
  
  
  
  // // ============
  // // Main
  // // ============
  async function main() {
  
    const myMapClass = new MyMapClass();

    
    
    try {
      map = await myMapClass.initialize();
  
    } catch (error) {
      console.error("Error initializing map or fetching feature data: ", error);
    }
  
  }
  