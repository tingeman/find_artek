"""Person name parsing and matching outside the report form (publications.utils_person).

Name lists are split into persons, names into their parts, and a typed value (name, study
number, initials, ``[id:<pk>]``) is resolved to persons in the database or, with USE_LDAP on,
in the directory. The directory is never contacted: find_ldap_person is mocked and returns
fake entries. All names, study numbers and initials are made up.
"""

from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from publications import utils_person
from publications.models import Person
from publications.test_factories import ldap_entry, make_person, make_user


def student_entry(study_number, sn='Zqdent', given_name='Stu'):
    return ldap_entry(sn, given_name, company='Studerende', name=study_number)


def last_names(names):
    return [utils_person.get_full_name_kwargs(string=n)['last'] for n in names]


class ParseNameListTests(SimpleTestCase):
    """A field with several persons is split into one string per person."""

    def test_single_name_is_one_person(self):
        self.assertEqual(utils_person.parse_name_list('Jane Zqroe'), ['Jane Zqroe'])

    def test_separators_and_ampersand_semicolon(self):
        names = utils_person.parse_name_list('Jane Zqroe and Jon Zqdoe; Ann Zqlee & Bo Zqvik')
        self.assertEqual(names, ['Jane Zqroe', 'Jon Zqdoe', 'Ann Zqlee', 'Bo Zqvik'])

    def test_danish_og_is_a_separator(self):
        self.assertEqual(utils_person.parse_name_list('Jane Zqroe og Jon Zqdoe'),
                         ['Jane Zqroe', 'Jon Zqdoe'])

    def test_first_last_comma_separated(self):
        names = utils_person.parse_name_list('Jane Zqroe, Jon Zqdoe, Ann Zqlee')
        self.assertEqual(last_names(names), ['Zqroe', 'Zqdoe', 'Zqlee'])

    def test_last_comma_first_pairs(self):
        names = utils_person.parse_name_list('Zqroe, Jane, Zqdoe, Jon')
        self.assertEqual(len(names), 2)
        self.assertEqual(last_names(names), ['Zqroe', 'Zqdoe'])

    def test_last_comma_first_with_middle_name(self):
        names = utils_person.parse_name_list('Zqroe, Jane Ann')
        self.assertEqual(len(names), 1)
        self.assertEqual(utils_person.get_full_name_kwargs(string=names[0]),
                         {'first': 'Jane', 'middle': 'Ann', 'last': 'Zqroe'})

    def test_von_part_keeps_pairs(self):
        names = utils_person.parse_name_list('van Zqdam, Jan, Zqroe, Jane')
        self.assertEqual(last_names(names), ['Zqdam', 'Zqroe'])


class NamePartsTests(SimpleTestCase):

    def test_full_name_kwargs_parts(self):
        self.assertEqual(
            utils_person.get_full_name_kwargs(string='van Zqdam, Jr, Jan Erik'),
            {'first': 'Jan', 'middle': 'Erik', 'prelast': 'van', 'last': 'Zqdam',
             'lineage': 'Jr'})

    def test_full_name_kwargs_initials_and_id_number(self):
        self.assertEqual(
            utils_person.get_full_name_kwargs(initials='zqjr', id_number='s990001'),
            {'initials': 'zqjr', 'id_number': 's990001'})

    def test_relaxed_kwargs_are_first_initial_and_lower_last_name(self):
        self.assertEqual(utils_person.get_relaxed_name_kwargs('Jane Ann Zqroe'),
                         {'first_relaxed': 'j', 'last_relaxed': 'zqroe'})

    def test_relaxed_kwargs_of_nothing_is_empty(self):
        self.assertEqual(utils_person.get_relaxed_name_kwargs(), {})

    def test_fullname_of_pybtex_person_and_dict(self):
        pers = utils_person.create_pybtex_person('Zqroe, Jr, Jane')
        self.assertEqual(utils_person.fullname(pers), 'Jane Zqroe, Jr')
        self.assertEqual(utils_person.fullname({'first': 'Jane', 'last': 'Zqroe'}),
                         'Jane Zqroe')


class _UserCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user('zqimporter')


