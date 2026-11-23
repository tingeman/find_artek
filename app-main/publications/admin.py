from django.contrib import admin, messages

from .models import Publication, Feature
from .report_delete import has_features, report_label, split_by_features


class PublicationAdmin(admin.ModelAdmin):
    """A report that still has features is never deleted (plan "features" T13,
    publications.report_delete).

    - ``has_delete_permission`` is False for such a report: its admin page shows no delete
      link and its delete page is refused. The "Delete selected" action asks the same for
      every selected report, so a selection that contains one is refused as a whole
      ("permission to delete ... publication" missing) and nothing is deleted.
    - ``delete_queryset`` (what the action calls after the confirmation) skips such reports
      anyway, in case one got features between the confirmation and the delete, and names
      them in an error message.
    """

    def has_delete_permission(self, request, obj=None):
        if obj is not None and has_features(obj):
            return False
        return super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        deletable, blocked = split_by_features(queryset)
        if blocked:
            self.message_user(
                request,
                'Not deleted, these reports still have features (delete them first): '
                + ', '.join(report_label(p) for p in blocked) + '.',
                level=messages.ERROR)
        if deletable:
            Publication.objects.filter(pk__in=[p.pk for p in deletable]).delete()


admin.site.register(Publication, PublicationAdmin)
# admin.site.register(Author, admin.ModelAdmin)
# admin.site.register(Publisher, admin.ModelAdmin)
admin.site.register(Feature, admin.ModelAdmin)
