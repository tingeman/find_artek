"""The checked media view (roadmap FA-R30, FA-R75; plan PLAN_confidential T5).

Every file under MEDIA_URL goes through publications.views_media.serve_media. The tests use a
temporary MEDIA_ROOT with tiny files they write themselves (never real media) and request the
files through the test client at the URL the app serves them under (MEDIA_URL without
FORCE_SCRIPT_NAME, so the tests work with the production settings of the release gate and with
the development settings).

Expected answers are written out by hand from the rule (publications.visibility):
- report PDF, appendix, thumbnail: the report's visibility;
- feature file and image: the feature's visibility (no report, or at least one visible report);
- temp upload: its uploader, artek_editor, superusers;
- anything else (unowned, ``.old``): artek_editor and superusers only (default deny);
- invalid paths and missing files: 404 for everyone.
"""
import datetime
import os
import re
import shutil
import tempfile
from io import StringIO
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, Group, User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve

from publications.media_access import (
    EDITORS_ONLY, PUBLIC, RESTRICTED, MediaIndex, can_access_media, resolve_media_path,
    thumbnail_key,
)
from publications.models import (
    Appendenciesship, Authorship, Feature, FileObject, ImageObject, ImageObjectship, Person,
    Publication, PubType,
)
from publications.roles import ARTEK_EDITOR, DTU_USER

ACCEL_PREFIX = '/find/_protected_media/'


def media_path(relpath):
    """The path the test client requests for ``relpath`` (relative to MEDIA_ROOT): MEDIA_URL
    without FORCE_SCRIPT_NAME (the test client sends PATH_INFO, without the script prefix)."""
    media_url = settings.MEDIA_URL
    script_name = (settings.FORCE_SCRIPT_NAME or '').rstrip('/')
    if script_name and media_url.startswith(script_name + '/'):
        media_url = media_url[len(script_name):]
    return media_url + quote(relpath)


def raw_media_path(raw):
    """Like ``media_path`` but ``raw`` is put into the URL as given (already quoted)."""
    return media_path('') + raw


# Reports (number -> verified, confidential).
P, U, C = '99-01', '99-02', '99-03'
REPORTS = {P: (True, False), U: (False, False), C: (True, True)}

USERS = ('anonymous', 'dtu', 'author', 'artek_editor', 'superuser')

# Users who may see each report (T2 matrix; 'author' is listed on every report).
REPORT_ALLOWED = {
    P: set(USERS),
    U: {'dtu', 'author', 'artek_editor', 'superuser'},
    C: {'author', 'artek_editor', 'superuser'},
}
EDITORS = {'artek_editor', 'superuser'}


def pdf_name(number):
    # The PDF stem differs from the number, so thumbnails by number and by stem differ.
    return f'reports/1999/{number}_v.pdf'


def appendix_name(number):
    return f'reports/1999/{number}/appendix.txt'


def thumb_by_number(number):
    return f'reports/1999/thumbs/{number}_thumb.jpg'


def thumb_by_stem(number):
    return f'reports/1999/thumbs/{number}_v_thumb.jpg'


SPACE_APPENDIX = f'reports/1999/{P}/my file.pdf'

# Features: name -> reports.
FEATURES = {'f-public': {P}, 'f-hidden': {C}, 'f-none': set()}
FEATURE_ALLOWED = {
    'f-public': set(USERS),
    'f-hidden': REPORT_ALLOWED[C],
    'f-none': set(USERS),   # features without a report stay public
}


def feature_file(name):
    return f'features/{name}/data.txt'


def feature_image(name):
    return f'features/{name}/photo.jpg'


TEMP_UPLOAD = 'temp/20261119-120000/upload.pdf'          # uploaded by 'author'
TEMP_NO_UPLOADER = 'temp/20261119-120001/nobody.pdf'      # FileObject without created_by
TEMP_STRAY = 'temp/20261118-090000/stray.pdf'             # no FileObject
ORPHAN = 'reports/1999/orphan.pdf'                        # no FileObject
OLD_PDF = f'reports/1999/{P}_v.pdf.old'                   # replaced PDF, no FileObject


