#

import unittest
from publications.models import FileObject, Keyword, Person, Publication, Topic, Feature
import json
from django.conf import settings
import os 

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


   # find all appendencis associated with a publication
    def test_get_appendices_on_number2(self):
        publication = Publication.objects.get(number="17-02")
        appendices = publication.appendices.all()

        # Define the expected file name
        expected_file_name = 'reports/2017/17-02/appendix_diplomingeniør.pdf'


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
            'Dæmning i Sisimiut',
            'Deltasedimenter ved Søndre Strømfjord',
            'Design and implementation of a data logger for permafrost temperature long-term monitoring in Arctic regions',
            'Determining Snow Depth Distribution From Unmanned Aerial Vehicles and Digital Photogrammetry ',
            'Development of a geological model for Kangerluk, Disko Island, Central West Greenland',
            'Development of a software application to monitor soil temperature under arctic conditions',
            'Digital Elevation Model Reconstruction of a Glaciarized Basin Using Land-Based Structure from Motion',
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
            'Geologiske og geofysiske undersøgelser af to områder i Sisimiut',
            'Geologisk landskabsanalyse med fotogrammetri som opmålingsværktøj',
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
            'New habor in Kangerlussuaq, western Greenlnad - Environmental  actions analysis  and preliminary harbor design',
            'New Harbor in Kangerlussuaq, Western Greenland. Wave- and Flow Modeling for the Analysis of Ship Movements and Marina Design',
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
            'The application of EM-methods to characterization of ice-rich permafrost in the area close to the airport in Ilulissat',
            'The Application of Geophysics to Characterize the Ice-rich Permafrost at the Area Close to the Airport in Ilulissat',
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









    ####### TESTING FEATURES STARTS HERE #######


    # Rapport 532 skal være den rigtige rapport.
    # Titlen skal ende pa Western Alps.
    # Expects rapport with id 532 to have the title
    # "Preliminary assessment of geohazards related to ice-rich landforms in the Western Alps"
    def test_expext_report_532_to_be_the_right_report(self):
        # Get repport from 
        report = Publication.objects.filter(id="532")[0]

        # Expect the title to be "Preliminary assessment of geohazards related to ice-rich landforms in the Western Alps"
        self.assertEqual(report.title, 'Preliminary assessment of geohazards related to ice-rich landforms in the Western Alps')






    # Rapport med id 532 og publication_id = 17-05, skal pege pa feature 1818,1819 Features. 
    # Feature 1818 skal have titlen "Aiguille du plat"
    # Feature 1819 skal have titlen "Aiguille du plat"
    def test_report_532_should_have_features_1818_and_1819(self):
        
        # Get repport with id 532
        publication = Publication.objects.get(id=532)

        # Expects to features associated with the report id 1818, 1819
        # list with expected feature ids, and name
        expected_features = [
            (1818, 'Aiguille du Plat de la Selle'),
            (1819, 'Aiguille du Plat de la Selle'),
        ]

        # Get associated appendices
        associated_features = Feature.objects.filter(publications=publication)

        for feature in associated_features:
            # assert that the feature is in the expected features list
            self.assertIn((feature.id, feature.name), expected_features)




    # Test if feature with ID 1767 is associated with publication 17-01.
    def test_field_measurements_associated_with_report_17_01(self):

        # Get repport with report number 17-01
        publication = Publication.objects.get(number="17-01")

        # Get all field measurements associated with the report
        associated_field_measurement = Feature.objects.filter(publications=publication)

        # Get the field measurement with pk 1767
        associated_field_measurement = associated_field_measurement.get(pk=1767)

        # Expected description of the field measurements
        expected_field_measurement_description = [
            'Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 51,91',
        ]

        # Get associated field measurements
        self.assertTrue(associated_field_measurement.description, expected_field_measurement_description[0])


    # Test find all features associated with publication 17-01
    def test_find_all_features_associated_with_report_17_01(self):

        # Get repport with report number 17-01
        publication = Publication.objects.get(number="17-01")

        # Get all field measurements associated with the report
        associated_field_measurement = Feature.objects.filter(publications=publication)



        # Kig i den gamle app under rapporten, 17-01, saa kan du se det passer.
        # Expected description of the field measurements
        expected_field_measurement_names = [
            'Bathymetri',
            'KAN_HA_FP_1',
            'KAN_HA_FP_2',
            'KAN_HA_FP_3',
            'KAN_HA_SH_1',
            'KAN_HA_SH_12',
            'KAN_HA_SH_13',
            'KAN_HA_SH_14',
            'KAN_HA_SH_15',
            'KAN_HA_SH_16',
            'KAN_HA_SH_17',
            'KAN_HA_SH_18',
            'KAN_HA_SH_19',
            'KAN_HA_SH_20',
            'KAN_HA_SH_21',
            'KAN_HA_SH_2',
            'KAN_HA_SH_23',
            'KAN_HA_SH_24',
            'KAN_HA_SH_25',
            'KAN_HA_SH_26',
            'KAN_HA_SH_27',
            'KAN_HA_SH_28',
            'KAN_HA_SH_29',
            'KAN_HA_SH_30',
            'KAN_G_SH_1',
            'KAN_HB_SH_1',
            'KAN_HA_SH_3',
            'KAN_HB_SH_3',
            'KAN_HB_SH_2',
            'KAN_HB_SH_4',
            'KAN_HB_SH_5',
            'KAN_HB_SH_6',
            'KAN_HA_SH_31',
            'KAN_HA_SH_32',
            'KAN_HB_SH_7',
            'KAN_HB_SH_8',
            'KAN_HB_SH_9',
            'KAN_HA_SH_5',
            'KAN_HB_SH_10',
            'KAN_HB_SH_11',
            'KAN_HB_SH_12',
            'KAN_HB_SH_13',
            'KAN_HB_SH_14',
            'KAN_HB_SH_15',
            'KAN_G_SH_2',
            'KAN_FP_3',
            'KAN_FP_3',
            'KAN_HA_SH_6',
            'KAN_HA_SH_7',
            'KAN_HA_SH_8',
            'KAN_HA_SH_9',
            'KAN_HA_SH_11',
            'Water level',
        ]

        expected_field_measurement_description = [
            "Bathymetric measurements with echo sounder. Reference UTM 22 N gr96 Mean Sea Level",
            "Rock sample from gneiss, <20 cm from surface. UCS = 57 MPa, Brazilian = 7,6 Mpa",
            "Rock sample from gneiss, <20 cm from surface. UCS = 80 MPa, Brazilian = 6,1 Mpa",
            "Rock sample from dolerite. UCS = 179 MPa, Brazilian = 23,6 Mpa",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 51,91",
            "Schmidt hammer on grinded surface (gneiss), angle = -52, HR = 40,55",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 47,32",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 51,75",
            "Schmidt hammer on grinded surface (gneiss), angle = -70, HR = 53,30",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 49,60",
            "Schmidt hammer on grinded surface (gneiss), angle = -53, HR = 45,50",
            "Schmidt hammer on grinded surface (gneiss), angle = -55, HR = 51,00",
            "Schmidt hammer on grinded surface (gneiss), angle = -46, HR = 50,00",
            "Schmidt hammer on grinded surface (gneiss), angle = -70, HR = 30,00",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 48,25",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 44,25",
            "Schmidt hammer on grinded surface (gneiss), angle = -45, HR = 51,86",
            "Schmidt hammer on grinded surface (gneiss), angle = -60, HR = 49,52",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 50,47",
            "Schmidt hammer on grinded surface (gneiss), angle = -70, HR = 45,74",
            "Schmidt hammer on grinded surface (gneiss), angle = -75, HR = 51,30",
            "Schmidt hammer on grinded surface (gneiss), angle = -60, HR = 48,20",
            "Schmidt hammer on grinded surface (gneiss), angle = -70, HR = 47,90",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 47,32",
            "Schmidt hammer on grinded surface (dolerite), angle = -90, HR = 54,32",
            "Schmidt hammer on grinded surface (gneiss), angle = -70, HR = 47,58",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 47,80",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 49,63",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 39,92",
            "Schmidt hammer on grinded surface (gneiss), angle = -65, HR = 46,10",
            "Schmidt hammer on grinded surface (gneiss), angle = -60, HR = 40,14",
            "Schmidt hammer on grinded surface (gneiss), angle = -60, HR = 50,25",
            "Schmidt hammer on grinded surface (gneiss), angle = -70, HR = 49,55",
            "Schmidt hammer on grinded surface (gneiss), angle = -70, HR = 48,05",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 50,79",
            "Schmidt hammer on grinded surface (gneiss), angle = -80, HR = 44,65",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 47,95",
            "Schmidt hammer on grinded surface (gneiss), angle = -70, HR = 43,20",
            "Schmidt hammer on grinded surface (gneiss), angle = -75, HR = 51,74",
            "Schmidt hammer on grinded surface (gneiss), angle = -75, HR = 47,22",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 46,40",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 49,10",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 55,80",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 50,30",
            "Schmidt hammer on grinded surface (dolerite), angle = -35, HR = 58,50",
            "Schmidt hammer on grinded surface (dolerite), angle = -60, HR = 46,6",
            "Schmidt hammer on grinded surface (dolerite), angle = 0, HR = 57,85",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 47,15",
            "Schmidt hammer on grinded surface (gneiss), angle = -90, HR = 48,60",
            "Schmidt hammer on grinded surface (gneiss), angle = -80, HR = 48,11",
            "Schmidt hammer on grinded surface (gneiss), angle = -50, HR = 38,83",
            "Schmidt hammer on grinded surface (gneiss), angle = -50, HR = 46,47",
            "Water level measured each 5 min. from 3/10/16 to 14/10/16. Reference: Mean Sea Level.",
        ]

        expected_field_measurement_pk = [
            1763,
            1764,
            1765,
            1766,
            1767,
            1768,
            1769,
            1770,
            1771,
            1772,
            1773,
            1774,
            1775,
            1776,
            1777,
            1778,
            1779,
            1780,
            1781,
            1782,
            1783,
            1784,
            1785,
            1786,
            1787,
            1788,
            1789,
            1790,
            1791,
            1792,
            1793,
            1794,
            1795,
            1796,
            1797,
            1798,
            1799,
            1800,
            1801,
            1802,
            1803,
            1804,
            1805,
            1806,
            1807,
            1808,
            1809,
            1810,
            1811,
            1812,
            1813,
            1814,
            1815,
        ]
        

        # loop though associated_field_measurement
        for i in range(len(associated_field_measurement)):
            # check if the name is correct
            self.assertEqual(
                associated_field_measurement[i].name,
                expected_field_measurement_names[i],
                "The name of the field measurement is not correct",
            )
            # check if the description is correct
            self.assertEqual(
                associated_field_measurement[i].description,
                expected_field_measurement_description[i],
                "The description of the field measurement is not correct",
            )
            # check if the primary key is correct
            self.assertEqual(
                associated_field_measurement[i].pk,
                expected_field_measurement_pk[i],
                "The primary key of the field measurement is not correct",
            )
    # q: assert true for the following arrays
    # expected_field_measurement_names
    # expected_field_measurement_description
    # expected_field_measurement_pk
    
    
    
    def test_get_related_publications(self):


        #
        feature = Feature.objects.get(pk=1352)
        print("feature.pk: ", feature.pk)
        print("feature.name: ", feature.name)
        print("feature.description: ", feature.description)
        print("feature.publications: ", feature.publications)

        # publication = Publication.objects.get(pk=1352)
        # # Get the related publications
        # related_publications = feature.get_related_publications()
        related_publications = feature.publications.all()

        # esxpected related publications titles
        expected_related_publications_titles = [
            'Screening for Greenlandic bacteria capable of inhibiting pathogenic bacteria',
        ]

        # assert 
        for i in range(len(related_publications)):
            self.assertEqual(
                related_publications[i].title,
                expected_related_publications_titles[i],
                "The title of the publication is not correct",
            )

     


    ####### TESTING FEATURES ENDS HERE #######   



