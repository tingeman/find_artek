"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import pdb
from django.test import TestCase
from find_artek.publications import ldap_person
from find_artek.publications import models

"""
Available assertion methods, callable within TestCase by invoking f.ex.:

self.assertRaises(func(), ValueError)

or

with self.assertRaises(ValueError):
    some_method_or_function_call(*args, **kwargs)

List of available assertions:
-----------------------------
unittest.TestCase.assertAlmostEqual
unittest.TestCase.assertAlmostEquals
unittest.TestCase.assertDictContainsSubset
unittest.TestCase.assertDictEqual
unittest.TestCase.assertEqual
unittest.TestCase.assertEquals
unittest.TestCase.assertFalse
unittest.TestCase.assertGreater
unittest.TestCase.assertGreaterEqual
unittest.TestCase.assertIn
unittest.TestCase.assertIs
unittest.TestCase.assertIsInstance
unittest.TestCase.assertIsNone
unittest.TestCase.assertIsNot
unittest.TestCase.assertIsNotNone
unittest.TestCase.assertItemsEqual
unittest.TestCase.assertLess
unittest.TestCase.assertLessEqual
unittest.TestCase.assertListEqual
unittest.TestCase.assertMultiLineEqual
unittest.TestCase.assertNotAlmostEqual
unittest.TestCase.assertNotAlmostEquals
unittest.TestCase.assertNotEqual
unittest.TestCase.assertNotEquals
unittest.TestCase.assertNotIn
unittest.TestCase.assertNotIsInstance
unittest.TestCase.assertNotRegexpMatches
unittest.TestCase.assertRaises
unittest.TestCase.assertRaisesRegexp
unittest.TestCase.assertRegexpMatches
unittest.TestCase.assertSequenceEqual
unittest.TestCase.assertSetEqual
unittest.TestCase.assertTrue
unittest.TestCase.assertTupleEqual
"""

user = models.User.objects.get(username='thin')


class LdapPersonTest(TestCase):
    def test_find_ldap_person(self):
        """
        Test that we can search for a person in active directory.
        """
        print "Running: test_find_ldap_person"
        # Find person by study number
        result = ldap_person.find_ldap_person(name='s051423')
        self.assertEquals(len(result), 1)
        self.assertEquals(result[0][1]['givenName'], ['Sun'])

        # Find persons by given name
        result = ldap_person.find_ldap_person(givenName='Thomas')
        self.assertGreater(len(result), 1)

        # Find persons by given name and initials
        result = ldap_person.find_ldap_person(givenName='Thomas',
                                              initials='thin')
        self.assertEquals(len(result), 1)
        self.assertEquals(result[0][1]['sn'], ['Ingeman-Nielsen'])


    def test_create_person_from_ldap(self):
        """
        Test that we can create a person based on the LDAP search.
        """
        print "Running: test_create_person_from_ldap"

        # Find persons by given name and initials
        result = ldap_person.find_ldap_person(givenName='Thomas',
                                               initials='thin')
        self.assertEquals(len(result), 1)
        self.assertEquals(result[0][1]['sn'], ['Ingeman-Nielsen'])

        # Now we have me!
        p = ldap_person.create_person_from_ldap(person=result[0], user=user)
        self.assertEquals(p[0].first, 'Thomas')
        self.assertEquals(p[0].last, 'Ingeman-Nielsen')
        self.assertEquals(p[0].first_relaxed, 't')
        self.assertEquals(p[0].last_relaxed, 'ingeman-nielsen')
        self.assertEquals(p[0].initials, 'thin')
        self.assertEquals(p[0].id_number, '11189')
        self.assertEquals(p[0].position, 'Lektor')
        self.assertEquals(p[0].id, 1)

        p = ldap_person.create_person_from_ldap(person=result[0], user=user)
        self.assertEquals(p[0].id, 2)

    def test_get_or_create_person_from_ldap(self):
        """
        Test that we can create and get a person based on the LDAP search.
        """
        print "Running: test_get_orcreate_person_from_ldap"

        # Find persons by given name and initials
        result = ldap_person.find_ldap_person(givenName='Thomas',
                                               initials='thin')
        self.assertEquals(len(result), 1)
        self.assertEquals(result[0][1]['sn'], ['Ingeman-Nielsen'])

        # Now we have me!
        p = ldap_person.get_or_create_person_from_ldap(person=result[0], user=user)
        self.assertEquals(p[0].first, 'Thomas')
        self.assertEquals(p[0].last, 'Ingeman-Nielsen')
        self.assertEquals(p[0].first_relaxed, 't')
        self.assertEquals(p[0].last_relaxed, 'ingeman-nielsen')
        self.assertEquals(p[0].initials, 'thin')
        self.assertEquals(p[0].id_number, '11189')
        self.assertEquals(p[0].position, 'Lektor')
        self.assertEquals(p[0].id, 1)

        p = ldap_person.get_or_create_person_from_ldap(person=result[0], user=user)
        self.assertEquals(p[0].id, 1)


