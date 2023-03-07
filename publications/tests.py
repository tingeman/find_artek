#

import unittest
from publications.models import Person


class TestPublicationData(unittest.TestCase):
    def setUp(self):
        pass


    # ------------------- starts here ------------------- #
    # These unit tests were created to compare data relations in the old v1.6 app and verify that features such as many-to-many relationships are still functioning correctly. 

    # Check whether the person named 'Niels Foged' is associated with the expected authorship of publications.
    def test_authorships(self):
        # Get the real data from the database
        person_niels_foged = Person.objects.get(id=3)
        niels_foged_author_publications = person_niels_foged.author_publication.all()

        # Define the expected titles
        expected_titles = [
            'Rekognocering mellem Utoqqaat og Maligiaq'
        ]

        # Iterate through the publications and compare their titles with the expected titles
        for i, author_publication in enumerate(niels_foged_author_publications):
            with self.subTest(i=i):
                self.assertEqual(author_publication.title, expected_titles[i])


    # Check whether the person named "Niels Foged" is associated with the expected editorship of publications.
    def test_editorships(self):
        # Get the real data from the database
        person_niels_foged = Person.objects.get(id=3)
        niels_foged_editor_publications = person_niels_foged.editor_publication.all()

        # Define the expected titles (empty list)
        expected_titles = []

        # Iterate through the publications and compare their titles with the expected titles
        for i, editor_publication in enumerate(niels_foged_editor_publications):
            with self.subTest(i=i):
                self.assertIn(editor_publication.title, expected_titles)


    # Check whether the person named "Niels Foged" is associated with the expected supervision of publications.
    def test_supervisorships(self):
        # Get the real data from the database
        person_niels_foged = Person.objects.get(id=3)
        niels_foged_supervisor_publications = person_niels_foged.supervisor_publication.all()

        # Define the expected titles
        expected_titles = [
            'Tekniske undersøgelser for anlægsarbejde i fjeld i Grønland',
            'Sonic Methods and Rock Mass Classification related to Tunnelling in Greenland',
            'Evaluering af permafrost og geotekniske forhold i Kangerlussuaq Lufthavn'
        ]

        # Iterate through the publications and compare their titles with the expected titles
        for i, supervisor_publication in enumerate(niels_foged_supervisor_publications):
            with self.subTest(i=i):
                self.assertEqual(supervisor_publication.title, expected_titles[i])

    


    # ------------------- ends here ------------------- #
    # These unit tests were created to compare data relations in the old v1.6 app and verify that features such as many-to-many relationships are still functioning correctly. 
