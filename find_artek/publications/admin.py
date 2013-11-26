# -*- coding: utf-8 -*-

from find_artek.publications.models import Publication, Person, PubType
from find_artek.publications.models import Authorship, Editorship, Supervisorship
from find_artek.publications.models import Feature, Keyword, Topic
from find_artek.publications.models import FileObject

from django.contrib.gis import admin
#from django.contrib.gis.maps.google import GoogleMap
from olwidget.admin import GeoModelAdmin


#GMAP = GoogleMap(key='AIzaSyBIagLz1ayoRbJZef1Er9h8WkWJF26hr44') # Can also set GOOGLE_MAPS_API_KEY in settings

#class GoogleAdmin(admin.OSMGeoAdmin):
#    extra_js = [GMAP.api_url + GMAP.key]
#    map_template = 'gis/admin/google.html'


class AuthorshipInline(admin.TabularInline):
    model = Authorship
    extra = 1


class EditorshipInline(admin.TabularInline):
    model = Editorship
    extra = 1


class SupervisorshipInline(admin.TabularInline):
    model = Supervisorship
    extra = 1


class PublicationAdmin(admin.ModelAdmin):
    list_display = ('number', 'title')
    inlines = (AuthorshipInline, EditorshipInline, SupervisorshipInline,)

    def save_model(self, request, obj, form, change):
        """When creating a new object, set the created_by field, else set the modified_by field.
        """
        if not change:
            if hasattr(obj.created_by):
                obj.created_by = request.user
        else:
            if hasattr(obj.modified_by):
                obj.modified_by = request.user
        obj.save()

    def save_formset(self, request, form, formset, change):
        """When creating a new object, set the created_by field, else set the modified_by field.
        Not sure if this is of interest to us.
        """
        if formset.model in [i.model for i in self.inlines]:
            instances = formset.save(commit=False)
            for obj in instances:
                if not change:
                    if hasattr(obj.created_by):
                        obj.created_by = request.user
                else:
                    if hasattr(obj.modified_by):
                        obj.modified_by = request.user
                obj.save()
        else:
            formset.save()


# Customize the map
class FeatureAdmin(GeoModelAdmin):
    list_display = ('name','modified_date',)
#    options = {
#        'layers': ['google.satellite'],
#        'default_lat': 44,
#        'default_lon': -72,
#    }

    # default zoom:
    zl = 4
    clon = -52.5
    clat = 67

    options = {'layers': ['osm.mapnik','google.satellite'],
        'map_options': {
            'controls': [
                         "LayerSwitcher",
                         "NavToolbar",
                         "PanZoom",
                         "Attribution"], },
#        'popups_outside': True,
#        'map_div_style': {'width': '600px', 'height': '360px'},
        'zoom_to_data_extent': True,
        'default_lon': clon,
        'default_lat': clat,
        'default_zoom': zl,
#        'default_lat': 44,
#        'default_lon': -72,
    }


class FileObjectAdmin(admin.ModelAdmin):
    list_display = ('file','modified_date',)


admin.site.register(Publication, PublicationAdmin)
admin.site.register(Person)
admin.site.register(PubType)
admin.site.register(Feature, FeatureAdmin)
admin.site.register(Topic)
admin.site.register(Keyword)
admin.site.register(FileObject, FileObjectAdmin)
#admin.site.register(Feature, admin.GeoModelAdmin)
