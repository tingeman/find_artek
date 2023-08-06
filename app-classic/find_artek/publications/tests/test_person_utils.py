"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from publications import person_utils


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



class PersonUtilsTest(TestCase):
    def test_parse_name_list(self):
        """
        Test that we can parse different types of name lists correctly
        """
        print "Running: test_parse_name_list"


        strs = ['Thomas Ingeman-Nielsen, Pernille Erland Jensen, Joakim von And',
                'Thomas Ingeman-Nielsen, Pernille Erland Jensen & Joakim von And',
                'Thomas Ingeman-Nielsen, Pernille Erland Jensen og Joakim von And',
                'Thomas Ingeman-Nielsen, Pernille Erland Jensen and Joakim von And',
                'Jensen, Pernille Erland',
                'Ingeman-Nielsen, Thomas, Jensen, Pernille Erland, von And, Joakim',
                'Ingeman-Nielsen, Thomas, Jensen, Pernille Erland & von And, Joakim',
                'Ingeman-Nielsen, Thomas, Jensen, Pernille Erland og von And, Joakim',
                'Ingeman-Nielsen, Thomas, Jensen, Pernille Erland and von And, Joakim',
                's050001; s060102; s070203', # What happens when passing study numbers?
                'thin; peej; gunki' # What happens when passing initials
                ]

        expected = [['Thomas Ingeman-Nielsen', 'Pernille Erland Jensen', 'Joakim von And'],
                    ['Thomas Ingeman-Nielsen', 'Pernille Erland Jensen', 'Joakim von And'],
                    ['Thomas Ingeman-Nielsen', 'Pernille Erland Jensen', 'Joakim von And'],
                    ['Thomas Ingeman-Nielsen', 'Pernille Erland Jensen', 'Joakim von And'],
                    ['Jensen, Pernille Erland'],
                    ['Ingeman-Nielsen, Thomas', 'Jensen, Pernille Erland', 'von And, Joakim'],
                    ['Ingeman-Nielsen, Thomas', 'Jensen, Pernille Erland', 'von And, Joakim'],
                    ['Ingeman-Nielsen, Thomas', 'Jensen, Pernille Erland', 'von And, Joakim'],
                    ['Ingeman-Nielsen, Thomas', 'Jensen, Pernille Erland', 'von And, Joakim'],
                    ['s050001', 's060102', 's070203'],
                    ['thin', 'peej', 'gunki']
                    ]

        # test the parsing of these lists
        for n,s in enumerate(strs):
            r = person_utils.parse_name_list(s)
            self.assertEquals(r, expected[n])