class CreatePersonFromPybtexTests(_UserCase):

    def test_creates_person_with_name_parts_and_relaxed_fields(self):
        pers = utils_person.create_pybtex_person('Jane Ann Zqroe')
        [person] = utils_person.create_person_from_pybtex(pers, self.user)
        person.refresh_from_db()
        self.assertEqual((person.first, person.middle, person.last), ('Jane', 'Ann', 'Zqroe'))
        self.assertEqual((person.first_relaxed, person.last_relaxed), ('j', 'zqroe'))
        self.assertEqual(person.created_by, self.user)

    def test_save_false_does_not_store(self):
        pers = utils_person.create_pybtex_person('Jane Zqroe')
        [person] = utils_person.create_person_from_pybtex(pers, self.user, save=False)
        self.assertIsNone(person.pk)
        self.assertFalse(Person.objects.filter(last='Zqroe').exists())

    def test_needs_person_and_user(self):
        with self.assertRaises(ValueError):
            utils_person.create_person_from_pybtex(None, self.user)
        with self.assertRaises(ValueError):
            utils_person.create_person_from_pybtex(
                utils_person.create_pybtex_person('Jane Zqroe'), None)


class GetPersonTests(TestCase):
    """Database lookup by name parts, study number or initials."""

    @classmethod
    def setUpTestData(cls):
        cls.jane = Person.objects.create(name='Jane Zqroe')   # sets the relaxed fields too
        cls.student = make_person('Stu', 'Zqdent', id_number='s990001')

    def test_exact_name_match(self):
        persons, match = utils_person.get_person(string='Jane Zqroe')
        self.assertEqual((list(persons), match), ([self.jane], 'db_exact'))

    def test_relaxed_match_on_initial_and_last_name(self):
        persons, match = utils_person.get_person(string='J. Zqroe')
        self.assertEqual((list(persons), match), ([self.jane], 'db_relaxed'))

    def test_exact_only_gives_no_relaxed_match(self):
        persons, match = utils_person.get_person(string='J. Zqroe', exact=True)
        self.assertEqual((list(persons), match), ([], None))

    def test_no_match(self):
        persons, _match = utils_person.get_person(string='Ann Zqlee')
        self.assertEqual(list(persons), [])

    def test_study_number(self):
        persons, match = utils_person.get_person(id_number='s990001', exact=True)
        self.assertEqual((list(persons), match), ([self.student], 'db_exact'))

    def test_nothing_to_search_for(self):
        self.assertEqual(utils_person.get_person(), ([], ''))


