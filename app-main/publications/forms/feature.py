"""Forms for working with features."""

import os

from django import forms
from django.forms import ModelForm
from publications.geometry import (
    GeometryError, feature_geojson, from_geojson, from_vertices, map_transform_note,
    parse_srid, plausibility_warnings, same_geometry,
)
from publications.forms.publication import (
    MultipleFileField, MultipleFileInput, max_upload_size_bytes, max_upload_size_mb,
)
from publications import feature_import
from publications.models import Feature
from django.core.exceptions import ValidationError

from django.utils.translation import gettext_lazy as _
import json


# Help list of reference systems for Greenland (plan "features" T6). Any EPSG code PROJ
# knows is accepted; these are offered in the field's datalist. EPSG numbers checked against
# PROJ in the container (GDAL SpatialReference names) on 2026-11-23.
GREENLAND_SRIDS = (
    (4326, 'WGS84, longitude / latitude (degrees)'),
    (4747, 'GR96, longitude / latitude (degrees)'),
    *((3178 + i, f'GR96 / UTM zone {18 + i}N') for i in range(12)),       # EPSG:3178-3189
    *((32618 + i, f'WGS84 / UTM zone {18 + i}N') for i in range(12)),     # EPSG:32618-32629
    (3857, 'WGS84 / Web Mercator (pseudo-Mercator, metres)'),
)

DATE_INPUT_FORMATS = ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']


def _date_widget():
    return forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'})


class AddFeatureByCoordinatesForm(ModelForm):
    """Add or edit a one-point feature by its coordinates (plan "features" T6).

    ``x_coordinate`` / ``y_coordinate`` in the CRS ``spatial_reference_system`` (any EPSG code
    PROJ knows; ``GREENLAND_SRIDS`` is the help list). Axis order is always x = easting /
    longitude, y = northing / latitude (publications.geometry). The point is built and
    transformed to WGS84 with ``geometry.from_vertices``; its GeometryError (unknown EPSG,
    coordinates that can't be transformed, latitude beyond 90 after the transform) is a form
    error and blocks the save.

    Problems that may be right (outside Greenland, values that look swapped, a UTM easting
    outside the zone) are not errors: after ``is_valid()`` they are in
    ``coordinate_warnings``, and the view asks for a confirmation before saving.

    With an instance (edit), the view passes the coordinates as entered as ``initial``. If
    x, y and the EPSG code are unchanged, the stored geometry and its source fields are kept
    (attribute-only edit; ``geometry_changed`` False, no warnings). Otherwise ``save()``
    replaces the geometry and ``source_srid``, ``source_geometry``, ``transform_note``
    (``GeometryResult.apply_to``); ``lines``/``polys`` stay empty. The view sets
    ``created_by`` / ``modified_by``.
    """

    x_coordinate = forms.FloatField(
        label=_('Easting / Longitude (x)'),
        help_text=_('UTM easting in metres, or longitude in decimal degrees (west is '
                    'negative, e.g. -51.7).'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
    )
    y_coordinate = forms.FloatField(
        label=_('Northing / Latitude (y)'),
        help_text=_('UTM northing in metres, or latitude in decimal degrees (e.g. 64.2).'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
    )
    spatial_reference_system = forms.CharField(
        max_length=20,
        label=_('Coordinate reference system (EPSG code)'),
        help_text=_('Any EPSG code, e.g. 4326 (WGS84 lon/lat) or 32622 (WGS84 / UTM 22N); '
                    'pick one from the list or type the code.'),
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 4326',
                                      'list': 'srid-help-list', 'autocomplete': 'off'}),
    )
    date = forms.DateField(
        widget=_date_widget(), input_formats=DATE_INPUT_FORMATS, required=True,
        help_text=_('Date when the feature was observed/measured'),
    )
    observation_date = forms.DateField(
        widget=_date_widget(), input_formats=DATE_INPUT_FORMATS, required=False,
        label=_('GNSS observation date'),
        help_text=_('GNSS observation date, basis for epoch calculations; empty = the feature '
                    'date is used.'),
    )

    # The coordinate block of the template, in this order; the rest is "Feature details".
    location_fields = ('x_coordinate', 'y_coordinate', 'spatial_reference_system',
                       'pos_quality', 'observation_date')
    srid_help_list = GREENLAND_SRIDS

    class Meta:
        model = Feature
        fields = ['name', 'type', 'area', 'date', 'observation_date', 'direction',
                  'description', 'comment', 'pos_quality']
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
        self.coordinate_warnings = ()

    @property
    def location_boundfields(self):
        return [self[name] for name in self.location_fields]

    @property
    def detail_boundfields(self):
        return [field for field in self.visible_fields()
                if field.name not in self.location_fields]

    def clean_spatial_reference_system(self):
        try:
            return parse_srid(self.cleaned_data.get('spatial_reference_system'))
        except GeometryError as error:
            raise ValidationError(str(error))

    def _initial_coordinates(self):
        """(srid, x, y) the edit form started with, or None (add, or not parseable)."""
        if self.instance.pk is None:
            return None
        try:
            return (parse_srid(self.initial.get('spatial_reference_system')),
                    float(self.initial.get('x_coordinate')),
                    float(self.initial.get('y_coordinate')))
        except (GeometryError, TypeError, ValueError):
            return None

    def clean(self):
        cleaned_data = super().clean()
        x = cleaned_data.get('x_coordinate')
        y = cleaned_data.get('y_coordinate')
        srid = cleaned_data.get('spatial_reference_system')
        if x is None or y is None or srid is None:
            return cleaned_data   # the field errors say what is missing
        if self._initial_coordinates() == (srid, x, y):
            self.geometry_changed = False   # attribute-only edit: keep the stored geometry
            return cleaned_data
        try:
            result = from_vertices('point', [(x, y)], srid)
        except GeometryError as error:
            self.add_error(None, str(error))
            return cleaned_data
        self.geometry_result = result
        self.geometry_changed = True
        self.coordinate_warnings = tuple(plausibility_warnings(srid, x, y)) + result.warnings
        return cleaned_data

    @property
    def wgs84_point(self):
        """The new point in WGS84 (for the confirm page), or None."""
        if self.geometry_result is None or self.geometry_result.points is None:
            return None
        return self.geometry_result.points[0]

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.geometry_changed and self.geometry_result is not None:
            self.geometry_result.apply_to(instance)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


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


