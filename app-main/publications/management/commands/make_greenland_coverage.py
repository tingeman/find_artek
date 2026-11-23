"""Write the coverage outline of the topographic map of Greenland (plan "features" T22, T23).

    python manage.py make_greenland_coverage SOURCE [--fill-km 45] [--buffer-km 12]
                                             [--tolerance-km 2.5] [--output PATH]

SOURCE: a land polygon file GDAL can read, in WGS84 longitude/latitude. Made from
**Natural Earth 10m land** (``ne_10m_land.shp`` from ``ne_10m_land.zip``, version 5.1.1;
https://www.naturalearthdata.com/, public domain). The Natural Earth files are not in the
repository: download and unzip them into a temporary folder, copy the folder into the container
and pass the ``.shp`` file.

Default output: ``publications/static/publications/data/greenland_topo_coverage.geojson``
(committed). What the map (``js/map/find-artek-map-layers.js``) does with it: the
Dataforsyningen topographic WMS draws opaque white outside its coverage (Greenland's land and a
blue sea band of roughly 15-40 km along the coast). The topographic layer is multiplied over the
Arctic SDI underlay, so that white shows the underlay, and the underlay is clipped to the
outside of this outline, so inside it no Arctic basemap coastline or name shows through (T23;
T22 clipped the topographic layer itself instead, which cut off names and islands at the coast).
Inside the outline the topographic map therefore has no backdrop: where the outline reaches
beyond the topographic map's blue sea band, its white shows. So the outline must stay inside
that band: hence the small seaward buffer (about 12 km). Wide fjords and bays (Scoresby Sund,
Disko Bay, Vaigat) are blue on the topographic map, so the outline fills them (``--fill-km``),
or the Arctic basemap would show inside them.

How the outline is made:

1. Every land polygon that intersects the Greenland box (``--bbox``, lon -75..-10, lat 59..84)
   is a candidate (multi-polygons are split into their polygons), cut to that box widened by
   15 degrees of longitude and 5 of latitude (the continents reach far south, where areas and
   distances in the polar projection are meaningless).
2. Greenland is the largest candidate. A smaller polygon is kept when it is at most
   ``--max-island-distance-km`` from Greenland, is smaller than ``--max-island-area-km2``, and
   is closer to Greenland than to every other large landmass (candidates of at least that
   area: Ellesmere and Baffin Island, Iceland), so Canadian islands across Nares Strait and
   Iceland are left out.
3. In EPSG:3413 (metres): fill fjords and bays by a morphological closing of the selected land
   with ``--fill-km`` (buffer outward by fill, then inward by fill), so water openings up to
   about 2 x fill wide are closed (default 45 km: about 90 km; ``--fill-km 0`` skips it).
   40 km would leave Disko Bay open: in Natural Earth its mouth, between Disko Island and the
   Aasiaat coast, is a little over 80 km wide (it closes from 42 km on). Then
   buffer seaward by ``--buffer-km``, cut out the other large landmasses buffered by
   ``LANDMASS_MARGIN_KM`` (2 km, so the outline never covers Ellesmere, Baffin Island or
   Iceland), fill the holes (enclosed water), simplify with ``--tolerance-km`` (topology
   preserving). Simplifying moves the edge by at most the tolerance, so along open coasts the
   outline lies between buffer - tolerance and buffer + tolerance from the coast: keep
   buffer + tolerance below the narrowest part of the blue sea band (about 15 km), since too
   small only shows a thin strip of the underlay along the coast, while too big shows the
   white border.
4. Back to WGS84, coordinates rounded to 4 decimals (at most about 11 m), one Feature with a
   (Multi)Polygon.

Writes no database rows and reads no media files.
"""
import json
import math
import os

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GeometryCollection, MultiPolygon, Polygon
from django.core.management.base import BaseCommand, CommandError

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'static', 'publications', 'data', 'greenland_topo_coverage.geojson')

WGS84 = 4326
METRIC_SRID = 3413          # NSIDC Sea Ice Polar Stereographic North, metres
GREENLAND_BBOX = (-75.0, 59.0, -10.0, 84.0)    # lon min, lat min, lon max, lat max
CUT_MARGIN_LON = 15.0
CUT_MARGIN_LAT = 5.0
SOURCE_NOTE = ('Natural Earth 10m land (https://www.naturalearthdata.com/, public domain); '
               'made by manage.py make_greenland_coverage')
