"""Feature geometry: build, check and transform to WGS84 (plan "features" T4, design note 2).

The one place for geometry handling of features. The map, coordinate entry and the Excel
import build their geometries here; the model field (``publications.fields.MultiPointField``,
FA-R101) takes care of writing them to MariaDB.

A feature has three geometry columns in EPSG:4326: ``points`` (MultiPoint), ``lines``
(MultiLineString) and ``polys`` (MultiPolygon). A feature may hold several kinds.

API
---

- ``GeometryError(ValueError)``: input that can't become a feature geometry; ``str(error)``
  is a message for the user.
- ``WGS84 = 4326``, ``GREENLAND_BOX = (-75, 58, -10, 85)`` (lon_min, lat_min, lon_max,
  lat_max; outside it is a warning only).
- ``parse_srid(value) -> int``: ``4326``, ``'4326'`` or ``'EPSG:4326'``; GeometryError for
  anything else or a code PROJ doesn't know.
- ``spatial_reference(srid) -> SpatialReference``: GDAL's SRS for an EPSG code;
  GeometryError if unknown.
- ``is_gr96(srid) -> bool``: the CRS is on the GR96 datum (Greenland 1996).
- ``transform_note(srid) -> str``: e.g. ``'EPSG:32622 -> EPSG:4326 (PROJ via GDAL 3.10.3)'``;
  GR96 sources get ``'; approximate (~1 m): no time-dependent transformation'`` appended;
  ``'EPSG:4326 (no transformation)'`` for WGS84 input.
- ``from_geojson(data, srid=4326) -> GeometryResult``: a GeoJSON FeatureCollection, Feature
  or geometry (dict or JSON text; as leaflet-draw writes it, lon/lat in WGS84). Accepts
  Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon; rejects other types
  (also GeometryCollection) and empty input.
- ``from_vertices(kind, vertices, srid) -> GeometryResult``: ``kind`` 'point' | 'line' |
  'polygon' (case-insensitive), ``vertices`` a sequence of (x, y) in EPSG ``srid``. Several
  points make one MultiPoint, a line one LineString, a polygon one ring.
- ``GeometryResult``: ``points``, ``lines``, ``polys`` (EPSG:4326 or None), ``source_srid``,
  ``source_geometry`` (WKT in the source coordinates; GEOMETRYCOLLECTION if several kinds),
  ``transform_note``, ``warnings`` (tuple of str); ``apply_to(feature)`` sets the three
  geometry columns (None clears a column) and ``source_srid``, ``source_geometry``,
  ``transform_note``; it does not save.
- ``MAP_DIGITIZED = 'digitized on the map (WGS84)'``, ``map_transform_note(result)``: the
  ``transform_note`` of a geometry drawn on the map (T5), e.g.
  ``'EPSG:4326 (no transformation); digitized on the map (WGS84)'``.
- ``source_origin(feature) -> 'map' | 'entered' | 'unknown'``: where the feature's geometry
  came from (map drawing; coordinates entered or imported; features registered before the
  source fields existed).
- ``feature_geojson(feature) -> dict``: the feature's stored geometry as a GeoJSON
  FeatureCollection (one Feature per non-empty column, exact coordinates), as the map editor
  loads it.
- ``same_geometry(result, feature, tolerance=1e-9) -> bool``: the result has the same
  geometry as the feature's stored columns (a kind missing on one side counts as different).

Rules
-----

- Coordinates are numbers (no bool, NaN or infinity); a vertex has 2 values (a third, the
  height, is ignored).
- A line needs at least 2 distinct vertices; a polygon ring at least 3 distinct vertices. An
  open ring is closed automatically. A self-intersecting polygon is an error, and so are
  polygons of one feature that overlap (an invalid MultiPolygon).
- Transformation in Python with GDAL/PROJ (MariaDB has no ST_Transform; roadmap FA-R4).
  Axis order is Django's traditional GIS order: x = longitude / easting, y = latitude /
  northing, also for EPSG:4326 and EPSG:4747, whose authority order is lat/lon (Django sets
  OAMS_TRADITIONAL_GIS_ORDER on every SpatialReference). GR96 -> WGS84 is the null
  transformation PROJ offers (no time-dependent ITRF transformation), good to about 1 m;
  the note says so.
- After the transform: longitude outside -180..180 or latitude outside -90..90 is an error;
  outside ``GREENLAND_BOX`` is a warning (returned in ``warnings``, not raised).
"""
import json
import math
import re
from dataclasses import dataclass, field