# --- Files and images of a feature (plan "features" T8, T8a; roadmap FA-R64) ---------------
# Same limit per file as appendices (settings.MAX_UPLOAD_SIZE_MB; nginx's limit on /find/ is
# the ceiling for the whole request).
#
# Files (T8a, owner 2026-11-23): any type except those a browser runs as active content
# (stored XSS: media is served from the app's own origin). Only the last extension counts
# (``x.svg.zip`` is fine, ``x.zip.svg`` is not); case does not matter. Files without an
# extension are accepted: the media view serves every type outside its small inline list as a
# download (attachment, application/octet-stream, nosniff), so a browser never renders them.
# The block-list is the second line of defence, for files opened outside the app.

FEATURE_FILE_BLOCKED_EXTENSIONS = frozenset({
    '.html', '.htm', '.xhtml', '.xht', '.shtml',   # HTML
    '.mht', '.mhtml',                              # HTML web archives (rendered as HTML)
    '.svg', '.svgz',                               # SVG runs scripts
    '.js', '.mjs',                                 # JavaScript
    '.hta',                                        # HTML application (runs as a program)
    '.swf',                                        # Flash
})
# Raster formats Pillow checks and thumbnails (webp: Pillow in the image is built with it,
# test_feature_media checks PIL.features.check('webp')). Other formats go in as files.
FEATURE_IMAGE_EXTENSIONS = frozenset({
    '.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.webp'})

FEATURE_BLOCKED_TYPES_TEXT = ', '.join(sorted(FEATURE_FILE_BLOCKED_EXTENSIONS))
FEATURE_ZIP_HINT = 'Such files (e.g. SVG figures) can be uploaded inside a .zip archive.'


def upload_extension(name):
    """Last extension of ``name``, lower case, with trailing dots and spaces ignored
    (``'x.SVG. '`` -> ``'.svg'``); ``''`` for a name without extension."""
    return os.path.splitext(os.path.basename(str(name)).rstrip('. '))[1].lower()


def _check_size(uploaded_file):
    if uploaded_file.size > max_upload_size_bytes():
        raise ValidationError(
            f'File "{uploaded_file.name}" is too large. Maximum file size is '
            f'{max_upload_size_mb()} MB per file.')


