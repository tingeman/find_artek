"""Forms for working with features."""

from django import forms
from django.forms import ModelForm
from publications.geometry import (
    GeometryError, feature_geojson, from_geojson, map_transform_note, same_geometry,
)
from publications.models import Feature
from django.core.exceptions import ValidationError
from django.contrib.gis.gdal import SpatialReference

from django.utils.translation import gettext_lazy as _
import json


class AddFeatureByCoordinatesForm(ModelForm):
    """Form for adding a point feature with known coordinates"""
    
    # Coordinate fields
    x_coordinate = forms.DecimalField(
        max_digits=15, 
        decimal_places=6,
        help_text="X coordinate (Easting/Longitude)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
    )
    y_coordinate = forms.DecimalField(
        max_digits=15, 
        decimal_places=6,
        help_text="Y coordinate (Northing/Latitude)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
    )
    
    # SRID field with simple help text
    spatial_reference_system = forms.CharField(
        max_length=10,
        label="Spatial Reference System (SRID)",
        help_text="Enter EPSG code (e.g., 4326, 32622).",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 4326'})
    )
    
    # Date field with proper widget
    date = forms.DateField(
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        ),
        input_formats=['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'],
        required=True,
        help_text="Date when the feature was observed/measured"
    )

    class Meta:
        model = Feature
        fields = ['name', 'type', 'area', 'date', 'direction', 'description', 
                 'comment', 'pos_quality']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Feature name'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Area/Location'}),
            'direction': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Direction/Orientation'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'pos_quality': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'name': 'Unique identifier or name for this feature',
            'type': 'Type of feature being registered',
            'area': 'General area or location description',
            'direction': 'Direction or orientation if applicable',
            'description': 'Detailed description of the feature',
            'comment': 'Additional comments or notes',
            'pos_quality': 'Quality/accuracy of the position measurement',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make required fields obvious
        self.fields['name'].required = True
        self.fields['type'].required = True
        self.fields['pos_quality'].required = True
        self.fields['date'].required = True
        self.fields['x_coordinate'].required = True
        self.fields['y_coordinate'].required = True
        self.fields['spatial_reference_system'].required = True
        
        # Set better labels for coordinate fields
        self.fields['x_coordinate'].label = "X Coordinate"
        self.fields['y_coordinate'].label = "Y Coordinate"

    def clean_spatial_reference_system(self):
        """Validate SRID"""
        srid = self.cleaned_data.get('spatial_reference_system')
        if not srid:
            raise ValidationError('Spatial Reference System is required')
        
        try:
            srid_int = int(srid)
            if srid_int <= 0:
                raise ValidationError('SRID must be a positive integer')
        except ValueError:
            raise ValidationError('SRID must be a valid integer')
            
        # Check if SRID exists in spatial reference database
        try:
            sr = SpatialReference(srid_int)
            # If we get here, the SRID is valid
        except Exception:
            # Issue a warning but don't reject
            self.add_error('spatial_reference_system', 
                          f'Warning: SRID {srid_int} may not be recognized by the system. '
                          f'Please verify this is correct.')
        
        return srid
    
    def clean(self):
        """Cross-field validation for coordinates"""
        cleaned_data = super().clean()
        x_coord = cleaned_data.get('x_coordinate')
        y_coord = cleaned_data.get('y_coordinate')
        srid = cleaned_data.get('spatial_reference_system')
        date = cleaned_data.get('date')
        name = cleaned_data.get('name')
        pos_quality = cleaned_data.get('pos_quality')
        
        # Check that all required fields are provided
        if not name:
            self.add_error('name', 'Feature name is required')
        
        if not pos_quality:
            self.add_error('pos_quality', 'Position quality is required')
        
        # Check that all coordinate fields are provided together
        coordinate_fields = [x_coord, y_coord, srid]
        has_any_coords = any(field is not None for field in coordinate_fields)
        has_all_coords = all(field is not None for field in coordinate_fields)
        
        if has_any_coords and not has_all_coords:
            if x_coord is None:
                self.add_error('x_coordinate', 'X coordinate is required when providing coordinate information')
            if y_coord is None:
                self.add_error('y_coordinate', 'Y coordinate is required when providing coordinate information')
            if srid is None:
                self.add_error('spatial_reference_system', 'Spatial Reference System is required when providing coordinates')
        
        # All coordinate fields are required for this form
        if not has_all_coords:
            if x_coord is None:
                self.add_error('x_coordinate', 'X coordinate is required')
            if y_coord is None:
                self.add_error('y_coordinate', 'Y coordinate is required')
            if srid is None:
                self.add_error('spatial_reference_system', 'Spatial Reference System is required')
        
        # Date field is required
        if not date:
            self.add_error('date', 'Date is required')
        
        # If we have all coordinate data, validate ranges
        if x_coord is not None and y_coord is not None and srid:
            try:
                srid_int = int(srid)
                
                # Coordinate range validation based on coordinate system type
                if srid_int == 4326:  # WGS84 Geographic
                    if not (-180 <= x_coord <= 180):
                        self.add_error('x_coordinate', 
                                     f'Warning: Longitude {x_coord} is outside normal range (-180 to 180)')
                    if not (-90 <= y_coord <= 90):
                        self.add_error('y_coordinate', 
                                     f'Warning: Latitude {y_coord} is outside normal range (-90 to 90)')
                
                elif 32600 <= srid_int <= 32700:  # UTM zones
                    if not (0 <= x_coord <= 1000000):
                        self.add_error('x_coordinate', 
                                     f'Warning: UTM Easting {x_coord} seems outside normal range (0-1,000,000m)')
                    if not (0 <= y_coord <= 10000000):
                        self.add_error('y_coordinate', 
                                     f'Warning: UTM Northing {y_coord} seems outside normal range (0-10,000,000m)')
                
                elif 25800 <= srid_int <= 25900:  # ETRS89 UTM zones
                    if not (0 <= x_coord <= 1000000):
                        self.add_error('x_coordinate', 
                                     f'Warning: UTM Easting {x_coord} seems outside normal range (0-1,000,000m)')
                    if not (0 <= y_coord <= 10000000):
                        self.add_error('y_coordinate', 
                                     f'Warning: UTM Northing {y_coord} seems outside normal range (0-10,000,000m)')
                
                # General validation for projected coordinates (should be positive)
                elif srid_int != 4326 and (x_coord < 0 or y_coord < 0):
                    if x_coord < 0:
                        self.add_error('x_coordinate', 
                                     'Warning: Negative coordinates are unusual for projected coordinate systems')
                    if y_coord < 0:
                        self.add_error('y_coordinate', 
                                     'Warning: Negative coordinates are unusual for projected coordinate systems')
                
            except ValueError:
                pass  # SRID validation already handled above
                
        return cleaned_data


