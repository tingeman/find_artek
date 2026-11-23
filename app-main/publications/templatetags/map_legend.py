"""Map legend and type colours for the templates (plan "features" T11).

``{% feature_type_colors_script %}``: the feature type colours as a JSON script block for
find-artek-map.js. Every page that loads find-artek-map.js includes it.

``{% feature_type_legend %}``: the legend (colour and name per feature type).
``{% feature_type_legend selected=selected_feature_types %}``: the same legend with a checkbox
per type (the overview map's type filter); ``selected`` is the set of checked type slugs.

Colours come from publications.map_styles (the single source).
"""
from django import template
from django.utils.html import json_script

from publications.map_styles import (COLORS_SCRIPT_ID, FEATURE_TYPE_COLORS, TYPE_FILTER_PARAM,
                                     feature_type_styles)

register = template.Library()


@register.simple_tag
def feature_type_colors_script():
    return json_script(FEATURE_TYPE_COLORS, COLORS_SCRIPT_ID)


@register.inclusion_tag('publications/shared_snippets/feature_type_legend.html')
def feature_type_legend(selected=None):
    styles = feature_type_styles()
    checkboxes = selected is not None
    for style in styles:
        style['checked'] = checkboxes and style['slug'] in selected
    return {'types': styles, 'checkboxes': checkboxes, 'param': TYPE_FILTER_PARAM}
