"""Permission methods of Publication, Feature and Person (plan registration T3, roadmap FA-R53 S4).

Matrix (app label 'publications'; active superusers pass every has_perm):

- Publication.is_editable_by: logged in and (change_publication, or edit_own_publication and
  listed as author, supervisor or editor).
- Publication.is_deletable_by: logged in and (delete_publication, or delete_own_publication
  and own).
- Publication.is_verifiable_by: verify_publication.
- Feature.is_editable_by / is_deletable_by: change_feature / delete_feature, or
  edit_own_feature / delete_own_feature and created_by is the user.
- Person.is_editable_by / is_deletable_by: change_person / delete_person, or the *_own_*
  permission and the person is the user (Person.is_related_to_user).

Anonymous users get False everywhere, without exceptions. Permissions are given directly
(not through the registration groups), so these tests don't depend on them.
"""
import datetime

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.test import TestCase

from publications.models import (
    Authorship, Editorship, Feature, Person, Publication, PubType, Supervisorship,
)


def _user(username, *codenames, superuser=False):
    """Create a user with the given 'publications' permissions and return a fresh copy
    (the permission cache of the instance that was changed would be stale)."""
    if superuser:
        user = User.objects.create_superuser(username, password='x')
    else:
        user = User.objects.create_user(username, password='x')
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label='publications', codename=codename))
    return User.objects.get(pk=user.pk)


class PublicationPermissionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = PubType.objects.create(type='STUDENTREPORT')
        cls.pub = Publication.objects.create(
            type=pubtype, title='Own report', number='99-01', year=1999)
        cls.other_pub = Publication.objects.create(
            type=pubtype, title='Other report', number='99-02', year=1999)

        # Persons as listed on cls.pub; matched by id_number (students) or initials (staff).
        cls.student = Person.objects.create(first='Stu', last='Dent', id_number='S990001')
        cls.supervisor = Person.objects.create(first='Su', last='Pervisor', initials='SUPV')
        cls.editor = Person.objects.create(first='Ed', last='Itor', initials='edtr')
        Authorship.objects.create(publication=cls.pub, person=cls.student, author_id=0)
        Supervisorship.objects.create(publication=cls.pub, person=cls.supervisor, supervisor_id=0)
        Editorship.objects.create(publication=cls.pub, person=cls.editor, editor_id=0)
        # A person without id_number/initials must not match anything.
        cls.blank = Person.objects.create(first='No', last='Ids')
        Authorship.objects.create(publication=cls.other_pub, person=cls.blank, author_id=0)

    def assertNone(self, user, pubs=None):
        for pub in pubs or (self.pub, self.other_pub):
            self.assertFalse(pub.is_editable_by(user))
            self.assertFalse(pub.is_deletable_by(user))
            self.assertFalse(pub.is_verifiable_by(user))

    def test_anonymous_gets_false_everywhere(self):
        self.assertNone(AnonymousUser())

    def test_user_without_permissions_gets_false_even_when_listed(self):
        self.assertNone(_user('s990001'))

    def test_edit_own_as_author_by_id_number_case_insensitive(self):
        user = _user('s990001', 'edit_own_publication')
        self.assertTrue(self.pub.is_editable_by(user))
        self.assertFalse(self.other_pub.is_editable_by(user))
        self.assertFalse(self.pub.is_deletable_by(user))
        self.assertFalse(self.pub.is_verifiable_by(user))

    def test_edit_own_as_supervisor_by_initials_case_insensitive(self):
        user = _user('supv', 'edit_own_publication')
        self.assertTrue(self.pub.is_editable_by(user))
        self.assertFalse(self.other_pub.is_editable_by(user))

    def test_edit_own_as_editor_by_initials(self):
        user = _user('EDTR', 'edit_own_publication')
        self.assertTrue(self.pub.is_editable_by(user))
        self.assertFalse(self.other_pub.is_editable_by(user))

    def test_edit_own_not_listed_is_not_editable(self):
        user = _user('s123456', 'edit_own_publication')
        self.assertFalse(self.pub.is_editable_by(user))
        self.assertFalse(self.other_pub.is_editable_by(user))

    def test_edit_own_on_unsaved_publication_is_false(self):
        user = _user('s990001', 'edit_own_publication')
        unsaved = Publication(type=self.pub.type, title='New', year=2000)
        self.assertFalse(unsaved.is_editable_by(user))

    def test_change_publication_edits_any(self):
        user = _user('staff1', 'change_publication')
        self.assertTrue(self.pub.is_editable_by(user))
        self.assertTrue(self.other_pub.is_editable_by(user))
        self.assertFalse(self.pub.is_deletable_by(user))
        self.assertFalse(self.pub.is_verifiable_by(user))

    def test_delete_publication_deletes_any(self):
        user = _user('staff2', 'delete_publication')
        self.assertTrue(self.pub.is_deletable_by(user))
        self.assertTrue(self.other_pub.is_deletable_by(user))
        self.assertFalse(self.pub.is_editable_by(user))

    def test_delete_own_publication_own_and_not_own(self):
        user = _user('S990001', 'delete_own_publication')
        self.assertTrue(self.pub.is_deletable_by(user))
        self.assertFalse(self.other_pub.is_deletable_by(user))
        self.assertFalse(self.pub.is_editable_by(user))

    def test_verify_publication(self):
        user = _user('verifier', 'verify_publication')
        self.assertTrue(self.pub.is_verifiable_by(user))
        self.assertTrue(self.other_pub.is_verifiable_by(user))
        self.assertFalse(self.pub.is_editable_by(user))
        self.assertFalse(self.pub.is_deletable_by(user))

    def test_other_permissions_do_not_verify(self):
        user = _user('staff3', 'change_publication', 'delete_publication',
                     'edit_own_publication', 'delete_own_publication')
        self.assertFalse(self.pub.is_verifiable_by(user))

    def test_superuser_gets_everything(self):
        user = _user('admin', superuser=True)
        for pub in (self.pub, self.other_pub):
            self.assertTrue(pub.is_editable_by(user))
            self.assertTrue(pub.is_deletable_by(user))
            self.assertTrue(pub.is_verifiable_by(user))

    def test_inactive_user_with_permissions_gets_false(self):
        user = _user('staff4', 'change_publication', 'delete_publication', 'verify_publication')
        user.is_active = False
        user.save()
        self.assertNone(User.objects.get(pk=user.pk))

    def test_sorted_supervisors_and_editors(self):
        # These helpers used the old field names (supervisor/editor) and raised AttributeError.
        self.assertEqual(list(self.pub.sorted_supervisors()), [self.supervisor])
        self.assertEqual(list(self.pub.sorted_editors()), [self.editor])


class FeaturePermissionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.creator = User.objects.create_user('s990001', password='x')
        cls.other = User.objects.create_user('s990002', password='x')
        cls.own = Feature.objects.create(name='own', date=datetime.date(2000, 1, 1))
        Feature.objects.filter(pk=cls.own.pk).update(created_by=cls.creator, modified_by=cls.other)
        cls.own.refresh_from_db()
        cls.orphan = Feature.objects.create(name='orphan', date=datetime.date(2000, 1, 1))
        cls.orphan.refresh_from_db()

    def test_anonymous_gets_false(self):
        for feature in (self.own, self.orphan):
            self.assertFalse(feature.is_editable_by(AnonymousUser()))
            self.assertFalse(feature.is_deletable_by(AnonymousUser()))

    def test_user_without_permissions_gets_false(self):
        user = User.objects.get(pk=self.creator.pk)
        self.assertFalse(self.own.is_editable_by(user))
        self.assertFalse(self.own.is_deletable_by(user))

    def test_own_created_feature_editable_and_deletable(self):
        user = _user('s990003', 'edit_own_feature', 'delete_own_feature')
        Feature.objects.filter(pk=self.own.pk).update(created_by=user)
        self.own.refresh_from_db()
        self.assertTrue(self.own.is_editable_by(user))
        self.assertTrue(self.own.is_deletable_by(user))

    def test_modifier_is_not_owner(self):
        # Only created_by counts; modified_by (self.other) does not own the feature.
        for codename in ('edit_own_feature', 'delete_own_feature'):
            self.other.user_permissions.add(
                Permission.objects.get(content_type__app_label='publications', codename=codename))
        user = User.objects.get(pk=self.other.pk)
        self.assertFalse(self.own.is_editable_by(user))
        self.assertFalse(self.own.is_deletable_by(user))

    def test_created_by_none_is_false_without_exception(self):
        user = _user('s990004', 'edit_own_feature', 'delete_own_feature')
        self.assertIsNone(self.orphan.created_by)
        self.assertFalse(self.orphan.is_editable_by(user))
        self.assertFalse(self.orphan.is_deletable_by(user))

    def test_change_feature_edits_any(self):
        user = _user('staff1', 'change_feature')
        self.assertTrue(self.own.is_editable_by(user))
        self.assertTrue(self.orphan.is_editable_by(user))
        self.assertFalse(self.own.is_deletable_by(user))

    def test_delete_feature_deletes_any(self):
        user = _user('staff2', 'delete_feature')
        self.assertTrue(self.own.is_deletable_by(user))
        self.assertTrue(self.orphan.is_deletable_by(user))
        self.assertFalse(self.own.is_editable_by(user))

    def test_superuser_gets_everything(self):
        user = _user('admin', superuser=True)
        self.assertTrue(self.orphan.is_editable_by(user))
        self.assertTrue(self.orphan.is_deletable_by(user))


class PersonPermissionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.person = Person.objects.create(first='Stu', last='Dent', id_number='S990001')
        cls.blank = Person.objects.create(first='No', last='Ids')

    def test_anonymous_gets_false(self):
        for person in (self.person, self.blank):
            self.assertFalse(person.is_related_to_user(AnonymousUser()))
            self.assertFalse(person.is_editable_by(AnonymousUser()))
            self.assertFalse(person.is_deletable_by(AnonymousUser()))

    def test_edit_and_delete_own_person(self):
        user = _user('s990001', 'edit_own_person', 'delete_own_person')
        self.assertTrue(self.person.is_editable_by(user))
        self.assertTrue(self.person.is_deletable_by(user))
        self.assertFalse(self.blank.is_editable_by(user))
        self.assertFalse(self.blank.is_deletable_by(user))

    def test_change_and_delete_person_any(self):
        user = _user('staff1', 'change_person', 'delete_person')
        self.assertTrue(self.blank.is_editable_by(user))
        self.assertTrue(self.blank.is_deletable_by(user))

    def test_without_permissions_false(self):
        user = _user('s990001')
        self.assertFalse(self.person.is_editable_by(user))
        self.assertFalse(self.person.is_deletable_by(user))