from django.contrib.gis import gdal
from django.contrib.gis.gdal import CoordTransform, GDALException, SpatialReference
from django.contrib.gis.geos import (
    GeometryCollection, LinearRing, LineString, MultiLineString, MultiPoint, MultiPolygon,
    Point, Polygon,
)

WGS84 = 4326
GREENLAND_BOX = (-75.0, 58.0, -10.0, 85.0)   # lon_min, lat_min, lon_max, lat_max

KINDS = ('point', 'line', 'polygon')
GEOJSON_TYPES = ('Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon',
                 'MultiPolygon')
GR96_REMARK = 'approximate (~1 m): no time-dependent transformation'

_SRID_RE = re.compile(r'^\s*(?:EPSG\s*:\s*)?(\d{1,9})\s*$', re.IGNORECASE)


class GeometryError(ValueError):
    """The input can't become a feature geometry. The message is meant for the user."""


# --- Reference systems -----------------------------------------------------------------------

def parse_srid(value):
    """The EPSG code in ``value`` (int, '3182' or 'EPSG:3182') as int; GeometryError if it
    is not a code or PROJ doesn't know it."""
    if isinstance(value, bool):
        raise GeometryError(f'"{value}" is not an EPSG code.')
    if isinstance(value, int):
        srid = value
    else:
        match = _SRID_RE.match(str(value or ''))
        if not match:
            raise GeometryError(f'"{value}" is not an EPSG code (e.g. 4326 or 32622).')
        srid = int(match.group(1))
    spatial_reference(srid)
    return srid


def spatial_reference(srid):
    """GDAL's SpatialReference for EPSG ``srid``; GeometryError if it is unknown."""
    if isinstance(srid, bool) or not isinstance(srid, int) or srid <= 0:
        raise GeometryError(f'"{srid}" is not an EPSG code.')
    try:
        return SpatialReference(srid)
    except (GDALException, TypeError, ValueError):
        raise GeometryError(f'Unknown coordinate reference system EPSG:{srid}.') from None


def is_gr96(srid):
    """True if EPSG ``srid`` is on the GR96 datum (EPSG:4747, 4909, GR96 / UTM 3178-3189)."""
    wkt = spatial_reference(srid).wkt
    return 'Greenland_1996' in wkt or 'Greenland 1996' in wkt


def gdal_version():
    """The GDAL version, e.g. '3.10.3'."""
    return '.'.join(str(part) for part in gdal.GDAL_VERSION)


def transform_note(srid):
    """How coordinates in EPSG ``srid`` became EPSG:4326 (stored on the feature)."""
    if srid == WGS84:
        return f'EPSG:{WGS84} (no transformation)'
    note = f'EPSG:{srid} -> EPSG:{WGS84} (PROJ via GDAL {gdal_version()})'
    if is_gr96(srid):
        note += f'; {GR96_REMARK}'
    return note


# --- Result ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class GeometryResult:
    """Geometries of one feature in EPSG:4326, with where they came from."""
    points: MultiPoint = None
    lines: MultiLineString = None
    polys: MultiPolygon = None
    source_srid: int = WGS84
    source_geometry: str = ''
    transform_note: str = ''
    warnings: tuple = field(default_factory=tuple)

    def apply_to(self, feature):
        """Set the geometry and source fields of ``feature`` (not saved)."""
        feature.points = self.points
        feature.lines = self.lines
        feature.polys = self.polys
        feature.source_srid = self.source_srid
        feature.source_geometry = self.source_geometry
        feature.transform_note = self.transform_note
        return feature


# --- Map drawings and stored geometry (plan "features" T5) -----------------------------------

MAP_DIGITIZED = 'digitized on the map (WGS84)'
FEATURE_COLUMNS = ('points', 'lines', 'polys')


def map_transform_note(result):
    """``transform_note`` for a geometry drawn on the map (marks it as digitized there)."""
    return f'{result.transform_note}; {MAP_DIGITIZED}'


def source_origin(feature):
    """'map' (drawn on the map), 'entered' (coordinates entered or imported) or 'unknown'
    (no source fields: registered before plan "features" T4)."""
    if feature.source_srid is None and not feature.source_geometry:
        return 'unknown'
    if MAP_DIGITIZED in (feature.transform_note or ''):
        return 'map'
    return 'entered'


def _as_lists(coords):
    if isinstance(coords, (tuple, list)):
        return [_as_lists(part) for part in coords]
    return coords


