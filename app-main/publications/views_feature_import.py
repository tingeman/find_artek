"""Excel import of features with a preview (plan "features" T10, roadmap FA-R63).

Two entry points, one preview and one import step (publications.feature_import does the
work):

- ``ReportFeatureImportView`` (``report/<pk>/features/import/``): from a report page; needs
  ``add_feature`` on that report (permissions.ADD_FEATURE). The features go into that report;
  the sheet's Report column may be empty, or must name this report.
- ``FeatureImportView`` (``features/import/``): from the Administration page; needs the
  Django permission ``publications.add_feature``. Every row names its report, and the user
  needs ``add_feature`` on each of them (a row for another report is an error).
- ``FeatureImportPreviewView`` (``features/import/<import_id>/``, GET): map, table and
  problems of the import kept in the session; checks again that the reports exist and may be
  edited. Nothing is saved.
- ``FeatureImportConfirmView`` (``features/import/<import_id>/confirm/``, POST only):
  ``action=import`` saves every feature in one transaction (after the same checks);
  ``action=cancel`` drops the import. Both remove it from the session.

An import id that is unknown, expired (feature_import.SESSION_MAX_AGE) or belongs to another
user sends the user to the import page with a message.
"""
import logging

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse

from publications import feature_import
from publications.forms import FeatureImportFileForm
from publications.models import Publication
from publications.permissions import (
    ADD_FEATURE, PublicationPermissionMixin, access_denied_response,
)
from publications.views import BaseFormView, BaseView

logger = logging.getLogger(__name__)

IMPORT_DENIED_MESSAGE = 'You do not have permission to add features.'
EXPIRED_MESSAGE = ('This import is no longer available (it expired, was imported or '
                   'cancelled). Please upload the file again.')


def may_import_features(user):
    """The guard of the administration import, preview and import steps."""
    return user.is_authenticated and user.has_perm('publications.add_feature')


class FeatureImportAccessMixin(AccessMixin):
    """Logged in with ``publications.add_feature``: anonymous users are sent to the login,
    others get 403. The reports themselves are checked per row and again before saving."""

    def dispatch(self, request, *args, **kwargs):
        if request.method.lower() not in self.http_method_names:
            return self.http_method_not_allowed(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not may_import_features(request.user):
            return access_denied_response(request, ADD_FEATURE, error=IMPORT_DENIED_MESSAGE)
        return super().dispatch(request, *args, **kwargs)


class _UploadMixin:
    """Step 1: read and check the file, keep the result in the session, show the preview."""
    template_name = 'publications/feature_import_upload.html'
    form_class = FeatureImportFileForm
    import_report = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'publication': self.import_report,
            'template_path': feature_import.TEMPLATE_STATIC_PATH,
            'max_vertices': feature_import.MAX_VERTICES,
            'cancel_url': self.cancel_url(),
        })
        return context

    def form_valid(self, form):
        uploaded_file = form.cleaned_data['file']
        try:
            workbook = feature_import.load_workbook(uploaded_file)
            parsed = feature_import.parse_workbook(workbook, self.request.user,
                                                   report=self.import_report)
        except (feature_import.ImportFileError, feature_import.ImportTooLarge) as error:
            form.add_error('file', str(error))
            return self.form_invalid(form)
        except Exception:
            logger.exception('Feature import: the uploaded file could not be read')
            form.add_error('file', 'The file could not be read as an Excel (.xlsx) file.')
            return self.form_invalid(form)
        data = feature_import.session_data(parsed, self.request.user, report=self.import_report,
                                           file_name=uploaded_file.name)
        import_id = feature_import.store(self.request.session, data)
        return redirect('publications:import_features_preview', import_id=import_id)


class ReportFeatureImportView(PublicationPermissionMixin, _UploadMixin, BaseFormView):
    """Import features into the report of the URL (add_feature on it)."""
    permission = ADD_FEATURE

    def get_permission_object(self):
        publication = super().get_permission_object()
        self.import_report = publication
        return publication

    def cancel_url(self):
        return reverse('publications:report', kwargs={'pk': self.import_report.pk})