def _check_upload(uploaded_file, extensions):
    """ValidationError if ``uploaded_file`` is over the limit or has another extension than
    ``extensions`` (allow-list; images)."""
    _check_size(uploaded_file)
    if upload_extension(uploaded_file.name) not in extensions:
        raise ValidationError(
            f'File "{uploaded_file.name}" has an unsupported file type. '
            f'Allowed types: {", ".join(sorted(extensions))}. '
            f'Other formats can be uploaded as files.')


def check_feature_file(uploaded_file):
    """ValidationError if ``uploaded_file`` is over the limit or of a blocked type."""
    _check_size(uploaded_file)
    if upload_extension(uploaded_file.name) in FEATURE_FILE_BLOCKED_EXTENSIONS:
        raise ValidationError(
            f'File "{uploaded_file.name}" is of a blocked file type. Blocked types (web pages, '
            f'scripts and SVG, which a browser would run): {FEATURE_BLOCKED_TYPES_TEXT}. '
            f'{FEATURE_ZIP_HINT}')


class MultipleImageField(forms.ImageField):
    """ImageField for several files (Pillow checks each one). Size and type are checked
    before Pillow opens the file."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        if not files:
            return single_file_clean(None, initial)   # required / empty handling
        cleaned = []
        for uploaded_file in files:
            _check_upload(uploaded_file, FEATURE_IMAGE_EXTENSIONS)
            cleaned.append(single_file_clean(uploaded_file, initial))
        return cleaned


class _FeatureUploadForm(forms.Form):
    """Common part: the limit per file in the help text and as ``data-max-size-mb``."""
    files_field = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields[self.files_field]
        field.widget.attrs['data-max-size-mb'] = str(self.max_size_mb)
        field.help_text = f'{field.help_text} Maximum {self.max_size_mb} MB per file.'

    @property
    def max_size_mb(self):
        return max_upload_size_mb()


class FeatureFileUploadForm(_FeatureUploadForm):
    """Upload one or more files to a feature (plan "features" T8)."""
    files_field = 'feature_files'
    blocked_types = FEATURE_BLOCKED_TYPES_TEXT   # shown on the upload page (T8a)
    zip_hint = FEATURE_ZIP_HINT
    feature_files = MultipleFileField(
        label='Files',
        widget=MultipleFileInput(attrs={'class': 'form-control'}),   # any type (T8a)
        help_text=('Any file type (documents, spreadsheets, instrument data, archives) except '
                   'the blocked types listed above.'))
    description = forms.CharField(
        required=False, max_length=1000,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Optional; the same description is stored for every file of this upload.')

    def clean_feature_files(self):
        files = self.files.getlist('feature_files')
        for uploaded_file in files:
            check_feature_file(uploaded_file)
        return files


class FeatureImageUploadForm(_FeatureUploadForm):
    """Upload one or more images to a feature (plan "features" T8). Each image is checked
    with Pillow; a thumbnail is made after the upload (utils_models)."""
    files_field = 'feature_images'
    feature_images = MultipleImageField(
        label='Images',
        widget=MultipleFileInput(attrs={
            'accept': ','.join(sorted(FEATURE_IMAGE_EXTENSIONS)), 'class': 'form-control'}),
        help_text='JPEG, PNG, GIF, TIFF or WebP.')
    caption = forms.CharField(
        required=False, max_length=1000,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Optional; the same caption is stored for every image of this upload.')


# --- Excel import of features (plan "features" T10, roadmap FA-R63) -------------------------

class FeatureImportFileForm(forms.Form):
    """Step 1 of the Excel import: the .xlsx file with the sheet "Features". The file is
    read in memory (publications.feature_import) and not stored."""
    file = forms.FileField(
        label='Excel file (.xlsx)',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx'}),
        help_text=f'An .xlsx file with a sheet "{feature_import.SHEET_NAME}", at most '
                  f'{feature_import.MAX_FILE_MB} MB and {feature_import.MAX_VERTICES} vertex '
                  f'rows.')

    def clean_file(self):
        uploaded_file = self.cleaned_data['file']
        if os.path.splitext(uploaded_file.name)[1].lower() != '.xlsx':
            raise ValidationError('Only Excel files (.xlsx) can be imported.')
        if uploaded_file.size > feature_import.MAX_FILE_MB * 1024 * 1024:
            raise ValidationError(f'The file is larger than {feature_import.MAX_FILE_MB} MB.')
        return uploaded_file
