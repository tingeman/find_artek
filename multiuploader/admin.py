from models import MultiuploaderImage
from django.contrib import admin


class MultiuploaderImageAdmin(admin.ModelAdmin):
    search_fields = ["filename", "batch_tag", "key_data"]
    list_display = ["filename", "image", "batch_tag", "key_data"]
    list_filter = ["filename", "image", "batch_tag", "key_data"]

admin.site.register(MultiuploaderImage, MultiuploaderImageAdmin)
