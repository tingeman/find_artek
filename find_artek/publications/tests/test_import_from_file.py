# -*- coding: utf-8 -*-
"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import pdb
from django.test import TestCase
from find_artek.publications import ldap_person
from find_artek.publications import models
from find_artek.publications import import_from_file
from find_artek.publications.scripts import prepopulate

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


class ImportFromFileTest(TestCase):

    def setUp(self):
        prepopulate.prepopulate_pubtype(prepopulate.pubtype_dict)
        prepopulate.prepopulate_topic(prepopulate.topics_data)
        kwargs = {'number': '00-00',
                  'title': 'Test report',
                  'year': '2000',
                  'created_by': user,
                  'modified_by': user,
                  'abstract': 'This is an abstract. Not very long.',
                  'type': models.PubType.objects.get(type='STUDENTREPORT'),}

        # Create or update publication
        instance, created = models.Publication.objects.get_or_create(
                                defaults=kwargs)

        self.pub = instance

        print "'{0}': created= {1}". format(instance.title, created)


    def test_add_persons_to_publication(self):
        """
        Test that we can add persons to a publication based on different
        types of ldap searches as well as a pure name string.
        """
        print "Running: test_add_persons_to_publication"

        # Test that we can add names from strings
        names = 'Thomas Ingeman-Nielsen, Pernille Erland Jensen'
        import_from_file.add_persons_to_publication(names,
                                                    self.pub,
                                                    'author',
                                                    user)
        auths = self.pub.author.all()
        self.assertEquals(len(auths),2)
        self.assertEquals(auths[0].first, 'Thomas')
        self.assertEquals(auths[1].first, 'Pernille')
        self.assertEquals(auths[1].middle, 'Erland')
        self.assertEquals(auths[1].first, 'Pernille')
        self.assertEquals(auths[0].initials, '')
        self.assertEquals(auths[1].initials, '')
        self.assertEquals(auths[0].department, '')
        self.assertEquals(auths[1].department, '')

        # And once again, a different format
        names = 'Ingeman-Nielsen, Thomas, Jensen, Pernille Erland'
        import_from_file.add_persons_to_publication(names,
                                                    self.pub,
                                                    'author',
                                                    user)

        auths = self.pub.author.all()
        self.assertEquals(len(auths),4)
        self.assertEquals(auths[2].first, 'Thomas')
        self.assertEquals(auths[3].first, 'Pernille')
        self.assertEquals(auths[3].middle, 'Erland')
        self.assertEquals(auths[3].first, 'Pernille')
        self.assertEquals(auths[2].initials, '')
        self.assertEquals(auths[3].initials, '')
        self.assertEquals(auths[2].department, '')
        self.assertEquals(auths[3].department, '')

        # Now do ldap search on initials
        names = 'thin; peej'
        import_from_file.add_persons_to_publication(names,
                                                    self.pub,
                                                    'author',
                                                    user)

        auths = self.pub.author.all()
        self.assertEquals(len(auths),6)
        self.assertEquals(auths[4].first, 'Thomas')
        self.assertEquals(auths[5].first, 'Pernille')
        self.assertEquals(auths[5].middle, 'Erland')
        self.assertEquals(auths[4].initials, 'thin')
        self.assertEquals(auths[5].initials, 'peej')
        self.assertIn('Byggeri', auths[4].department)
        self.assertIn('Byggeri', auths[5].department)
        self.assertEquals(auths[4].id_number, '11189')

        # Now do ldap search on study numbers
        names = 's133712;s133717'
        import_from_file.add_persons_to_publication(names,
                                                    self.pub,
                                                    'author',
                                                    user)

        auths = self.pub.author.all()
        self.assertEquals(len(auths),8)
        self.assertEquals(auths[6].first, 'Martin')
        self.assertEquals(auths[7].first, 'Mads')
        self.assertEquals(auths[7].last,  u'S\xf8rensen')
        self.assertEquals(auths[6].initials, '')
        self.assertEquals(auths[7].initials, '')
        self.assertEquals(auths[6].position, 'student')
        self.assertEquals(auths[7].position, 'student')
        self.assertEquals(auths[6].id_number, 's133712')

        # And now some troublesome characters
        names = u'Åse Ælling Sørensen'
        import_from_file.add_persons_to_publication(names,
                                                    self.pub,
                                                    'author',
                                                    user)

        auths = self.pub.author.all()
        self.assertEquals(len(auths),9)
        self.assertEquals(auths[8].first, u'Åse')
        self.assertEquals(auths[8].middle, u'Ælling')
        self.assertEquals(auths[8].last, u'Sørensen')
        self.assertEquals(auths[8].initials, '')
        self.assertEquals(auths[8].department, '')

        # Test that LDAP search binds the same Person model entry
        n_before = len(models.Person.objects.all())
        names = 'thin'
        import_from_file.add_persons_to_publication(names,
                                                    self.pub,
                                                    'author',
                                                    user)

        n_after = len(models.Person.objects.all())
        self.assertEquals(n_before, n_after)

        # Author 0 is Thomas Ingeman-Nielsen, created from name string,
        # this should be a single person reference
        self.assertEquals(len(auths[0].authorship_set.all()), 1)

        # Author 4 is Thomas Ingeman-Nielsen, created from LDAP search,
        # this authorship_set, should contain two entries (author 4 and 9)
        self.assertEquals(len(auths[4].authorship_set.all()), 2)