# Test FileObject
    def test_get_file_foreach_publication(self):

        # import json file
        json_file_path = os.path.join(settings.BASE_DIR, 'management', 'datatransfer_script', 'publications_fileobject_assoc.json')
        with open(json_file_path) as json_file:
            data = json.load(json_file)


        publications = Publication.objects.all()
        for d in data:
            
            asserted_filename = d['filename']

            if asserted_filename is None:
                # expect an error when trying to get the file
                publication = publications.get(pk=d['id'])

                # Here, the with self.assertRaises(AttributeError): block will pass if an AttributeError is thrown within the block. If no AttributeError is thrown, then the test will fail.
                with self.assertRaises(AttributeError):
                    filename = publication.file.filename()

                # if publication.file is not None:
                
                #     # Here, the with self.assertRaises(AttributeError): block will pass if an AttributeError is thrown within the block. If no AttributeError is thrown, then the test will fail.
                #     with self.assertRaises(AttributeError):
                #         filename = publication.file.filename()
                # else:
                #     print (publication.file)

                
            else :
                publication = publications.get(pk=d['id'])
                # get the fileobject
                filename = publication.file.filename()              
                # assert that that file name are the same
                self.assertEqual(filename, asserted_filename, "The filename is correct")





   
    
# Test FileObject




# Tjek feature pa 1818,1819. og se om deres titler er som forventet. (Aiguille du plat)
# Feature 1818 skal have titlen "Aiguille du plat"


    # ------------------- ends here ------------------- #
    # These unit tests were created to compare data relations in the old v1.6 app and verify that features such as many-to-many relationships are still functioning correctly. 

# Write image function check if image is objectship association is correct











# test if api works 