def all_fixture_files():
    files = [SPACE_APPENDIX, TEMP_UPLOAD, TEMP_NO_UPLOADER, TEMP_STRAY, ORPHAN, OLD_PDF]
    for number in REPORTS:
        files += [pdf_name(number), appendix_name(number), thumb_by_number(number),
                  thumb_by_stem(number)]
    for name in FEATURES:
        files += [feature_file(name), feature_image(name)]
    return files


def file_bytes(relpath):
    return f'content of {relpath}\n'.encode()


class MediaTreeMixin:
    """A temporary MEDIA_ROOT (``self.media_root``) with every fixture file, and a file outside
    it (``self.outside_file``). Removed after each test."""

    def setUp(self):
        super().setUp()
        base = tempfile.mkdtemp(prefix='find_artek_media_test_')
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        self.media_root = os.path.join(base, 'media')
        os.makedirs(self.media_root)
        self.outside_file = os.path.join(base, 'secret.txt')
        with open(self.outside_file, 'wb') as f:
            f.write(b'outside MEDIA_ROOT\n')
        for relpath in all_fixture_files():
            self.write_media(relpath)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

    def write_media(self, relpath, content=None):
        full = os.path.join(self.media_root, *relpath.split('/'))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(file_bytes(relpath) if content is None else content)
        return full


class MediaFixtureMixin(MediaTreeMixin):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')
        groups = {name: Group.objects.get(name=name) for name in (DTU_USER, ARTEK_EDITOR)}

        def user(username, *group_names, superuser=False):
            if superuser:
                u = User.objects.create_superuser(username, password='x')
            else:
                u = User.objects.create_user(username, password='x')
            u.groups.add(groups[DTU_USER], *(groups[g] for g in group_names))
            return u

        cls.users = {
            'dtu': user('s990999'),
            'author': user('s990001'),
            'artek_editor': user('edit', ARTEK_EDITOR),
            'superuser': user('root', superuser=True),
        }
        author = Person.objects.create(first='Stu', last='Dent', id_number='S990001')

        cls.pubs = {}
        for number, (verified, confidential) in REPORTS.items():
            pub = Publication.objects.create(
                type=pubtype, number=number, title=f'Report {number}', year=1999,
                verified=verified, confidential=confidential,
                file=FileObject.objects.create(file=pdf_name(number)))
            Appendenciesship.objects.create(
                publication=pub, fileobject=FileObject.objects.create(file=appendix_name(number)))
            Authorship.objects.create(publication=pub, person=author, author_id=0)
            cls.pubs[number] = pub
        Appendenciesship.objects.create(
            publication=cls.pubs[P], fileobject=FileObject.objects.create(file=SPACE_APPENDIX))

        for name, numbers in FEATURES.items():
            feature = Feature.objects.create(name=name, date=datetime.date(1999, 7, 1))
            feature.publications.set([cls.pubs[n] for n in numbers])
            feature.files.add(FileObject.objects.create(file=feature_file(name)))
            ImageObjectship.objects.create(
                feature=feature,
                imageobject=ImageObject.objects.create(image=feature_image(name), caption=''))

        temp = FileObject.objects.create(file=TEMP_UPLOAD)
        FileObject.objects.filter(pk=temp.pk).update(created_by=cls.users['author'])
        FileObject.objects.create(file=TEMP_NO_UPLOADER)

    def login(self, key):
        self.client.logout()
        if key != 'anonymous':
            self.client.force_login(self.users[key])

    def fetch(self, path, method='get'):
        """Request ``path``; read and close a streamed body (``response.body``)."""
        response = getattr(self.client, method)(path)
        if response.streaming:
            # Consuming the content closes the file (the test client wraps the iterator; an
            # extra response.close() would close the DB connection inside the test).
            response.body = b''.join(response.streaming_content)
        else:
            response.body = response.content
        return response

    def assertAccess(self, relpath, allowed_users):
        for key in USERS:
            with self.subTest(file=relpath, user=key):
                self.login(key)
                response = self.fetch(media_path(relpath))
                self.assertEqual(response.status_code, 200 if key in allowed_users else 404)