@override_settings(USE_LDAP=False)
class GetPersonFromStringTests(_UserCase):
    """get_person_from_string with the directory off: only the database is used."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.jane = Person.objects.create(name='Jane Zqroe')
        cls.student = make_person('Stu', 'Zqdent', id_number='s990001')
        cls.staff = make_person('Su', 'Zqvisor', initials='zqsv')

    def resolve(self, value, **kwargs):
        with mock.patch('publications.utils_person.ldap3.Connection',
                        side_effect=AssertionError('ldap3 must not be used')):
            persons, match = utils_person.get_person_from_string(value, self.user, **kwargs)
        return (list(persons) if persons is not None else None), match

    def test_id_tag(self):
        self.assertEqual(self.resolve(f'Whatever Name [id:{self.jane.pk}]'),
                         ([self.jane], 'pid'))

    def test_id_tag_of_missing_person(self):
        self.assertEqual(self.resolve('Jane Zqroe [id:999999]'), (None, None))

    def test_study_number_in_database(self):
        self.assertEqual(self.resolve('s990001'), ([self.student], 'db_exact'))

    def test_unknown_study_number(self):
        self.assertEqual(self.resolve('s990999'), (None, None))

    def test_initials_in_database(self):
        self.assertEqual(self.resolve('zqsv'), ([self.staff], 'db_exact'))

    def test_unknown_initials(self):
        self.assertEqual(self.resolve('zqxx'), (None, None))

    def test_name_exact(self):
        # Before the fix, every plain name raised NameError (get_from_namestring).
        self.assertEqual(self.resolve('Jane Zqroe'), ([self.jane], 'db_exact'))

    def test_name_relaxed(self):
        self.assertEqual(self.resolve('J. Zqroe'), ([self.jane], 'db_relaxed'))

    def test_name_without_first_name_is_not_resolved(self):
        self.assertEqual(self.resolve('van Zqroe'), (None, None))


def _no_extra_persons(test, before):
    test.assertEqual(Person.objects.count(), before)


@override_settings(USE_LDAP=True)
class LdapLookupTests(_UserCase):
    """With USE_LDAP on, a study number or initials not in the database are looked up in the
    directory (mocked). The person is built from the entry but not saved (save=False).

    Before the fix, get_from_studynumber/get_from_initials called
    get_or_create_person_from_ldap(person=...) and every directory hit raised TypeError."""

    def test_study_number_found_in_directory(self):
        before = Person.objects.count()
        with mock.patch('publications.utils_person.find_ldap_person',
                        return_value=[student_entry('s990777')]) as find:
            persons, match = utils_person.get_from_studynumber('s990777', self.user)
        find.assert_called_once_with(name='s990777')
        self.assertEqual(match, 'ldap')
        [person] = persons
        self.assertEqual((person.first, person.last, person.id_number, person.position),
                         ('Stu', 'Zqdent', 's990777', 'student'))
        self.assertIsNone(person.pk)
        _no_extra_persons(self, before)

    def test_initials_found_in_directory(self):
        entry = ldap_entry('Zqvisor', 'Su', initials='zqsu')   # neither student nor title
        with mock.patch('publications.utils_person.find_ldap_person',
                        return_value=[entry]) as find:
            persons, match = utils_person.get_from_initials('zqsu', self.user)
        find.assert_called_once_with(initials='zqsu')
        self.assertEqual(match, 'ldap')
        self.assertEqual([(p.last, p.initials) for p in persons], [('Zqvisor', 'zqsu')])

    def test_get_person_from_string_saves_directory_person_on_request(self):
        with mock.patch('publications.utils_person.find_ldap_person',
                        return_value=[student_entry('s990778')]):
            persons, match = utils_person.get_person_from_string(
                's990778', self.user, save=True)
        self.assertEqual(match, 'ldap')
        self.assertTrue(Person.objects.filter(id_number='s990778', last='Zqdent').exists())
        self.assertEqual(Person.objects.get(id_number='s990778').created_by, self.user)

    def test_ldap_tag_forces_directory_although_in_database(self):
        make_person('Old', 'Zqrecord', id_number='s990779')
        with mock.patch('publications.utils_person.find_ldap_person',
                        return_value=[student_entry('s990779')]) as find:
            persons, match = utils_person.get_person_from_string('s990779 [id:ldap]', self.user)
        find.assert_called_once_with(name='s990779')
        self.assertEqual(match, 'ldap')
        # The person already in the database is reused, not duplicated.
        self.assertEqual([p.last for p in persons], ['Zqrecord'])

    def test_not_in_directory(self):
        with mock.patch('publications.utils_person.find_ldap_person', return_value=[]):
            self.assertEqual(utils_person.get_from_studynumber('s990780', self.user),
                             (None, None))
            self.assertEqual(utils_person.get_from_initials('zqnn', self.user), (None, None))

    def test_database_hit_does_not_ask_directory(self):
        student = make_person('Stu', 'Zqdent', id_number='s990781')
        with mock.patch('publications.utils_person.find_ldap_person') as find:
            persons, match = utils_person.get_from_studynumber('s990781', self.user)
        find.assert_not_called()
        self.assertEqual((list(persons), match), ([student], 'db_exact'))


class LdapEntryToPersonTests(_UserCase):
    """Mapping of a directory entry to Person fields, and get-or-create from an entry."""

    def test_student_entry(self):
        info = utils_person.get_person_info_from_ldap_object(student_entry('s990790'))
        self.assertEqual(info['position'], 'student')
        self.assertEqual(info['id_number'], 's990790')
        self.assertEqual((info['first'], info['last']), ('Stu', 'Zqdent'))
        self.assertEqual((info['first_relaxed'], info['last_relaxed']), ('s', 'zqdent'))

    def test_employee_entry(self):
        entry = ldap_entry('Zqvisor', 'Su Ann', title='Lektor', employee_id='99001',
                           department='Zq Dept', initials='zqsa')
        info = utils_person.get_person_info_from_ldap_object(entry)
        self.assertEqual(
            {k: info[k] for k in ('first', 'middle', 'last', 'position', 'id_number',
                                  'department', 'initials')},
            {'first': 'Su', 'middle': 'Ann', 'last': 'Zqvisor', 'position': 'Lektor',
             'id_number': '99001', 'department': 'Zq Dept', 'initials': 'zqsa'})

    def test_creates_new_person_from_entry(self):
        [person] = utils_person.get_or_create_person_from_ldap(
            ldap_object=student_entry('s990791'), user=self.user)
        self.assertIsNotNone(person.pk)
        self.assertEqual((person.id_number, person.created_by), ('s990791', self.user))

    def test_existing_study_number_is_reused(self):
        existing = make_person('Stu', 'Zqdent', id_number='s990792')
        before = Person.objects.count()
        [person] = utils_person.get_or_create_person_from_ldap(
            ldap_object=student_entry('s990792'), user=self.user)
        self.assertEqual(person, existing)
        self.assertEqual(Person.objects.count(), before)

    def test_needs_entry_and_user(self):
        with self.assertRaises(ValueError):
            utils_person.get_or_create_person_from_ldap(ldap_object=None, user=self.user)
        with self.assertRaises(ValueError):
            utils_person.get_or_create_person_from_ldap(
                ldap_object=student_entry('s990793'), user=None)

    def test_update_person_from_entry(self):
        person = make_person('Old', 'Name', id_number='s990794')
        utils_person.update_person_from_ldap_object(
            person, student_entry('s990794', sn='Zqnew', given_name='Stu'), user=self.user)
        person.refresh_from_db()
        self.assertEqual((person.first, person.last, person.position),
                         ('Stu', 'Zqnew', 'student'))
        self.assertEqual(person.modified_by, self.user)


class LdapEntryMatchingTests(_UserCase):
    """get_or_create_person_from_ldap with an entry that has both an id_number and initials:
    an existing person matches when both match, or one matches and the other is empty in the
    database. A person never matches only because one of their fields is empty (before the
    fix, every person with empty initials or an empty id_number matched)."""

    def entry(self):
        return ldap_entry('Zqvisor', 'Su', title='Lektor', employee_id='99001',
                          department='Zq Dept', initials='zqsa')

    def get_or_create(self, entry=None):
        [person] = utils_person.get_or_create_person_from_ldap(
            ldap_object=entry or self.entry(), user=self.user)
        return person

    def assertNewPerson(self, person, *unrelated):
        self.assertNotIn(person, unrelated)
        self.assertEqual((person.id_number, person.initials, person.last),
                         ('99001', 'zqsa', 'Zqvisor'))
        self.assertEqual(person.created_by, self.user)

    def test_unrelated_persons_with_empty_fields_are_not_matched(self):
        no_initials = make_person('Un', 'Zqrel', id_number='s990100')
        no_id_number = make_person('Ot', 'Zqher', initials='zqot')
        self.assertNewPerson(self.get_or_create(), no_initials, no_id_number)

    def test_same_id_number_other_initials_is_not_matched(self):
        other = make_person('Su', 'Zqvisor', id_number='99001', initials='zqxx')
        self.assertNewPerson(self.get_or_create(), other)

    def test_same_initials_other_id_number_is_not_matched(self):
        other = make_person('Su', 'Zqvisor', id_number='88001', initials='zqsa')
        self.assertNewPerson(self.get_or_create(), other)

    def test_exact_match(self):
        existing = make_person('Su', 'Zqvisor', id_number='99001', initials='zqsa')
        self.assertEqual(self.get_or_create(), existing)

    def test_id_number_match_with_empty_initials(self):
        existing = make_person('Su', 'Zqvisor', id_number='99001')
        self.assertEqual(self.get_or_create(), existing)

    def test_initials_match_with_empty_id_number(self):
        existing = make_person('Su', 'Zqvisor', initials='zqsa')
        self.assertEqual(self.get_or_create(), existing)

    def test_exact_match_is_preferred(self):
        make_person('Su', 'Zqvisor', initials='zqsa')
        make_person('Su', 'Zqvisor', id_number='99001')
        exact = make_person('Su', 'Zqvisor', id_number='99001', initials='zqsa')
        self.assertEqual(self.get_or_create(), exact)

    def test_entry_without_id_number_and_initials_matches_nobody(self):
        # Before the fix, the empty query matched every person and returned one of them.
        existing = make_person('Any', 'Zqbody', id_number='s990101', initials='zqab')
        person = self.get_or_create(ldap_entry('Zqnone', 'No'))
        self.assertNotEqual(person, existing)
        self.assertEqual((person.last, person.id_number, person.initials),
                         ('Zqnone', '', ''))