def feature_geojson(feature):
    """The stored geometry of ``feature`` as a GeoJSON FeatureCollection dict. Coordinates
    are the stored floats (not rounded), so the unchanged collection compares equal."""
    types = {'points': 'MultiPoint', 'lines': 'MultiLineString', 'polys': 'MultiPolygon'}
    features = []
    for column in FEATURE_COLUMNS:
        geom = getattr(feature, column)
        if geom is None or geom.empty:
            continue
        features.append({
            'type': 'Feature',
            'properties': {'column': column},
            'geometry': {'type': types[column], 'coordinates': _as_lists(geom.coords)},
        })
    return {'type': 'FeatureCollection', 'features': features}


def same_geometry(result, feature, tolerance=1e-9):
    """True if ``result`` (GeometryResult) has the geometry stored on ``feature``: per
    column both empty, or equal vertex by vertex within ``tolerance`` degrees."""
    for column in FEATURE_COLUMNS:
        new, old = getattr(result, column), getattr(feature, column)
        if old is not None and old.empty:
            old = None
        if (new is None) != (old is None):
            return False
        if new is None:
            continue
        try:
            if not new.equals_exact(old, tolerance):
                return False
        except Exception:   # GEOSException for geometries of different kinds
            return False
    return True


# --- Building --------------------------------------------------------------------------------

def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            value = float(str(value).strip())
        except (TypeError, ValueError):
            raise GeometryError(f'"{value}" is not a number.') from None
    value = float(value)
    if not math.isfinite(value):
        raise GeometryError('Coordinates must be finite numbers.')
    return value


def _vertex(position):
    """(x, y) from a position [x, y] or [x, y, z]."""
    if isinstance(position, (str, bytes)) or not hasattr(position, '__len__') \
            or len(position) not in (2, 3):
        raise GeometryError(f'A vertex needs two coordinates (x, y), not {position!r}.')
    return _number(position[0]), _number(position[1])


def _vertices(positions):
    if isinstance(positions, (str, bytes)) or not hasattr(positions, '__iter__'):
        raise GeometryError('Expected a list of vertices.')
    return [_vertex(position) for position in positions]


def _point(position):
    return Point(*_vertex(position))


def _line(positions):
    vertices = _vertices(positions)
    if len(set(vertices)) < 2:
        raise GeometryError('A line needs at least 2 different vertices.')
    return LineString(vertices)


def _ring(positions):
    vertices = _vertices(positions)
    if len(set(vertices)) < 3:
        raise GeometryError('A polygon needs at least 3 different vertices.')
    if vertices[0] != vertices[-1]:
        vertices.append(vertices[0])
    return LinearRing(vertices)


def _polygon(rings):
    if isinstance(rings, (str, bytes)) or not hasattr(rings, '__iter__'):
        raise GeometryError('Expected a list of polygon rings.')
    rings = [_ring(ring) for ring in rings]
    if not rings:
        raise GeometryError('A polygon needs at least 3 different vertices.')
    polygon = Polygon(*rings)
    if not polygon.valid:
        raise GeometryError(
            f'The polygon is not valid (e.g. its edges cross): {polygon.valid_reason}.')
    return polygon


def _build(points, lines, polys, srid):
    """GeometryResult from lists of Point, LineString and Polygon in EPSG ``srid``."""
    if not (points or lines or polys):
        raise GeometryError('No geometry: add at least one point, line or polygon.')
    source = {
        'points': MultiPoint(points, srid=srid) if points else None,
        'lines': MultiLineString(lines, srid=srid) if lines else None,
        'polys': MultiPolygon(polys, srid=srid) if polys else None,
    }
    if source['polys'] is not None and not source['polys'].valid:
        raise GeometryError('Polygons of one feature must not overlap or touch along an edge.')
    parts = [geom for geom in source.values() if geom is not None]
    source_wkt = parts[0].wkt if len(parts) == 1 else GeometryCollection(parts).wkt

    srs = spatial_reference(srid)
    transform = None if srid == WGS84 else CoordTransform(srs, spatial_reference(WGS84))
    result = {}
    for name, geom in source.items():
        if geom is None:
            result[name] = None
            continue
        if transform is not None:
            try:
                geom = geom.transform(transform, clone=True)
            except GDALException:
                raise GeometryError(
                    f'The coordinates can\'t be transformed from EPSG:{srid} to WGS84; '
                    'check the coordinates and the reference system.') from None
        geom.srid = WGS84
        result[name] = geom
    warnings = _check_range([geom for geom in result.values() if geom is not None], srid)
    return GeometryResult(source_srid=srid, source_geometry=source_wkt,
                          transform_note=transform_note(srid), warnings=tuple(warnings),
                          **result)