class MediaAccessMatrixTests(MediaFixtureMixin, TestCase):

    def test_report_pdf(self):
        for number, allowed in REPORT_ALLOWED.items():
            self.assertAccess(pdf_name(number), allowed)

    def test_appendix(self):
        for number, allowed in REPORT_ALLOWED.items():
            self.assertAccess(appendix_name(number), allowed)

    def test_thumbnail_by_report_number(self):
        for number, allowed in REPORT_ALLOWED.items():
            self.assertAccess(thumb_by_number(number), allowed)

    def test_thumbnail_by_pdf_stem(self):
        for number, allowed in REPORT_ALLOWED.items():
            self.assertAccess(thumb_by_stem(number), allowed)

    def test_thumbnail_of_another_year_is_unowned(self):
        # The number matches, but generate_thumbnails puts it under the report's year.
        relpath = f'reports/2000/thumbs/{P}_thumb.jpg'
        self.write_media(relpath)
        self.assertAccess(relpath, EDITORS)

    def test_feature_file(self):
        for name, allowed in FEATURE_ALLOWED.items():
            self.assertAccess(feature_file(name), allowed)

    def test_feature_image(self):
        for name, allowed in FEATURE_ALLOWED.items():
            self.assertAccess(feature_image(name), allowed)

    def test_temp_upload(self):
        self.assertAccess(TEMP_UPLOAD, {'author', 'artek_editor', 'superuser'})

    def test_temp_upload_without_uploader(self):
        self.assertAccess(TEMP_NO_UPLOADER, EDITORS)

    def test_unowned_files(self):
        for relpath in (ORPHAN, OLD_PDF, TEMP_STRAY):
            self.assertAccess(relpath, EDITORS)

    def test_file_shared_by_hidden_and_public_report_is_public(self):
        # One FileObject used as appendix of the confidential and the public report:
        # allowed if any owner allows.
        shared = FileObject.objects.get(file=appendix_name(C))
        Appendenciesship.objects.create(publication=self.pubs[P], fileobject=shared)
        self.assertAccess(appendix_name(C), set(USERS))

    def test_missing_file_is_404_also_for_editors(self):
        for key in ('anonymous', 'superuser'):
            with self.subTest(user=key):
                self.login(key)
                self.assertEqual(self.fetch(media_path('reports/1999/missing.pdf')).status_code, 404)

    def test_owned_but_missing_file_is_404(self):
        os.remove(os.path.join(self.media_root, *pdf_name(P).split('/')))
        self.login('anonymous')
        self.assertEqual(self.fetch(media_path(pdf_name(P))).status_code, 404)

    def test_directory_is_404(self):
        self.login('superuser')
        self.assertEqual(self.fetch(media_path('reports/1999')).status_code, 404)

    def test_denied_anonymous_is_not_redirected_to_login(self):
        self.login('anonymous')
        response = self.fetch(media_path(pdf_name(C)))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('Location', response)

    def test_post_is_405(self):
        self.login('superuser')
        self.assertEqual(self.fetch(media_path(pdf_name(P)), method='post').status_code, 405)

    def test_head_is_allowed(self):
        self.login('anonymous')
        self.assertEqual(self.fetch(media_path(pdf_name(P)), method='head').status_code, 200)


class MediaPathSafetyTests(MediaFixtureMixin, TestCase):
    """Paths that leave MEDIA_ROOT answer 404, also for a superuser (who may see every file
    inside it)."""

    def assertNotFound(self, path):
        with self.subTest(path=path):
            self.login('superuser')
            response = self.fetch(path)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(b'outside MEDIA_ROOT', response.body)

    def test_traversal(self):
        outside_abs = self.outside_file.replace(os.sep, '/')
        for raw in ('../secret.txt',
                    '%2e%2e/secret.txt',
                    '%2E%2E%2Fsecret.txt',
                    '..%2fsecret.txt',
                    'reports/../../secret.txt',
                    'reports/1999/%2e%2e/%2e%2e/%2e%2e/secret.txt',
                    '..%5Csecret.txt',
                    'reports%5C..%5C..%5Csecret.txt',
                    '/' + outside_abs.lstrip('/'),
                    quote(outside_abs, safe=''),
                    '//etc/passwd',
                    '%2Fetc%2Fpasswd'):
            self.assertNotFound(raw_media_path(raw))

    def test_sanity_inside_file_is_served_to_superuser(self):
        self.login('superuser')
        self.assertEqual(self.fetch(media_path(ORPHAN)).status_code, 200)

    def test_symlink_out_of_media_root(self):
        link = os.path.join(self.media_root, 'reports', '1999', 'link.pdf')
        try:
            os.symlink(self.outside_file, link)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest(f'symlinks cannot be created here: {exc}')
        # Even when a public report owns the name.
        Appendenciesship.objects.create(
            publication=self.pubs[P],
            fileobject=FileObject.objects.create(file='reports/1999/link.pdf'))
        self.assertNotFound(media_path('reports/1999/link.pdf'))
        self.login('anonymous')
        self.assertEqual(self.fetch(media_path('reports/1999/link.pdf')).status_code, 404)


