/**
 * Feature Map Selector for Add Feature By Map
 *
 * This script initializes a Leaflet map that allows users to click and add multiple points,
 * creating a MultiPoint geometry.
 *
 * Features:
 * - Click to add points
 * - View list of added points with coordinates
 * - Clear all points
 * - Reset map view
 * - Automatically updates the hidden form field with GeoJSON data
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Grab the container element and verify if it exists
    const mapContainer = document.getElementById('feature-map');
    if (!mapContainer) {
        console.error('Map container not found');
        return;
    }

    // Initialize the map with a default view of Greenland
    const map = L.map('feature-map').setView([70.738, -40.5795], 4);
    
    // Add a tile layer (you can choose different providers)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);
    
    // Array to store the selected points
    const selectedPoints = [];
    let markersLayer = L.layerGroup().addTo(map);
    
    // Function to add a marker when the map is clicked
    function addMarker(e) {
        const latlng = e.latlng;
        
        // Create a new marker
        const marker = L.marker(latlng, {
            draggable: true
        }).addTo(markersLayer);
        
        // Add popup with coordinates and option to remove
        const popupContent = `
            <div>
                <p>Latitude: ${latlng.lat.toFixed(6)}<br>
                Longitude: ${latlng.lng.toFixed(6)}</p>
                <button class="btn btn-danger btn-sm remove-marker">Remove</button>
            </div>
        `;
        
        marker.bindPopup(popupContent);
        
        // When marker is dragged, update the GeoJSON
        marker.on('dragend', function() {
            updatePointsList();
            updateFormField();
        });
        
        // Handle click on the remove button in the popup
        marker.on('popupopen', function() {
            document.querySelector('.remove-marker').addEventListener('click', function() {
                markersLayer.removeLayer(marker);
                updatePointsList();
                updateFormField();
            });
        });
        
        // Add to the selected points and update the display
        selectedPoints.push({
            marker: marker,
            latlng: latlng
        });
        
        updatePointsList();
        updateFormField();
    }
    
    // Function to update the list of points displayed below the map
    function updatePointsList() {
        const pointsList = document.getElementById('points-list');
        if (!pointsList) return;
        
        if (markersLayer.getLayers().length === 0) {
            pointsList.innerHTML = `
                <div class="alert alert-info">No points selected yet. Click on the map to add points.</div>
            `;
            return;
        }
        
        let html = '<ul class="list-group">';
        
        markersLayer.getLayers().forEach((marker, index) => {
            const latlng = marker.getLatLng();
            html += `
                <li class="list-group-item d-flex justify-content-between align-items-center small">
                    <span>Point ${index + 1}: Lat: ${latlng.lat.toFixed(6)}, Lng: ${latlng.lng.toFixed(6)}</span>
                    <button class="btn btn-outline-danger btn-sm btn-remove-point" data-index="${index}">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </li>
            `;
        });
        
        html += '</ul>';
        pointsList.innerHTML = html;
        
        // Add event listeners to remove buttons
        document.querySelectorAll('.btn-remove-point').forEach((button) => {
            button.addEventListener('click', function() {
                const index = parseInt(this.getAttribute('data-index'));
                const layers = markersLayer.getLayers();
                if (layers[index]) {
                    markersLayer.removeLayer(layers[index]);
                    updatePointsList();
                    updateFormField();
                }
            });
        });
    }
    
    // Function to update the hidden form field with GeoJSON data
    function updateFormField() {
        const geojsonField = document.querySelector('input[name="geojson_data"]');
        if (!geojsonField) return;
        
        // Create GeoJSON FeatureCollection
        const features = markersLayer.getLayers().map(marker => {
            const latlng = marker.getLatLng();
            return {
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [latlng.lng, latlng.lat] // GeoJSON is [longitude, latitude]
                },
                properties: {}
            };
        });
        
        const geojson = {
            type: 'FeatureCollection',
            features: features
        };
        
        // Update the hidden input field
        geojsonField.value = JSON.stringify(geojson);
    }
    
    // Function to clear all points
    function clearPoints() {
        markersLayer.clearLayers();
        updatePointsList();
        updateFormField();
    }
    
    // Function to reset the map view
    function resetMapView() {
        map.setView([70.738, -40.5795], 4);
    }
    
    // Add event listener to the map for adding points
    map.on('click', addMarker);
    
    // Add event listeners for the control buttons
    document.getElementById('clear-points')?.addEventListener('click', clearPoints);
    document.getElementById('reset-view')?.addEventListener('click', resetMapView);
    
    // Initial setup
    updatePointsList();
});
