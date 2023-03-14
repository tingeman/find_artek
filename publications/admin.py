from django.contrib import admin
from .models import Publication, Feature

# Register your models here.
admin.site.register(Publication, admin.ModelAdmin)
# admin.site.register(Author, admin.ModelAdmin)
# admin.site.register(Publisher, admin.ModelAdmin)
admin.site.register(Feature, admin.ModelAdmin)