DECIMALS = 4
LANDMASS_MARGIN_KM = 2.0     # other large landmasses are cut out with this margin
MAX_FILL_KM = 200.0          # a larger closing would start to fill Baffin Bay-sized water


def land_polygons(path):
    """Every polygon of every feature of every layer in `path` (WGS84), as GEOS Polygons."""
    try:
        source = DataSource(path)
    except Exception as error:     # GDALException, or a path GDAL can't open
        raise CommandError(f'Cannot read {path}: {error}') from error
    for layer in source:
        for feature in layer:
            geometry = feature.geom.geos
            geometry.srid = WGS84
            if isinstance(geometry, Polygon):
                yield geometry
            elif isinstance(geometry, MultiPolygon):
                for polygon in geometry:
                    polygon.srid = WGS84
                    yield polygon


def select_greenland(polygons, bbox=GREENLAND_BBOX, max_island_distance=100_000,
                     max_island_area=20_000e6):
    """The polygons that make up Greenland, in METRIC_SRID: (mainland, [islands], [large]).

    `large`: the other large landmasses (candidates of at least `max_island_area`, e.g.
    Ellesmere, Baffin Island, Iceland). `polygons`: WGS84 GEOS Polygons; distances in metres,
    areas in square metres.
    """
    box = Polygon.from_bbox(bbox)
    box.srid = WGS84
    # Cut to a larger box first: the continents (North America) are single polygons that reach
    # far south, where the polar projection is no good for areas or distances. Larger than
    # `bbox`, so a neighbour's coast just outside `bbox` (Ellesmere next to Pim Island at lon
    # -75) still counts in the distance test.
    lon_min, lat_min, lon_max, lat_max = bbox
    cut_box = Polygon.from_bbox((lon_min - CUT_MARGIN_LON, max(lat_min - CUT_MARGIN_LAT, 0.0),
                                 lon_max + CUT_MARGIN_LON, min(lat_max + CUT_MARGIN_LAT, 90.0)))
    cut_box.srid = WGS84
    candidates = []
    for polygon in polygons:
        if polygon.intersects(box):
            part = polygon.intersection(cut_box)
            if isinstance(part, Polygon):
                parts = [part]
            elif isinstance(part, GeometryCollection):     # MultiPolygon included
                parts = [item for item in part if isinstance(item, Polygon)]
            else:
                parts = []
            for item in parts:
                if not item.empty:
                    item.srid = WGS84
                    candidates.append(item.transform(METRIC_SRID, clone=True))
    if not candidates:
        raise CommandError('No land polygon in the Greenland box.')
    candidates.sort(key=lambda polygon: polygon.area, reverse=True)
    mainland, others = candidates[0], candidates[1:]
    large = [polygon for polygon in others if polygon.area >= max_island_area]
    islands = []
    for polygon in others:
        if polygon.area >= max_island_area:
            continue
        distance = polygon.distance(mainland)
        if distance > max_island_distance:
            continue
        if any(polygon.distance(other) < distance for other in large):
            continue
        islands.append(polygon)
    return mainland, islands, large


def without_holes(geometry):
    """`geometry` (Polygon or MultiPolygon) with only the exterior rings."""
    parts = [geometry] if isinstance(geometry, Polygon) else list(geometry)
    filled = MultiPolygon([Polygon(part.exterior_ring) for part in parts])
    filled.srid = geometry.srid
    return filled


def as_multipolygon(geometry):
    """The polygons of `geometry` as a MultiPolygon (lines and points of a collection dropped)."""
    if isinstance(geometry, MultiPolygon):
        result = geometry
    elif isinstance(geometry, Polygon):
        result = MultiPolygon([geometry])
    elif isinstance(geometry, GeometryCollection):
        result = MultiPolygon([part for part in geometry if isinstance(part, Polygon)])
    else:
        result = MultiPolygon([])
    result.srid = geometry.srid
    return result


def coverage_outline(mainland, islands, buffer_m, tolerance_m, fill_m=0.0, large=()):
    """Closed (fjords filled), buffered, filled, simplified outline in WGS84 (a MultiPolygon).

    Lengths in metres, geometries in METRIC_SRID. `large`: polygons the outline must not cover
    (cut out with a LANDMASS_MARGIN_KM margin).
    """
    land = MultiPolygon([mainland] + list(islands))
    land.srid = METRIC_SRID
    land = land.unary_union
    if fill_m > 0:
        # Morphological closing: water openings up to about 2 x fill_m wide are filled.
        land = land.buffer(fill_m).buffer(-fill_m)
    outline = land.buffer(buffer_m)
    if large:
        others = MultiPolygon(list(large))
        others.srid = METRIC_SRID
        outline = outline.difference(others.buffer(LANDMASS_MARGIN_KM * 1000))
    outline = without_holes(as_multipolygon(outline))
    outline = without_holes(as_multipolygon(
        outline.simplify(tolerance_m, preserve_topology=True)))
    outline.transform(WGS84)
    return outline


