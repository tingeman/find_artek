"""Visibility of person data (plan "registration" T13, decided 2026-11-18).

- Anonymous users: no ``id_number``; no e-mail of a student (position 'student', or an
  id_number that is a study number 's' + 6 digits). Staff e-mails stay visible.
- Logged-in users see both.
- The contact fields (phone, cell_phone, address_1, address_2, zip_code, town, state,
  country, homepage) are shown nowhere (person page, API) and can't be stored through a
  form, even when they are set in the database.

Checked on the person page, the person API (list and detail) and the person autocomplete.
The rules themselves are in publications.person_privacy and Person.is_student().
"""
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.forms import ModelForm
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from publications import forms as publication_forms
from publications import person_privacy
from publications.forms import AddPersonForm
from publications.models import Person
from publications.roles import DTU_USER
from publications.test_report_access import _path
from publications.test_upload_appendix_access import _app_path

CONTACT_VALUES = {
    'phone': 'PHONE-4711-MARK',
    'cell_phone': 'CELL-4712-MARK',
    'address_1': 'ADDR1-MARK street',
    'address_2': 'ADDR2-MARK floor',
    'zip_code': 'ZIP-4713-MARK',
    'town': 'TOWN-MARK-ville',
    'state': 'STATE-MARK-land',
    'country': 'COUNTRY-MARK-ia',
    'homepage': 'https://homepage-mark.example.org/',
}


def _api_path(name, **kwargs):
    return _app_path(reverse(f'api:{name}', kwargs=kwargs))


class IsStudentTests(SimpleTestCase):

    def test_position_student_any_case(self):
        for position in ('student', 'Student', ' STUDENT '):
            with self.subTest(position=position):
                self.assertTrue(Person(position=position).is_student())

    def test_study_number_any_case(self):
        for id_number in ('s123456', 'S123456'):
            with self.subTest(id_number=id_number):
                self.assertTrue(Person(id_number=id_number).is_student())

    def test_staff_and_other_ids_are_not_students(self):
        for kwargs in ({'position': 'Associate professor', 'id_number': '12345'},
                       {'id_number': 's12345'}, {'id_number': 's1234567'},
                       {'id_number': 'x123456'}, {'position': 'Student assistant'}, {}):
            with self.subTest(**kwargs):
                self.assertFalse(Person(**kwargs).is_student())


class PersonPrivacyTestBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Student by position only (id_number is not a study number)
        cls.student_pos = Person.objects.create(
            first='Posi', last='Tionstudent', position='Student', id_number='EMP-777-POS',
            email='posi.student@student.example.org', **CONTACT_VALUES)
        # Student by study number only (no position), upper-case S
        cls.student_num = Person.objects.create(
            first='Numb', last='Erstudent', id_number='S654321',
            email='numb.student@student.example.org', **CONTACT_VALUES)
        cls.staff = Person.objects.create(
            first='Staf', last='Member', position='Associate professor', id_number='E-98765-STAFF',
            email='staff.member@example.org', **CONTACT_VALUES)
        cls.user = User.objects.create_user('s990001', password='x')

    def assertNoContactValues(self, text):
        for field, value in CONTACT_VALUES.items():
            self.assertNotIn(value, text, f'{field} is output')
        self.assertNotIn('homepage-mark', text)


class PersonPagePrivacyTests(PersonPrivacyTestBase):

    def page(self, person):
        response = self.client.get(_path('person', pk=person.pk))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_anonymous_sees_no_id_number(self):
        for person in (self.student_pos, self.student_num, self.staff):
            with self.subTest(person=person.last):
                self.assertNotIn(person.id_number, self.page(person))

    def test_anonymous_sees_no_student_email(self):
        for person in (self.student_pos, self.student_num):
            with self.subTest(person=person.last):
                self.assertNotIn(person.email, self.page(person))

    def test_anonymous_sees_staff_email(self):
        self.assertIn(self.staff.email, self.page(self.staff))

    def test_logged_in_sees_id_number_and_email(self):
        self.client.force_login(self.user)
        for person in (self.student_pos, self.student_num, self.staff):
            with self.subTest(person=person.last):
                html = self.page(person)
                self.assertIn(person.id_number, html)
                self.assertIn(person.email, html)

    def test_contact_fields_never_shown(self):
        for login in (False, True):
            if login:
                self.client.force_login(self.user)
            for person in (self.student_pos, self.student_num, self.staff):
                with self.subTest(person=person.last, logged_in=login):
                    self.assertNoContactValues(self.page(person))


