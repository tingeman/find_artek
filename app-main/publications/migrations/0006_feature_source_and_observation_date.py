"""Feature: where the geometry came from and the GNSS observation date (plan "features" T4).

Adds four nullable/blank columns to publications_feature (source_srid, source_geometry,
transform_note with default '', observation_date). Existing rows keep all their values; no
data migration."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publications', '0005_person_merge_person_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='feature',
            name='observation_date',
            field=models.DateField(blank=True, help_text='Basis for epoch calculations; defaults to the feature date when empty.', null=True, verbose_name='GNSS observation date'),
        ),
        migrations.AddField(
            model_name='feature',
            name='source_geometry',
            field=models.TextField(blank=True, help_text='WKT of the geometry in the coordinates as entered.', null=True),
        ),
        migrations.AddField(
            model_name='feature',
            name='source_srid',
            field=models.PositiveIntegerField(blank=True, help_text='EPSG code of the coordinates as entered (before the transformation to WGS84).', null=True, verbose_name='source EPSG code'),
        ),
        migrations.AddField(
            model_name='feature',
            name='transform_note',
            field=models.CharField(blank=True, default='', help_text='How the coordinates were transformed to WGS84 (EPSG:4326).', max_length=255),
        ),
    ]
