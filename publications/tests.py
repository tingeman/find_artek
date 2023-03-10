#

import unittest
from publications.models import FileObject, Keyword, Person, Publication, Topic


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


    # find publication type on number: 13-18
    def test_get_type_on_number(self):
        publication = Publication.objects.get(number="13-18")
        type_object = publication.type

        # Define the expected type
        expected_type = 'STUDENTREPORT'

        # Compare the type with the expected type
        self.assertEqual(type_object.type, expected_type)

    # find all associated topics
    def test_get_topics_on_number(self):
        publication = Publication.objects.get(number="13-18")
        topics = publication.publication_topics.all()
        
        expected_topics = [
            'Geoteknik',
        ]

        # Iterate through the topics and compare their names with the expected names
        for i, topic in enumerate(topics):
            with self.subTest(i=i):
                self.assertEqual(topic.topic, expected_topics[i])

    
    # find all associated keywords
    def test_get_keywords_on_number(self):
        publication = Publication.objects.get(number="13-18")
        keywords = publication.publication_keywords.all()

        print("")

        
        expected_keywords = [
            'Permafrost',
            'geotechnic',
            'Greenland',
            'oedometer test',
            'FDR test',
            'Classification test',
            'Temperature controled tests',
            'fine-grained soil',
            'Saline soil',
        ]

        # Iterate through the keywords and compare their names with the expected names
        for i, keyword in enumerate(keywords):
            with self.subTest(i=i):
                self.assertEqual(keyword.keyword, expected_keywords[i])


    # Test if you can find all publications and it's assicated files related to a person - Niels Foged with id 3
    # This is relevant under http://find-artek-1-6-11.local:8080/pubs/person/3/
    def test_get_files_on_person(self):
        # Get the real data from the database
        person = Person.objects.get(id=3)
        author_publications = person.publication_author.all()
        editor_publications = person.publication_editor.all()
        supervisor_publications = person.publication_supervisor.all()


        # Define the expected author reports
        expected_author_reports = [
            'Rekognocering mellem Utoqqaat og Maligiaq'
        ]

        # Definde the expected editor reports
        expected_editor_reports = []

        # Define the expected supervisor reports
        expected_supervisor_reports = [
            'Tekniske undersøgelser for anlægsarbejde i fjeld i Grønland',
            'Sonic Methods and Rock Mass Classification related to Tunnelling in Greenland',
            'Evaluering af permafrost og geotekniske forhold i Kangerlussuaq Lufthavn'
        ]

        # Iterate through author publications
        for i, author_publication in enumerate(author_publications):
            with self.subTest(i=i):
                self.assertIn(author_publication.title, expected_author_reports[i])

        for i, editor_publication in enumerate(editor_publications):
            with self.subTest(i=i):
                self.assertIn(editor_publication.title, expected_editor_reports[i])

        for i, supervisor_publication in enumerate(supervisor_publications):
            with self.subTest(i=i):
                self.assertIn(supervisor_publication.title, expected_supervisor_reports[i])

   # find all appendencis associated with a publication
    def test_get_appendices_on_number(self):
        publication = Publication.objects.get(number="11-28")
        appendices = publication.appendices.all()

        # Define the expected file name
        expected_file_name = 'reports/2011/11-28/Samlet_bilag.pdf'


        # asser each appendix
        for i, appendix in enumerate(appendices):
            with self.subTest(i=i):
                self.assertEqual(appendix.file, expected_file_name)


    # Test if you can get the file object associated with publication id 130
    def test_file(self):
        # Get the real data from the database
        publication = Publication.objects.get(number="09-34", id=130)
        file_object = publication.file

        # Define the expected file name
        expected_file_name = 'reports/2009/09-34.pdf'

        # Compare the file name with the expected file name
        self.assertEqual(file_object.file, expected_file_name)



    # Test if you can get all publications related to a specific topic
    def test_get_publications_on_topic(self):
        # Get the real data from the database
        topic = Topic.objects.get(topic="Geoteknik")

        # Get all publications related to the topic
        publications = Publication.objects.filter(publication_topics=topic).order_by('title')

        # print("\n")
        # # print each publication
        # for publication in publications:
        #     print(publication.title)

        # Define expected publication titles
        expected_publication_titles = [
            'Accuracy of Digital Elevation Model by Structure from Motion using Aerial Imagery',
            'Analyse af eksistens af - samt tilgængelighed til grønlandsrelaterede data',
            'Anvendelsesorienteret undersøgelse af granit',
            'Brugen af permafrostfundering i Grønland',
            'Byudvidelsesområde i Sisimiut - forundersøgelse af område nord for Ulkebugten',
            'Clay Stabilization in Greenland',
            'Deltasedimenter ved Søndre Strømfjord',
            'Design and implementation of a data logger for permafrost temperature long-term monitoring in Arctic regions',
            'Determining Snow Depth Distribution From Unmanned Aerial Vehicles and Digital Photogrammetry ',
            'Development of a geological model for Kangerluk, Disko Island, Central West Greenland',
            'Development of a software application to monitor soil temperature under arctic conditions',
            'Digital Elevation Model Reconstruction of a Glaciarized Basin Using Land-Based Structure from Motion',
            'Dæmning i Sisimiut',
            'Elektroosmose - afvanding af forskellige sedimenter',
            'Establishment of a long-term site for permafrost thickness and temperature monitoring',
            'Estimating Volume and Volume Change of a Small Greenlandic Glacier with Geophysical Methods',
            'Etablering af lufthavne, Grønland',
            'Evaluering af permafrost og geotekniske forhold i Kangerlussuaq Lufthavn',
            'Forstudie til midtvejsprojekt i Sisimiut',
            'Fremstilling af letklinker ud fra grønlandsk ler',
            'Fundering i permafrost - Geotekniske undersøgelser i Kangerlussuaq',
            'Fysiske materialeegenskaber ved Jernoxidstabiliseret jord',
            'Geofysisk forundersøgelse for anlæggelse af mine i Grønland',
            'Geoidehøjden i Sisimiut en analyse af sammenhængen mellem geoidemodeller og middelvandstand',
            'Geoidemodel for Sisimiut - en metode til forbedring af kotering med GPS',
            'Geologisk landskabsanalyse med fotogrammetri som opmålingsværktøj',
            'Geologiske og geofysiske undersøgelser af to områder i Sisimiut',
            'Geomorfologisk landskabsanalyse ved 2. fjorden',
            'Geophysical Investigation for Groundwater at Kangerluk',
            'Geophysical surveys at Thule Air Base, Vehicle Maintenance',
            'Georadar i områder med permafrost, Grønland',
            'Georadar målinger Vandsø 5 Sisimiut',
            'Geotechnical properties of glaciomarine sediments for harbour construction in from Kangerlusuaq fjord',
            'Geotekniske egenskaber af permafrost fra Ilulissat',
            'Greenland 96: Glaciology: Glacial dynamics',
            'Grundvandsressourcer i et område med diskontinuert permafrost',
            'Havnebefæstelser i Arktis',
            'Ingeniørgeologiske undersøgelser ved Utoqqaat og Vandsø 5',
            'Investigation of nonlinearity of the subgrade with embedded sensors and modeling of the linear backcalculation problem',
            'Kimberlites and lamproites in Holsteinsborg, Greenland',
            'Klimamæssige påvirkninger for Nuussuaq Halvøen',
            'Klinker af ler fra Kangerlussuaq',
            'Korrelation af forundersøgelsesmetoderne ERT og CPTU',
            'Kortlægning af permafrost med georader og MEP',
            'Kulbrinteefterforskning i Vestgrønland',
            'Landskabsanalyse af et arktisk område',
            'Lime stabilization of fine-grained sediments in Ilulissat (Greenland)',
            'MEP-undersøgelse af Fossilsletten ved Kangerlussuaq, Vestgrønland',
            'Mineralogi af ler fra Søndre Strømfjord',
            'New Harbor in Kangerlussuaq, Western Greenland. Wave- and Flow Modeling for the Analysis of Ship Movements and Marina Design',
            'New habor in Kangerlussuaq, western Greenlnad - Environmental  actions analysis  and preliminary harbor design',
            'Ny havn i Kangaamiut - Forundersøgelser og forslag til en ny havn',
            'Opmåling og geologisk beskrivelse af område ved Tasersuaq',
            'Opmåling og undersøgelser af bjergarter på Disko - Del 1: Geologisk og mineralogisk undersøgelse af basalter',
            'Opmåling og undersøgelser af bjergarter på Disko - Del 2: Landmåling og fotogrammetri på Skansen',
            'Optimering af grønlandsk letklinkefremstilling',
            'Optimization of Zonge test setup',
            'Overfladenær geologi i Sisimiut kortlagt med Ground Penetrationg Radar',
            'Overførselstunneler til vandkraftværker i permafrostområder',
            'Paakitsoq Hydro Power Plant - Thermal Modelling of a Subsurface Permafrozen Tunnel in Rock',
            'Permafrost-kortlægning med den geoelektriske metode: Godhavn',
            'Preliminary assessment of geohazards related to ice-rich landforms in the Western Alps',
            'Properties of bricks produced from Greenlandic marine sediments',
            'Recommendation of components for an Autonomous Automatic Mass-balance Station (AAMS)',
            'Reflektionsseismisk og mikropalæontologiske undersøgelse af Første Fjorden, Sisimiut, Grønland',
            'Reflektionsseismisk og mikropalæontologiske undersøgelse ved vandløb i Ikertoq og Amerdloq, Sisimiut, Grønland',
            'Retningsbestemte geomagnetiske anomalier - undersøgelse af to kimberlitgange i Sisimiut',
            'Snow Distribution Statistical Modelling and UAV-borne Remote Sensing of Snow Reflectance in the Arctic',
            'Sonic Methods and Rock Mass Classification related to Tunnelling in Greenland',
            'Specialkursus i Fotogrammetrisk geologisk kortlægning',
            'Styrkeegenskaber for periglaciale fænomener: Godhavn - Forprojekt',
            'The Application of Geophysics to Characterize the Ice-rich Permafrost at the Area Close to the Airport in Ilulissat',
            'The application of EM-methods to characterization of ice-rich permafrost in the area close to the airport in Ilulissat',
            'The mechanical properties of a fine-grained saline permafrost soil (Ilulissat)',
            'Ubundne bærelagsmaterialer til vejbygning i arktiske regioner',
            'Undersøgelse af det aktive lag over permafrosten - med fokus på forskellige variables betydning for lagets vertikale udstrækning',
            'Undersøgelse af olieforurenet grund i Sisimiut, samt rensning af jorden ved kompostering',
            'Undersøgelse af permafrost i Sisimiut - vha. geologiske og geofysiske metoder',
            'Use of Greenlandic Clay as Filler in Concrete',
            'Vand i jord under arktiske forhold',
            'Vej mellem Sisimiut og Kangerlussuaq',
        ]

        # assert the publications
        self.assertEqual(len(publications), len(expected_publication_titles))

        for i, publication in enumerate(publications):
            with self.subTest(i=i):
                self.assertEqual(publication.title, expected_publication_titles[i])



    # Find all reports that is asssociated with the keyword 'Permafrost'
    def test_find_all_reports_associated_with_a_keyword(self):
        
        keyword = Keyword.objects.get(keyword='Permafrost')

        publications = Publication.objects.filter(publication_keywords=keyword)

        expected_publication_titles = [
            'Delineating Ground Ice',
            'Annual Variation of the Frost Table at Kangerlussuaq Airport, Western Greenland',
            'Geotechnical properties of permafrozen,fine-grained soil in West Greenland',
            'Elektroosmotisk dræning af lerede jordarter i danske og arktiske egne',
            'Test report for user guide',
            'Lime stabilization of fine-grained sediments in Ilulissat (Greenland)',
            'The mechanical properties of a fine-grained saline permafrost soil (Ilulissat)',
            'Development of a software application to monitor soil temperature under arctic conditions',
        ]

        # assert the publications
        self.assertEqual(len(publications), len(expected_publication_titles))

        for i, publication in enumerate(publications):
            with self.subTest(i=i):
                self.assertEqual(publication.title, expected_publication_titles[i])






 

    # ------------------- ends here ------------------- #
    # These unit tests were created to compare data relations in the old v1.6 app and verify that features such as many-to-many relationships are still functioning correctly. 
