# Generated by Django 4.1.4 on 2023-03-02 21:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('publications', '0016_urlobject_publication_publications_urls'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageObject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('modified_date', models.DateTimeField(auto_now=True)),
                ('original_URL', models.CharField(blank=True, max_length=1000)),
                ('caption', models.TextField(max_length=1000)),
                ('created_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_modified', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('modified_date', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(blank=True, max_length=100)),
                ('type', models.CharField(blank=True, choices=[('PHOTO', 'Photo'), ('SAMPLE', 'Sample'), ('BOREHOLE', 'Borehole'), ('GEOPHYSICAL DATA', 'Geophysical data'), ('FIELD MEASUREMENT', 'Field measurement'), ('LAB MEASUREMENT', 'Lab measurement'), ('RESOURCE', 'Resource'), ('OTHER', 'Other')], default='OTHER', max_length=30)),
                ('area', models.CharField(blank=True, max_length=100)),
                ('date', models.DateField(blank=True)),
                ('direction', models.CharField(blank=True, max_length=100)),
                ('description', models.TextField(blank=True, max_length=65535)),
                ('comment', models.TextField(blank=True, max_length=65535)),
                ('pos_quality', models.CharField(blank=True, choices=[('Approximate', 'Approximate'), ('GPS (phase)', 'GPS (phase)'), ('GPS (code)', 'GPS (code)'), ('Unknown', 'Unknown')], default='Unknown', max_length=30)),
                ('quality', models.SmallIntegerField(choices=[(0, 'Current'), (10, 'Created'), (20, 'Changed'), (40, 'Rejected'), (50, 'Obsolete')], default=10)),
                ('URLs', models.ManyToManyField(blank=True, to='publications.urlobject')),
                ('created_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('files', models.ManyToManyField(blank=True, to='publications.fileobject')),
                ('images', models.ManyToManyField(blank=True, to='publications.imageobject')),
                ('modified_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_modified', to=settings.AUTH_USER_MODEL)),
                ('publications', models.ManyToManyField(blank=True, to='publications.publication')),
            ],
            options={
                'permissions': (('edit_own_feature', 'Can edit own featuress'), ('delete_own_feature', 'Can delete own features')),
            },
        ),
    ]