class FeatureImportView(FeatureImportAccessMixin, _UploadMixin, BaseFormView):
    """Import features into the reports named in the sheet (Administration page)."""

    def cancel_url(self):
        return reverse('publications:administration')


def start_url(data):
    """Where an import started: the report's import page, or the administration import."""
    pk = data.get('report_pk') if data else None
    if pk is not None and Publication.objects.filter(pk=pk).exists():
        return reverse('publications:import_report_features', kwargs={'pk': pk})
    return reverse('publications:import_features')


class _StoredImportMixin(FeatureImportAccessMixin):

    def load_import(self):
        self.import_id = self.kwargs['import_id']
        self.data = feature_import.load(self.request.session, self.import_id, self.request.user)
        return self.data

    def expired(self):
        messages.error(self.request, EXPIRED_MESSAGE)
        return redirect('publications:import_features')


class FeatureImportPreviewView(_StoredImportMixin, BaseView):
    """Step 2: show the stored import; nothing is saved."""
    template_name = 'publications/feature_import_preview.html'
    http_method_names = ['get', 'head', 'options']

    def get(self, request, *args, **kwargs):
        data = self.load_import()
        if data is None:
            return self.expired()
        blocking = feature_import.recheck(data, request.user)
        has_errors = feature_import.has_errors(data)
        report = (Publication.objects.filter(pk=data['report_pk']).first()
                  if data.get('report_pk') else None)
        features = data['features']
        problems = feature_import.problems(data)
        context = self.get_context_data(**kwargs)
        context.update({
            'import_id': self.import_id,
            'data': data,
            'publication': report,
            'features': features,
            'problems': problems,
            'blocking': blocking,
            'has_errors': has_errors,
            'importable': bool(features) and not has_errors and not blocking,
            'error_count': sum(1 for item in problems if item[1] == 'error'),
            'warning_count': sum(1 for item in problems if item[1] == 'warning'),
            'preview_geojson': feature_import.preview_geojson(data),
            'start_url': start_url(data),
            'template_path': feature_import.TEMPLATE_STATIC_PATH,
        })
        return render(request, self.template_name, context)


class FeatureImportConfirmView(_StoredImportMixin, BaseView):
    """Step 3 (POST): ``action=import`` saves everything in one transaction, ``cancel`` drops
    the import."""
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        data = self.load_import()
        if data is None:
            return self.expired()
        preview_url = reverse('publications:import_features_preview',
                              kwargs={'import_id': self.import_id})
        if request.POST.get('action') != 'import':
            feature_import.discard(request.session, self.import_id)
            messages.info(request, 'Import cancelled; no features were saved.')
            return HttpResponseRedirect(start_url(data))
        if feature_import.has_errors(data) or not data['features']:
            messages.error(request, 'The file has errors; nothing was imported.')
            return HttpResponseRedirect(preview_url)
        blocking = feature_import.recheck(data, request.user)
        if blocking:
            for text in blocking:
                messages.error(request, text)
            messages.error(request, 'Nothing was imported.')
            return HttpResponseRedirect(preview_url)
        try:
            created = feature_import.save_import(data, request.user)
        except Exception:
            logger.exception('Feature import %s failed', self.import_id)
            messages.error(request, 'The import failed; nothing was saved.')
            return HttpResponseRedirect(preview_url)
        feature_import.discard(request.session, self.import_id)

        numbers = sorted({item['report_number'] for item in data['features']})
        count = len(created)
        messages.success(request, f"{count} feature{'s' if count != 1 else ''} imported into "
                                  f"report{'s' if len(numbers) != 1 else ''} "
                                  f"{', '.join(numbers)}.")
        report_pks = {item['report_pk'] for item in data['features']}
        if len(report_pks) == 1:
            return redirect('publications:report', pk=report_pks.pop())
        return redirect('publications:import_features')
