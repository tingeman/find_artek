// Feature page: the map shows this one feature (plan "features" T3, FindArtekMap).
// The feature id comes from the map element's data-feature-id.
document.addEventListener('DOMContentLoaded', function () {
    const element = document.getElementById('map');
    if (!element) {
        return;
    }
    const findArtekMap = new FindArtekMap({element: element, mode: 'feature'});
    findArtekMap.loadFeatures().catch(function (error) {
        console.error('Could not load the feature:', error);
    });
});
