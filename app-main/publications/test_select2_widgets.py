"""django-select2 widgets of the report form (plan "django-5", T3: django-select2 8.4.8).

The author/supervisor fields use the heavy (AJAX) widget fed by our own person autocomplete
view; topics and keywords use the light tag widget. Checked: the rendered attributes the
select2 JavaScript reads, the form media (the JS/CSS files collectstatic must ship) and the
JSON the autocomplete returns in the shape the widget expects.
"""
from django.test import TestCase
from django.urls import reverse

from publications.forms.publication import AddEditReportForm
from publications.models import Keyword, Person, Topic
from publications.test_factories import make_user, page_path


class ReportFormSelect2Tests(TestCase):

    @classmethod
    def setUpTestData(cls):
        Topic.objects.create(topic='Select2 topic')
        Keyword.objects.create(keyword='select2-keyword')

    def setUp(self):
        self.form = AddEditReportForm()

    def test_person_fields_are_heavy_widgets_on_the_person_autocomplete(self):
        url = reverse('publications:person-autocomplete')
        for name in ('authors', 'supervisors'):
            with self.subTest(field=name):
                html = str(self.form[name])
                self.assertIn('django-select2-heavy', html)
                self.assertIn(f'data-ajax--url="{url}"', html)
                self.assertIn('data-field_id=', html)
                self.assertIn('data-tags="true"', html)

    def test_topics_and_keywords_are_light_tag_widgets_with_their_choices(self):
        for name, option, tags in (('publication_topics', 'Select2 topic', 'false'),
                                   ('publication_keywords', 'select2-keyword', 'true')):
            with self.subTest(field=name):
                html = str(self.form[name])
                self.assertIn('django-select2', html)
                self.assertNotIn('django-select2-heavy', html)
                self.assertIn(option, html)
                self.assertIn(f'data-tags="{tags}"', html)

    def test_media_includes_django_select2_assets(self):
        media = str(self.form.media)
        self.assertIn('django_select2/django_select2.js', media)
        self.assertIn('select2', media)
        self.assertIn('.css', media)


class PersonAutocompleteShapeTests(TestCase):
    """The response shape processResults in django_select2.js reads (``results`` of
    ``{id, text}``)."""

    def test_results_are_id_and_text(self):
        person = Person.objects.create(first='Selecta', last='Twoington')
        # The autocomplete is for logged-in users only (FA-R82).
        self.client.force_login(make_user('select2user'))
        response = self.client.get(page_path('person-autocomplete'), {'term': 'Twoington'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'results': [{'id': person.pk, 'text': str(person)}]})
