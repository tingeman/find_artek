"""Feature type colours and the overview map's type filter (plan "features" T11, FA-R65 part).

The one place that says which colour a feature type has on the map. Used by
- the map component in the browser: ``{% feature_type_colors_script %}`` renders the colours
  as a JSON script block (id ``find-artek-type-colors``) that find-artek-map.js reads;
- the legend on the overview map and the report page: ``{% feature_type_legend %}``
  (templatetags/map_legend.py).

The overview map keeps its type filter in the URL as ``types=<slug>,<slug>,...`` next to
lat/lng/zoom. No ``types`` parameter = every type shown; ``types=`` (empty) = none.
"""
from publications.models import Feature

# Colour per Feature.type value. Every type in Feature.feature_types needs an entry
# (test_map_overview.py checks it). Hex values (#rrggbb), so the tests can check them: every
# colour must stand out on white and on the light map layers (contrast ratio against white at
# least 3:1, test_map_styles.py) and differ clearly from the others. Points get a black outline
# on the map, lines are drawn in the colour itself.
# T16 (owner's browser check): 'white' (OTHER) was invisible on white, 'yellow' (BOREHOLE) and
# 'pink' (LAB MEASUREMENT) nearly so; they became teal, dark goldenrod and deep pink. The other
# colours are the old CSS names written as hex.
FEATURE_TYPE_COLORS = {
    Feature.PHOTO: '#ff0000',               # red
    Feature.SAMPLE: '#008000',              # green
    Feature.BOREHOLE: '#b8860b',            # dark goldenrod (was yellow)
    Feature.GEOPHYSICAL_DATA: '#0000ff',    # blue
    Feature.FIELD_MEASUREMENT: '#800080',   # purple
    Feature.LAB_MEASUREMENT: '#d6337f',     # deep pink (was pink)
    Feature.RESOURCE: '#a52a2a',            # brown
    Feature.OTHER: '#00838f',               # teal (was white)
}

# Colour of a type that has no entry (shouldn't happen; the same value is in the JS).
UNKNOWN_TYPE_COLOR = '#808080'   # gray

# Query parameter of the overview map's type filter.
TYPE_FILTER_PARAM = 'types'

# Id of the JSON script block with the colours (find-artek-map.js reads it).
COLORS_SCRIPT_ID = 'find-artek-type-colors'


def feature_type_slug(value):
    """URL form of a Feature.type value: 'GEOPHYSICAL DATA' -> 'geophysical-data'."""
    return value.lower().replace(' ', '-')


def feature_type_styles():
    """[{'value', 'slug', 'label', 'color'}] for every feature type, in the model's order."""
    return [
        {'value': value, 'slug': feature_type_slug(value), 'label': label,
         'color': FEATURE_TYPE_COLORS.get(value, UNKNOWN_TYPE_COLOR)}
        for value, label in Feature.feature_types
    ]


def selected_type_slugs(query):
    """The type slugs selected by the ``types`` parameter of ``query`` (a QueryDict).

    No parameter: every type. Otherwise the known slugs in the comma-separated list (case
    and surrounding spaces ignored, unknown values dropped), so ``types=`` selects none."""
    all_slugs = [style['slug'] for style in feature_type_styles()]
    if TYPE_FILTER_PARAM not in query:
        return set(all_slugs)
    wanted = {part.strip().lower() for part in query.get(TYPE_FILTER_PARAM, '').split(',')}
    return {slug for slug in all_slugs if slug in wanted}
