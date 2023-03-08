#

import unittest
from publications.models import Person, Publication


class TestPublicationData(unittest.TestCase):
    def setUp(self):
        pass


    # ------------------- starts here ------------------- #
    # These unit tests were created to compare data relations in the old v1.6 app and verify that features such as many-to-many relationships are still functioning correctly. 

    # Check whether the person named 'Niels Foged' is associated with the expected authorship of publications.
    def test_authorships(self):
        # Get the real data from the database
        person_niels_foged = Person.objects.get(id=3)
        niels_foged_publication_author = person_niels_foged.publication_author.all()

        # Define the expected titles
        expected_titles = [
            'Rekognocering mellem Utoqqaat og Maligiaq'
        ]

        # Iterate through the publications and compare their titles with the expected titles
        for i, publication_author in enumerate(niels_foged_publication_author):
            with self.subTest(i=i):
                self.assertEqual(publication_author.title, expected_titles[i])


    # Check whether the person named "Niels Foged" is associated with the expected editorship of publications.
    def test_editorships(self):
        # Get the real data from the database
        person_niels_foged = Person.objects.get(id=3)
        niels_foged_publication_editor = person_niels_foged.publication_editor.all()

        # Define the expected titles (empty list)
        expected_titles = []

        # Iterate through the publications and compare their titles with the expected titles
        for i, publication_editor in enumerate(niels_foged_publication_editor):
            with self.subTest(i=i):
                self.assertIn(publication_editor.title, expected_titles)


    # Check whether the person named "Niels Foged" is associated with the expected supervision of publications.
    def test_supervisorships(self):
        # Get the real data from the database
        person_niels_foged = Person.objects.get(id=3)
        niels_foged_publication_supervisor = person_niels_foged.publication_supervisor.all()

        # Define the expected titles
        expected_titles = [
            'Tekniske undersøgelser for anlægsarbejde i fjeld i Grønland',
            'Sonic Methods and Rock Mass Classification related to Tunnelling in Greenland',
            'Evaluering af permafrost og geotekniske forhold i Kangerlussuaq Lufthavn'
        ]

        # Iterate through the publications and compare their titles with the expected titles
        for i, publication_supervisor in enumerate(niels_foged_publication_supervisor):
            with self.subTest(i=i):
                self.assertEqual(publication_supervisor.title, expected_titles[i])

    
    # Test if can get all the authorships from a publication
    def test_authors(self):
        # Get the real data from the database
        publication = Publication.objects.get(id=130) # Title: Tekniske undersøgelser for anlægsarbejde i fjeld i Grønland
        authors = publication.authors.all()

        # Define the expected names
        expected_names = [
            'Mathias Dahl'
        ]

        # Iterate through the authors and compare their names with the expected names
        for i, author in enumerate(authors):
            with self.subTest(i=i):
                self.assertEqual(f"{author.first} {author.last}", expected_names[i])


    # Test if you can get all the supervisors from a publication
    def test_supervisors(self):
        # Get the real data from the database
        publication = Publication.objects.get(id=130)
        supervisors = publication.supervisors.all()

        # Define the expected names
        expected_names = [
            'Niels Foged',
            'Thomas Ingeman-Nielsen'
        ]

        # Iterate through the supervisors and compare their names with the expected names
        for i, supervisor in enumerate(supervisors):
            with self.subTest(i=i):
                self.assertEqual(f"{supervisor.first} {supervisor.last}", expected_names[i])


    # ------------------- ends here ------------------- #
    # These unit tests were created to compare data relations in the old v1.6 app and verify that features such as many-to-many relationships are still functioning correctly. 