class AddFeatureByMap(ModelForm):
    """Add or edit a feature by drawing on the map (plan "features" T5).

    ``geojson_data`` (hidden) holds what the map editor drew: a GeoJSON FeatureCollection in
    WGS84 (lon/lat) with points, lines and polygons in any mix (find-artek-map-edit.js).
    ``publications.geometry.from_geojson`` checks and builds it; its GeometryError becomes a
    form error.

    With an instance (edit), the field starts with the stored geometry
    (``geometry.feature_geojson``). If the submitted geometry is the stored one (unchanged
    text, or the same vertices within 1e-9 degrees), the geometry and the source fields
    (``source_srid``, ``source_geometry``, ``transform_note``) are kept: an attribute-only
    edit. Otherwise ``save()`` replaces all three geometry columns (a kind no longer drawn
    becomes NULL) and the source fields describe the map drawing (EPSG:4326, transform note
    ending in "digitized on the map (WGS84)"; design note 8).

    After ``is_valid()``: ``geometry_changed`` (bool) and ``geometry_warnings`` (tuple of
    str, e.g. outside Greenland) for the view's messages.
    """

    geojson_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    date = forms.DateField(
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        input_formats=['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'],
        required=True,
        help_text=_("Date when the feature was observed/measured"),
    )

    observation_date = forms.DateField(
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        input_formats=['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'],
        required=False,
        label=_('GNSS observation date'),
        help_text=_('GNSS observation date, basis for epoch calculations; empty = the feature '
                    'date is used.'),
    )

    class Meta:
        model = Feature
        fields = ['name', 'type', 'area', 'date', 'observation_date', 'pos_quality',
                  'direction', 'description', 'comment']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Feature name'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Area/Location'}),
            'direction': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Direction/Orientation'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'pos_quality': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'name': _('Unique identifier or name for this feature'),
            'type': _('Type of feature being registered'),
            'area': _('General area or location description'),
            'direction': _('Direction or orientation if applicable'),
            'description': _('Detailed description of the feature'),
            'comment': _('Additional comments or notes'),
            'pos_quality': _('Quality/accuracy of the position measurement'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('name', 'type', 'pos_quality', 'date'):
            self.fields[name].required = True
        self.geometry_result = None
        self.geometry_changed = False
        self.initial_geojson = None
        if self.instance.pk is not None:
            self.initial_geojson = json.dumps(feature_geojson(self.instance))
            self.initial.setdefault('geojson_data', self.initial_geojson)

    @property
    def geometry_warnings(self):
        return self.geometry_result.warnings if self.geometry_result is not None else ()

    def _is_initial_geojson(self, text):
        if self.initial_geojson is None:
            return False
        try:
            return json.loads(text) == json.loads(self.initial_geojson)
        except ValueError:
            return False

    def clean_geojson_data(self):
        text = (self.cleaned_data.get('geojson_data') or '').strip()
        if not text:
            raise ValidationError(_('Nothing drawn on the map: draw at least one point, line '
                                    'or polygon.'))
        if self._is_initial_geojson(text):
            # Not touched in the editor: keep the stored geometry as it is (also a stored
            # geometry that the checks of today would refuse).
            self.geometry_changed = False
            return text
        try:
            result = from_geojson(text)
        except GeometryError as error:
            raise ValidationError(str(error))
        if self.instance.pk is not None and same_geometry(result, self.instance):
            self.geometry_changed = False
        else:
            self.geometry_changed = True
            self.geometry_result = result
        return text

    def save(self, commit=True):
        """The feature with the attributes, and the drawn geometry if it changed
        (``GeometryResult.apply_to``: all three columns and the source fields). The view
        sets ``created_by`` / ``modified_by``."""
        instance = super().save(commit=False)
        if self.geometry_changed and self.geometry_result is not None:
            self.geometry_result.apply_to(instance)
            instance.transform_note = map_transform_note(self.geometry_result)
        if commit:
            instance.save()
            self.save_m2m()
        return instance
