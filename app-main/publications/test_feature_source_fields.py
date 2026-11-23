"""Feature source fields, epoch date and the add-by-map save (plan "features" T4).

- Feature.source_srid / source_geometry / transform_note / observation_date (migration 0006)
  are optional; features without them (all features registered before) save and read as
  before, points included (raw ST_AsText as in test_feature_geometry, FA-R101).
- Feature.epoch_date = observation_date or date.
- GeometryResult.apply_to + save stores all three geometry columns.
- AddFeatureByMap.save() keeps the points (FA-R107: it set an unknown attribute before) and
  AddFeatureByMapView sets created_by and modified_by.
"""
import datetime

from django.db import connection

from publications.forms import AddFeatureByMap
from publications.geometry import from_geojson, from_vertices
from publications.models import Feature
from publications.test_factories import page_path
from publications.test_feature_geometry import stored_points_wkt
from publications.test_report_access import ReportAccessTestBase

DAY = datetime.date(2001, 7, 15)
MAP_POINTS = ('{"type": "FeatureCollection", "features": ['
              '{"type": "Feature", "geometry": {"type": "Point", "coordinates": [-50.5, 67.0]}},'
              '{"type": "Feature", "geometry": {"type": "Point", "coordinates": [-51.5, 68.0]}}]}')


def stored_wkt(feature, column):
    """``column`` of the feature as MariaDB has it (ST_AsText), or None for NULL."""
    assert column in ('points', 'lines', 'polys')
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT ST_AsText(`{column}`) FROM publications_feature WHERE id = %s',
                       [feature.pk])
        return cursor.fetchone()[0]


class FeatureSourceFieldTests(ReportAccessTestBase):

    def test_epoch_date_without_observation_date_is_the_date(self):
        feature = Feature(name='f', date=DAY)
        self.assertEqual(feature.epoch_date, DAY)

    def test_epoch_date_with_observation_date(self):
        observed = datetime.date(2001, 7, 20)
        feature = Feature(name='f', date=DAY, observation_date=observed)
        self.assertEqual(feature.epoch_date, observed)

    def test_existing_style_feature_saves_and_reads_points(self):
        feature = Feature.objects.create(
            name='Old', date=DAY,
            points=from_vertices('point', [(-50.5, 67.0)], 4326).points)
        feature = Feature.objects.get(pk=feature.pk)
        self.assertIsNone(feature.source_srid)
        self.assertIsNone(feature.source_geometry)
        self.assertEqual(feature.transform_note, '')
        self.assertIsNone(feature.observation_date)
        self.assertEqual(feature.epoch_date, DAY)
        self.assertIsNotNone(stored_points_wkt(feature), 'points stored as NULL')
        self.assertEqual(feature.points.coords, ((-50.5, 67.0),))
        # Saving again (e.g. after an attribute change) keeps it so.
        feature.name = 'Old, renamed'
        feature.save()
        self.assertIsNotNone(stored_points_wkt(feature))

    def test_new_fields_saved(self):
        result = from_vertices('point', [(430000, 7450000)], 3182)
        feature = result.apply_to(Feature(name='New', date=DAY,
                                          observation_date=datetime.date(2001, 7, 16)))
        feature.save()
        feature = Feature.objects.get(pk=feature.pk)
        self.assertEqual(feature.source_srid, 3182)
        self.assertEqual(feature.source_geometry, result.source_geometry)
        self.assertIn('MULTIPOINT', feature.source_geometry)
        self.assertEqual(feature.transform_note, result.transform_note)
        self.assertIn('approximate', feature.transform_note)
        self.assertEqual(feature.observation_date, datetime.date(2001, 7, 16))
        self.assertEqual(feature.epoch_date, datetime.date(2001, 7, 16))
        self.assertIsNotNone(stored_points_wkt(feature), 'points stored as NULL')
        self.assertAlmostEqual(feature.points[0].x, result.points[0].x, places=6)

    def test_apply_to_stores_every_kind(self):
        result = from_geojson({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [-51, 67]}},
            {'type': 'Feature', 'geometry': {'type': 'LineString',
                                             'coordinates': [[-51, 67], [-52, 68]]}},
            {'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [
                [[-51, 67], [-50, 67], [-50, 68]]]}},
        ]})
        feature = result.apply_to(Feature(name='Mixed', date=DAY))
        feature.save()
        for column in ('points', 'lines', 'polys'):
            with self.subTest(column=column):
                self.assertIsNotNone(stored_wkt(feature, column), f'{column} stored as NULL')
        self.assertTrue(Feature.objects.get(pk=feature.pk).source_geometry
                        .startswith('GEOMETRYCOLLECTION'))

    def test_apply_to_clears_other_kinds(self):
        feature = from_vertices('line', [(-51, 67), (-52, 68)], 4326).apply_to(
            Feature(name='Edit', date=DAY))
        feature.save()
        from_vertices('point', [(-51, 67)], 4326).apply_to(feature)
        feature.save()
        self.assertIsNone(stored_wkt(feature, 'lines'))
        self.assertIsNotNone(stored_wkt(feature, 'points'))


class AddFeatureByMapSaveTests(ReportAccessTestBase):

    def form_data(self, name='By map'):
        return {'name': name, 'type': Feature.PHOTO, 'date': '2000-01-01',
                'pos_quality': 'Unknown', 'geojson_data': MAP_POINTS}

    def test_form_save_keeps_points(self):
        form = AddFeatureByMap(data=self.form_data())
        self.assertTrue(form.is_valid(), form.errors)
        feature = form.save()
        self.assertFalse(hasattr(feature, 'geometry'))
        self.assertIsNotNone(stored_points_wkt(feature), 'points stored as NULL')
        feature = Feature.objects.get(pk=feature.pk)
        self.assertEqual(feature.points.coords, ((-50.5, 67.0), (-51.5, 68.0)))
        self.assertEqual(feature.source_srid, 4326)
        # features T5: a map drawing is marked as such (feature page: "digitized on the map").
        self.assertEqual(feature.transform_note,
                         'EPSG:4326 (no transformation); digitized on the map (WGS84)')

    def test_form_rejects_invalid_coordinates(self):
        data = self.form_data()
        data['geojson_data'] = ('{"type": "FeatureCollection", "features": [{"type": "Feature",'
                                ' "geometry": {"type": "Point", "coordinates": [-50.5, 67, 1, 2]}}]}')
        form = AddFeatureByMap(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('geojson_data', form.errors)

    def test_view_sets_created_by_and_modified_by(self):
        self.client.force_login(self.dtu_own)
        response = self.client.post(page_path('add_feature_by_map', report_pk=self.pub.pk),
                                    self.form_data())
        self.assertEqual(response.status_code, 302)
        feature = Feature.objects.get(name='By map')
        self.assertEqual(feature.created_by, self.dtu_own)
        self.assertEqual(feature.modified_by, self.dtu_own)
        self.assertEqual(list(feature.publications.all()), [self.pub])
        self.assertIsNotNone(stored_points_wkt(feature))