def _coords(geom):
    """All (lon, lat) pairs of a geometry."""
    if isinstance(geom, Point):
        yield geom.x, geom.y
    elif isinstance(geom, (LineString, LinearRing)):
        for coord in geom.coords:
            yield coord[0], coord[1]
    else:   # Polygon and collections iterate over their parts
        for part in geom:
            yield from _coords(part)


def _check_range(geoms, srid):
    """GeometryError if a coordinate is outside lon -180..180 / lat -90..90; a list with a
    warning if one is outside GREENLAND_BOX."""
    lon_min, lat_min, lon_max, lat_max = GREENLAND_BOX
    outside = False
    for geom in geoms:
        for lon, lat in _coords(geom):
            if not (math.isfinite(lon) and math.isfinite(lat)) \
                    or not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise GeometryError(
                    f'Coordinates out of range after transformation from EPSG:{srid} '
                    f'(longitude {lon:.6f}, latitude {lat:.6f}); check the coordinates, '
                    'their order (x = easting/longitude) and the reference system.')
            if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
                outside = True
    if outside:
        return ['Some coordinates are outside Greenland (longitude -75 to -10, latitude 58 '
                'to 85). Check the coordinates and the reference system.']
    return []


def from_vertices(kind, vertices, srid):
    """GeometryResult of one geometry ``kind`` ('point', 'line', 'polygon') from (x, y)
    ``vertices`` in EPSG ``srid`` (several points: one MultiPoint)."""
    kind = str(kind or '').strip().lower()
    if kind not in KINDS:
        raise GeometryError(f'Unknown geometry type "{kind}"; use point, line or polygon.')
    srid = parse_srid(srid)
    if kind == 'point':
        points = [Point(*vertex) for vertex in _vertices(vertices)]
        if not points:
            raise GeometryError('A point feature needs at least one vertex.')
        return _build(points, [], [], srid)
    if kind == 'line':
        return _build([], [_line(vertices)], [], srid)
    return _build([], [], [_polygon([vertices])], srid)


def _geojson_geometries(data):
    """The GeoJSON geometry objects in ``data`` (FeatureCollection, Feature or geometry)."""
    if not isinstance(data, dict):
        raise GeometryError('Invalid GeoJSON: expected an object.')
    kind = data.get('type')
    if kind == 'FeatureCollection':
        features = data.get('features')
        if not isinstance(features, list):
            raise GeometryError('Invalid GeoJSON: a FeatureCollection needs "features".')
        for feature in features:
            if not isinstance(feature, dict) or feature.get('type') != 'Feature':
                raise GeometryError('Invalid GeoJSON: expected a Feature.')
            yield from _geojson_geometries(feature)
    elif kind == 'Feature':
        if data.get('geometry') is not None:
            yield from _geojson_geometries(data['geometry'])
    elif kind in GEOJSON_TYPES:
        yield data
    else:
        raise GeometryError(f'Geometry type "{kind}" is not supported; use points, lines '
                            'and polygons.')


def from_geojson(data, srid=WGS84):
    """GeometryResult from GeoJSON ``data`` (dict or JSON text) with coordinates in EPSG
    ``srid`` (leaflet-draw: WGS84, x = lon)."""
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except ValueError:
            raise GeometryError('Invalid GeoJSON (not JSON).') from None
    srid = parse_srid(srid)
    points, lines, polys = [], [], []
    for geometry in _geojson_geometries(data):
        kind, coords = geometry['type'], geometry.get('coordinates')
        if coords is None or isinstance(coords, (str, bytes)) \
                or not hasattr(coords, '__iter__'):
            raise GeometryError(f'Invalid GeoJSON: {kind} without coordinates.')
        if kind == 'Point':
            points.append(_point(coords))
        elif kind == 'MultiPoint':
            points.extend(_point(position) for position in coords)
        elif kind == 'LineString':
            lines.append(_line(coords))
        elif kind == 'MultiLineString':
            lines.extend(_line(line) for line in coords)
        elif kind == 'Polygon':
            polys.append(_polygon(coords))
        else:   # MultiPolygon
            polys.extend(_polygon(polygon) for polygon in coords)
    return _build(points, lines, polys, srid)
