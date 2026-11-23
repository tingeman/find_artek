// Overview map: every feature the user may see (plan "features" T3, FindArtekMap).
document.addEventListener('DOMContentLoaded', function () {
    const element = document.getElementById('map');
    if (!element) {
        return;
    }
    const overlay = document.getElementById('loading-overlay');
    const findArtekMap = new FindArtekMap({element: element, mode: 'overview'});

    if (overlay) {
        overlay.style.display = 'flex';
    }
    findArtekMap.loadFeatures()
        .catch(function (error) {
            console.error('Could not load the features:', error);
        })
        .finally(function () {
            if (overlay) {
                overlay.style.display = 'none';
            }
        });
});