class ResolveMediaPathTests(MediaTreeMixin, SimpleTestCase):

    def test_rejected(self):
        for path in ('', '.', './', '..', '../x', 'a/../b', 'a/..', '/abs/path', 'a\\b',
                     '..\\x', 'a\x00b', None):
            with self.subTest(path=path):
                self.assertIsNone(resolve_media_path(path))

    def test_normalised(self):
        self.assertEqual(resolve_media_path('reports//1999/./x.pdf'), 'reports/1999/x.pdf')
        self.assertEqual(resolve_media_path('reports/1999/x.pdf'), 'reports/1999/x.pdf')

    def test_thumbnail_key(self):
        self.assertEqual(thumbnail_key('reports/1999/thumbs/99-01_thumb.jpg'),
                         ('reports/1999', '99-01'))
        self.assertIsNone(thumbnail_key('reports/1999/99-01_thumb.jpg'))
        self.assertIsNone(thumbnail_key('reports/1999/thumbs/_thumb.jpg'))
        self.assertIsNone(thumbnail_key('reports/1999/thumbs/99-01.jpg'))


class MediaResponseTests(MediaFixtureMixin, TestCase):

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX=ACCEL_PREFIX)
    def test_accel_mode_has_header_and_no_body(self):
        # Production: gunicorn never streams a file; nginx does (X-Accel-Redirect).
        self.login('anonymous')
        for method in ('get', 'head'):
            with self.subTest(method=method):
                response = self.fetch(media_path(SPACE_APPENDIX), method=method)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.streaming)
                self.assertEqual(response.body, b'')
                self.assertEqual(response['X-Accel-Redirect'],
                                 '/find/_protected_media/reports/1999/99-01/my%20file.pdf')
                self.assertEqual(response['Content-Type'], 'application/pdf')
                self.assertNotIn('Content-Disposition', response)

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX=ACCEL_PREFIX)
    def test_accel_mode_content_types(self):
        unknown = 'reports/1999/unknown.zz-no-such-type'
        self.write_media(unknown)
        self.login('superuser')
        for relpath, content_type in ((pdf_name(P), 'application/pdf'),
                                      (thumb_by_number(P), 'image/jpeg'),
                                      (appendix_name(P), 'text/plain'),
                                      (unknown, 'application/octet-stream')):
            with self.subTest(file=relpath):
                response = self.fetch(media_path(relpath))
                self.assertEqual(response['Content-Type'], content_type)
                self.assertEqual(response['X-Accel-Redirect'], ACCEL_PREFIX + relpath)
                self.assertEqual(response.body, b'')

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX=ACCEL_PREFIX)
    def test_accel_mode_denied_has_no_header(self):
        self.login('anonymous')
        response = self.fetch(media_path(pdf_name(C)))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('X-Accel-Redirect', response)

    @override_settings(MEDIA_ACCEL_REDIRECT_PREFIX='')
    def test_stream_mode_returns_the_file(self):
        self.login('anonymous')
        for relpath in (pdf_name(P), SPACE_APPENDIX):
            with self.subTest(file=relpath):
                response = self.fetch(media_path(relpath))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.body, file_bytes(relpath))
                self.assertNotIn('X-Accel-Redirect', response)
                self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_cache_control(self):
        cases = (
            ('anonymous', pdf_name(P), 'public, max-age=3600'),
            ('author', pdf_name(P), 'public, max-age=3600'),
            ('dtu', thumb_by_number(P), 'public, max-age=3600'),
            ('dtu', pdf_name(U), 'private, no-store'),
            ('author', pdf_name(C), 'private, no-store'),
            ('artek_editor', appendix_name(C), 'private, no-store'),
            ('author', TEMP_UPLOAD, 'private, no-store'),
            ('artek_editor', ORPHAN, 'private, no-store'),
            ('author', feature_image('f-hidden'), 'private, no-store'),
            ('anonymous', feature_file('f-none'), 'public, max-age=3600'),
        )
        for key, relpath, expected in cases:
            with self.subTest(user=key, file=relpath):
                self.login(key)
                response = self.fetch(media_path(relpath))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Cache-Control'], expected)