class PersonApiPrivacyTests(PersonPrivacyTestBase):

    def list_data(self):
        response = self.client.get(_api_path('person-list'))
        self.assertEqual(response.status_code, 200)
        return {item['id']: item for item in response.json()}, response.content.decode()

    def detail_data(self, person):
        response = self.client.get(_api_path('person-detail', pk=person.pk))
        self.assertEqual(response.status_code, 200)
        return response.json(), response.content.decode()

    def items(self):
        """(label, data, raw JSON) for every person, from the list and the detail view."""
        listed, raw_list = self.list_data()
        for person in (self.student_pos, self.student_num, self.staff):
            yield person, 'list', listed[person.pk], raw_list
            data, raw = self.detail_data(person)
            yield person, 'detail', data, raw

    def test_anonymous_gets_no_id_number(self):
        for person, view, data, raw in self.items():
            with self.subTest(person=person.last, view=view):
                self.assertIsNone(data['id_number'])
                self.assertNotIn(person.id_number, raw)

    def test_anonymous_gets_no_student_email_but_staff_email(self):
        for person, view, data, raw in self.items():
            with self.subTest(person=person.last, view=view):
                if person == self.staff:
                    self.assertEqual(data['email'], self.staff.email)
                else:
                    self.assertIsNone(data['email'])
                    self.assertNotIn(person.email, raw)

    def test_logged_in_gets_id_number_and_email(self):
        self.client.force_login(self.user)
        for person, view, data, raw in self.items():
            with self.subTest(person=person.last, view=view):
                self.assertEqual(data['id_number'], person.id_number)
                self.assertEqual(data['email'], person.email)

    def test_contact_fields_never_in_api(self):
        for login in (False, True):
            if login:
                self.client.force_login(self.user)
            for person, view, data, raw in self.items():
                with self.subTest(person=person.last, view=view, logged_in=login):
                    for field in person_privacy.CONTACT_FIELDS:
                        self.assertNotIn(field, data)
                    self.assertNoContactValues(raw)


class PersonAutocompletePrivacyTests(PersonPrivacyTestBase):
    """Looking a person up by study number would reveal the id_number to anonymous users."""

    def results(self, term):
        response = self.client.get(_path('person-autocomplete'), {'term': term})
        self.assertEqual(response.status_code, 200)
        return [item['id'] for item in response.json()['results']]

    def test_anonymous_cannot_look_up_by_study_number(self):
        self.assertNotIn(self.student_num.pk, self.results('s654321'))

    def test_logged_in_can_look_up_by_study_number(self):
        self.client.force_login(self.user)
        self.assertIn(self.student_num.pk, self.results('s654321'))

    def test_anonymous_name_search_still_works(self):
        self.assertIn(self.staff.pk, self.results('Member'))


class ContactFieldsNotEditableTests(TestCase):

    def test_add_person_form_ignores_contact_fields(self):
        data = {'name': 'Form Person', 'email': 'form.person@example.org', **CONTACT_VALUES}
        form = AddPersonForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        person = form.save()
        person.refresh_from_db()
        self.assertEqual(person.email, 'form.person@example.org')
        for field in person_privacy.CONTACT_FIELDS:
            self.assertEqual(getattr(person, field), '', field)

    def test_add_person_ajax_post_does_not_store_contact_fields(self):
        user = User.objects.create_user('s990002', password='x')
        user.groups.add(Group.objects.get(name=DTU_USER))
        self.client.force_login(user)
        response = self.client.post(_path('add_person_ajax'),
                                    {'name': 'Ajax Person', **CONTACT_VALUES},
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200, response.content)
        person = Person.objects.get(pk=response.json()['person_id'])
        for field in person_privacy.CONTACT_FIELDS:
            self.assertEqual(getattr(person, field), '', field)

    def test_no_person_model_form_has_contact_fields(self):
        person_forms = [
            obj for obj in vars(publication_forms).values()
            if isinstance(obj, type) and issubclass(obj, ModelForm)
            and getattr(getattr(obj, '_meta', None), 'model', None) is Person
        ]
        self.assertIn(AddPersonForm, person_forms)
        for form_class in person_forms:
            with self.subTest(form=form_class.__name__):
                self.assertFalse(set(form_class.base_fields) & set(person_privacy.CONTACT_FIELDS))

    def test_admin_does_not_offer_contact_fields(self):
        """Person is not registered in the admin today; if it is, its form must exclude
        the contact fields."""
        model_admin = admin.site._registry.get(Person)
        if model_admin is None:
            return
        superuser = User.objects.create_superuser('admin', password='x')
        request = RequestFactory().get('/')
        request.user = superuser
        form_class = model_admin.get_form(request)
        self.assertFalse(set(form_class.base_fields) & set(person_privacy.CONTACT_FIELDS))
