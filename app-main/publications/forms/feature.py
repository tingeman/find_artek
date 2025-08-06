"""Forms for working with features."""

from django import forms
from django.forms import ModelForm
from publications.models import Feature
from django.core.exceptions import ValidationError
from django.contrib.gis.gdal import SpatialReference
from django.contrib.gis.geos import Point, MultiPoint
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
    """
    Form for adding a multipoint feature using Leaflet map input.
    Allows users to select multiple points on a map which will be stored as a MultiPoint geometry.
    """
    
    # Hidden field to store the GeoJSON data from the map
    geojson_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )
    
    # Hidden field to store the SRID automatically from the map
    map_srid = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial="4326"  # Default to WGS84 (used by Leaflet)
    )
    
    # Date field with proper widget (same as the coordinates form)
    date = forms.DateField(
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        ),
        input_formats=['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d'],
        required=True,
        help_text=_("Date when the feature was observed/measured")
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
        # Make required fields obvious
        self.fields['name'].required = True
        self.fields['type'].required = True
        self.fields['pos_quality'].required = True
        self.fields['date'].required = True
        
        # Add help text for the map
        self.geojson_help_text = _(
            "Use the map to select points. Click to add points. "
            "You can add multiple points which will be saved as a multipoint geometry."
        )
        
    def clean_geojson_data(self):
        """Validate GeoJSON data from the map"""
        geojson_data = self.cleaned_data.get('geojson_data')
        
        if not geojson_data:
            raise ValidationError(_('No points selected on the map. Please add at least one point.'))
        
        try:
            data = json.loads(geojson_data)
            
            # Verify that we have a valid GeoJSON with points
            if 'type' not in data or data['type'] != 'FeatureCollection':
                raise ValidationError(_('Invalid GeoJSON data format'))
                
            if 'features' not in data or not data['features']:
                raise ValidationError(_('No points found in the GeoJSON data'))
            
            # Check that we have at least one point
            points_count = len(data['features'])
            if points_count == 0:
                raise ValidationError(_('No points selected on the map. Please add at least one point.'))
            
            # Validate each point's coordinates
            for feature in data['features']:
                if feature['geometry']['type'] != 'Point':
                    raise ValidationError(_('Only point features are supported'))
                    
                coords = feature['geometry']['coordinates']
                if len(coords) < 2:
                    raise ValidationError(_('Invalid coordinates in GeoJSON'))
                
                # Basic validation for WGS84 coordinates
                lon, lat = coords[0], coords[1]
                if not (-180 <= lon <= 180):
                    raise ValidationError(_('Longitude value out of range (-180 to 180)'))
                if not (-90 <= lat <= 90):
                    raise ValidationError(_('Latitude value out of range (-90 to 90)'))
            
            return geojson_data
            
        except json.JSONDecodeError:
            raise ValidationError(_('Invalid GeoJSON format'))
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        geojson_data = cleaned_data.get('geojson_data')
        date = cleaned_data.get('date')
        name = cleaned_data.get('name')
        pos_quality = cleaned_data.get('pos_quality')
        
        # Check that all required fields are provided
        if not name:
            self.add_error('name', _('Feature name is required'))
        
        if not pos_quality:
            self.add_error('pos_quality', _('Position quality is required'))
        
        if not date:
            self.add_error('date', _('Date is required'))
        
        if not geojson_data:
            self.add_error('geojson_data', _('No points selected on the map'))
                
        return cleaned_data
    
    def save(self, commit=True):
        """
        Override the save method to create a MultiPoint geometry from the GeoJSON data
        before saving the model instance.
        """
        instance = super().save(commit=False)
        
        # Get GeoJSON data
        geojson_data = self.cleaned_data.get('geojson_data')
        if geojson_data:
            try:
                data = json.loads(geojson_data)
                points = []
                
                # Extract point coordinates from GeoJSON
                for feature in data['features']:
                    if feature['geometry']['type'] == 'Point':
                        coords = feature['geometry']['coordinates']
                        # Create Point objects (x=lon, y=lat for WGS84)
                        points.append(Point(coords[0], coords[1]))
                
                # Create MultiPoint geometry from the points
                if points:
                    multipoint = MultiPoint(points)
                    
                    # Set the geometry field - the exact field name depends on your model
                    # Assuming your Feature model has a 'geometry' field
                    instance.geometry = multipoint
                    
                    # Get SRID from the form (default is 4326 for WGS84)
                    srid = self.cleaned_data.get('map_srid', '4326')
                    try:
                        instance.geometry.srid = int(srid)
                    except ValueError:
                        # Default to WGS84 if there's an issue
                        instance.geometry.srid = 4326
            
            except (json.JSONDecodeError, KeyError, IndexError):
                # If there's an error processing the GeoJSON, we'll let the form validation handle it
                pass
        
        if commit:
            instance.save()
        
        return instance