class CheckMediaAccessCommandTests(MediaFixtureMixin, TestCase):

    EXPECTED = {  # class: (public, restricted, editors_only)
        'report_pdf': (1, 2, 0),
        'appendix': (2, 2, 0),
        'thumbnail': (2, 4, 0),
        'feature_file': (2, 1, 0),
        'feature_image': (2, 1, 0),
        'temp': (0, 1, 1),
        'unowned': (0, 0, 3),
        'total': (9, 11, 4),
    }

    def run_command(self, *args):
        out = StringIO()
        call_command('check_media_access', *args, stdout=out)
        return out.getvalue()

    def parse_counts(self, output):
        counts = {}
        for line in output.splitlines():
            m = re.match(r'^(\w+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$', line)
            if m:
                counts[m.group(1)] = tuple(int(g) for g in m.groups()[1:4])
                self.assertEqual(int(m.group(5)), sum(counts[m.group(1)]))
        return counts

    def test_counts(self):
        output = self.run_command()
        self.assertEqual(self.parse_counts(output), self.EXPECTED)
        self.assertNotIn('Unowned files', output)
        self.assertNotIn(ORPHAN, output)
        self.assertNotIn('content of', output)   # never file contents

    def test_list_unowned(self):
        output = self.run_command('--list-unowned')
        self.assertEqual(self.parse_counts(output), self.EXPECTED)
        listed = output.split('Unowned files (3):', 1)[1].split()
        self.assertEqual(sorted(listed), sorted([ORPHAN, OLD_PDF, TEMP_STRAY]))

    def test_index_agrees_with_the_view(self):
        # The command's level and the view's answer come from the same rule.
        index = MediaIndex()
        anonymous = AnonymousUser()
        for relpath in all_fixture_files():
            with self.subTest(file=relpath):
                _, level = index.classify(relpath)
                allowed, public = can_access_media(anonymous, relpath)
                self.assertEqual(level == PUBLIC, allowed)
                self.assertEqual(level == PUBLIC, public)
                if level == EDITORS_ONLY:
                    for key in ('dtu', 'author'):
                        self.assertFalse(can_access_media(self.users[key], relpath)[0])
                elif level == RESTRICTED:
                    self.assertTrue(any(can_access_media(self.users[key], relpath)[0]
                                        for key in ('dtu', 'author')))


class MediaRouteTests(TestCase):
    """The route is MEDIA_URL without FORCE_SCRIPT_NAME. (TestCase: importing the URLconf
    queries the database, api.views.)"""

    def test_route_from_settings(self):
        from find_artek.urls import _media_route
        with override_settings(FORCE_SCRIPT_NAME='/find', MEDIA_URL='/find/media/'):
            self.assertEqual(_media_route(), 'media/<path:path>')       # production
        with override_settings(FORCE_SCRIPT_NAME='', MEDIA_URL='/find/media/'):
            self.assertEqual(_media_route(), 'find/media/<path:path>')  # development settings

    def test_media_path_resolves_to_the_view(self):
        match = resolve(media_path('') + 'reports/1999/a b.pdf')   # resolve() gets PATH_INFO
        self.assertEqual(match.url_name, 'media')
        self.assertEqual(match.kwargs, {'path': 'reports/1999/a b.pdf'})