def vertex_count(geometry):
    return sum(len(ring) for polygon in geometry for ring in polygon)


def rounded(coordinates):
    if isinstance(coordinates[0], (int, float)):
        return [round(value, DECIMALS) for value in coordinates[:2]]
    return [rounded(part) for part in coordinates]


def feature_collection(outline, buffer_km, tolerance_km, fill_km=0.0):
    geometry = json.loads(outline.geojson)
    geometry['coordinates'] = rounded(geometry['coordinates'])
    return {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'properties': {
                'name': 'Greenland topographic map coverage (approximate)',
                'source': SOURCE_NOTE,
                'fill_km': fill_km,
                'buffer_km': buffer_km,
                'tolerance_km': tolerance_km,
            },
            'geometry': geometry,
        }],
    }


class Command(BaseCommand):
    help = ('Write the coverage outline of the Dataforsyningen topographic map (Greenland land '
            'with fjords filled, buffered seaward) from Natural Earth 10m land.')

    def add_arguments(self, parser):
        parser.add_argument('source', help='Land polygons in WGS84, e.g. ne_10m_land.shp.')
        parser.add_argument('--fill-km', type=float, default=45.0,
                            help='Close fjords and bays up to about twice this width before '
                                 'buffering (default 45; 0: no closing).')
        parser.add_argument('--buffer-km', type=float, default=12.0,
                            help='Seaward buffer around the land (default 12).')
        parser.add_argument('--tolerance-km', type=float, default=2.5,
                            help='Simplification tolerance (default 2.5).')
        parser.add_argument('--max-island-distance-km', type=float, default=100.0,
                            help='Islands farther from Greenland are left out (default 100).')
        parser.add_argument('--max-island-area-km2', type=float, default=20000.0,
                            help='Polygons at least this large count as other landmasses '
                                 '(default 20000).')
        parser.add_argument('--bbox', type=float, nargs=4, default=list(GREENLAND_BBOX),
                            metavar=('LON_MIN', 'LAT_MIN', 'LON_MAX', 'LAT_MAX'),
                            help='Box of the candidate polygons (default -75 59 -10 84).')
        parser.add_argument('--output', default=DEFAULT_OUTPUT,
                            help=f'Where to write the GeoJSON (default: {DEFAULT_OUTPUT}).')

    def handle(self, *args, **options):
        buffer_km = options['buffer_km']
        tolerance_km = options['tolerance_km']
        fill_km = options['fill_km']
        if not all(math.isfinite(value) for value in (buffer_km, tolerance_km, fill_km)):
            raise CommandError('--fill-km, --buffer-km and --tolerance-km must be finite.')
        if buffer_km <= 0 or tolerance_km < 0 or tolerance_km >= buffer_km:
            raise CommandError('Need buffer > 0 and 0 <= tolerance < buffer.')
        if fill_km < 0 or fill_km > MAX_FILL_KM:
            raise CommandError(f'Need 0 <= fill <= {MAX_FILL_KM:g} km.')
        mainland, islands, large = select_greenland(
            land_polygons(options['source']), bbox=tuple(options['bbox']),
            max_island_distance=options['max_island_distance_km'] * 1000,
            max_island_area=options['max_island_area_km2'] * 1e6)
        outline = coverage_outline(mainland, islands, buffer_km * 1000, tolerance_km * 1000,
                                   fill_m=fill_km * 1000, large=large)
        if outline.empty:
            raise CommandError('The outline is empty.')
        data = feature_collection(outline, buffer_km, tolerance_km, fill_km)
        text = json.dumps(data, separators=(',', ':')) + '\n'
        output = options['output']
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        with open(output, 'w', encoding='utf-8') as handle:
            handle.write(text)
        self.stdout.write(self.style.SUCCESS(
            f'{len(islands)} islands, {len(outline)} polygons, {vertex_count(outline)} vertices, '
            f'{len(text)} bytes written to {output}'))
