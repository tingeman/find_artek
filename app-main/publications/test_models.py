"""Relations of a report and of a person (plan "test coverage" T6).

What the removed old ``publications/tests.py`` meant to check against the production copy,
now on made-up fixtures: a report's authors, supervisors and editors and their order, its
appendices, keywords, topics and features, and the reports of a person
(``Person.sorted_authorships`` / ``sorted_supervisorships`` / ``sorted_editorships``).
"""
import datetime

from django.test import TestCase

from publications.models import (
    Appendenciesship, Authorship, Editorship, Feature, FileObject, Keyword, Person, Publication,
    Supervisorship, Topic,
)
from publications.test_factories import make_person, make_report, report_type


def numbers(publications):
    return [pub.number for pub in publications]


def lasts(persons):
    return [person.last for person in persons]


class ReportPersonsTests(TestCase):
    """Authors, supervisors and editors of a report, in the order of their index."""

    @classmethod
    def setUpTestData(cls):
        cls.pubtype = report_type()
        cls.a, cls.b, cls.c = (make_person('Ann', 'Alpha'), make_person('Ben', 'Beta'),
                               make_person('Cat', 'Gamma'))
        cls.pub = make_report(cls.pubtype, '99-01', verified=True, confidential=False)
        # Created out of order: the index, not the insertion order or the name, decides.
        for person, index in ((cls.b, 2), (cls.c, 0), (cls.a, 1)):
            Authorship.objects.create(publication=cls.pub, person=person, author_id=index)
        for person, index in ((cls.a, 1), (cls.b, 0)):
            Supervisorship.objects.create(publication=cls.pub, person=person,
                                          supervisor_id=index)
        for person, index in ((cls.c, 1), (cls.b, 0)):
            Editorship.objects.create(publication=cls.pub, person=person, editor_id=index)
        # Another report with other persons: must not show up on cls.pub.
        cls.other = make_report(cls.pubtype, '99-02', verified=True, confidential=False,
                                authors=[make_person('Dan', 'Delta')],
                                supervisors=[make_person('Eve', 'Epsilon')])

    def test_authors(self):
        self.assertEqual(lasts(self.pub.sorted_authors()), ['Gamma', 'Alpha', 'Beta'])
        self.assertEqual(set(lasts(self.pub.authors.all())), {'Alpha', 'Beta', 'Gamma'})

    def test_authorships(self):
        authorships = list(self.pub.sorted_authorships())
        self.assertEqual([a.author_id for a in authorships], [0, 1, 2])
        self.assertEqual(lasts(a.person for a in authorships), ['Gamma', 'Alpha', 'Beta'])

    def test_supervisors(self):
        self.assertEqual(lasts(self.pub.sorted_supervisors()), ['Beta', 'Alpha'])
        self.assertEqual(lasts(s.person for s in self.pub.sorted_supervisorships()),
                         ['Beta', 'Alpha'])

    def test_editors(self):
        self.assertEqual(lasts(self.pub.sorted_editors()), ['Beta', 'Gamma'])
        self.assertEqual(lasts(e.person for e in self.pub.sorted_editorships()),
                         ['Beta', 'Gamma'])

    def test_factory_order(self):
        """make_report lists the persons in the order given."""
        x, y = make_person('Xen', 'Zulu'), make_person('Yul', 'Able')
        pub = make_report(self.pubtype, '99-03', verified=True, confidential=False,
                          authors=[x, y], supervisors=[y, x], editors=[x])
        self.assertEqual(lasts(pub.sorted_authors()), ['Zulu', 'Able'])
        self.assertEqual(lasts(pub.sorted_supervisors()), ['Able', 'Zulu'])
        self.assertEqual(lasts(pub.sorted_editors()), ['Zulu'])

    def test_reverse_relations_of_a_person(self):
        self.assertEqual(numbers(self.a.publication_author.all()), ['99-01'])
        self.assertEqual(numbers(self.a.publication_supervisor.all()), ['99-01'])
        self.assertEqual(numbers(self.a.publication_editor.all()), [])
        self.assertEqual(numbers(self.c.publication_editor.all()), ['99-01'])

    def test_report_without_persons(self):
        pub = make_report(self.pubtype, '99-04', verified=True, confidential=False)
        self.assertEqual(list(pub.sorted_authors()), [])
        self.assertEqual(list(pub.sorted_supervisors()), [])
        self.assertEqual(list(pub.sorted_editors()), [])

    def test_deleting_a_report_keeps_the_persons(self):
        self.other.delete()
        self.assertTrue(Person.objects.filter(last='Delta').exists())
        self.assertFalse(Authorship.objects.filter(person__last='Delta').exists())
        self.assertFalse(Supervisorship.objects.filter(person__last='Epsilon').exists())

    def test_deleting_a_person_removes_only_their_roles(self):
        self.a.delete()
        self.assertEqual(lasts(self.pub.sorted_authors()), ['Gamma', 'Beta'])
        self.assertEqual(lasts(self.pub.sorted_supervisors()), ['Beta'])
        self.assertTrue(Publication.objects.filter(pk=self.pub.pk).exists())


class PersonSortedReportsTests(TestCase):
    """Person.sorted_authorships / sorted_supervisorships / sorted_editorships: the reports of
    a person in that role, newest year first, then report number descending, then title.

    They used the related names ``publication_authors`` / ``..._supervisors`` /
    ``..._editors``, which don't exist (the relations are ``publication_author`` etc.), so
    every call raised AttributeError. Nothing calls them yet (the templates use the methods
    of Publication with the same names)."""

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.person = make_person('Pat', 'Person')
        other = make_person('Oli', 'Other')

        def report(number, year, title=None, **roles):
            return make_report(pubtype, number, verified=True, confidential=False, year=year,
                               title=title, **roles)

        mine = [cls.person]
        # Years and numbers out of order; two reports of the same year and number differ
        # only by title.
        report('05-02', 2005, authors=mine, supervisors=[other])
        report('12-01', 2012, authors=[other, cls.person], supervisors=mine, editors=mine)
        report('05-10', 2005, authors=mine)
        report('98-01', 1998, title='B title', authors=mine, editors=mine)
        report('98-01', 1998, title='A title', authors=mine)
        report('20-01', 2020, authors=[other], supervisors=[other])   # not theirs
        report('99-01', 1999, supervisors=mine)

    def rows(self, queryset):
        return [(pub.year, pub.number, pub.title) for pub in queryset]

    def test_sorted_authorships(self):
        self.assertEqual(self.rows(self.person.sorted_authorships()), [
            (2012, '12-01', 'Report 12-01'),
            (2005, '05-10', 'Report 05-10'),
            (2005, '05-02', 'Report 05-02'),
            (1998, '98-01', 'A title'),
            (1998, '98-01', 'B title'),
        ])

    def test_sorted_supervisorships(self):
        self.assertEqual(self.rows(self.person.sorted_supervisorships()), [
            (2012, '12-01', 'Report 12-01'),
            (1999, '99-01', 'Report 99-01'),
        ])

    def test_sorted_editorships(self):
        self.assertEqual(self.rows(self.person.sorted_editorships()), [
            (2012, '12-01', 'Report 12-01'),
            (1998, '98-01', 'B title'),
        ])

    def test_person_without_reports(self):
        nobody = make_person('No', 'Body')
        self.assertEqual(list(nobody.sorted_authorships()), [])
        self.assertEqual(list(nobody.sorted_supervisorships()), [])
        self.assertEqual(list(nobody.sorted_editorships()), [])


class ReportAppendicesKeywordsTopicsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.pub = make_report(pubtype, '99-01', verified=True, confidential=False,
                              topics=['Geotechnics', 'Hydrology'],
                              keywords=['permafrost', 'drilling'])
        cls.other = make_report(pubtype, '99-02', verified=True, confidential=False,
                                topics=['Geotechnics'], keywords=['permafrost', 'ice'])
        # Only the names are stored; no file is opened.
        cls.app1 = FileObject.objects.create(file='reports/99-01/appendix_a.pdf',
                                             description='Appendix A')
        cls.app2 = FileObject.objects.create(file='reports/99-01/appendix_b.zip')
        for fileobject in (cls.app1, cls.app2):
            Appendenciesship.objects.create(publication=cls.pub, fileobject=fileobject)

    def test_appendices(self):
        self.assertEqual(sorted(f.filename() for f in self.pub.appendices.all()),
                         ['appendix_a.pdf', 'appendix_b.zip'])
        self.assertEqual(list(self.other.appendices.all()), [])
        self.assertEqual(numbers(self.app1.publication_appendices.all()), ['99-01'])

    def test_main_file_is_not_an_appendix(self):
        main = FileObject.objects.create(file='reports/99-02/report.pdf')
        self.other.file = main
        self.other.save()
        self.assertEqual(list(self.other.appendices.all()), [])
        self.assertEqual(Publication.objects.get(file=main), self.other)

    def test_deleting_a_report_removes_its_appendix_links(self):
        self.pub.delete()
        self.assertFalse(Appendenciesship.objects.exists())
        self.assertEqual(FileObject.objects.count(), 2)

    def test_keywords(self):
        self.assertEqual(sorted(str(k) for k in self.pub.publication_keywords.all()),
                         ['drilling', 'permafrost'])
        # One Keyword row shared by both reports.
        permafrost = Keyword.objects.get(keyword='permafrost')
        self.assertEqual(sorted(numbers(permafrost.publication_set.all())), ['99-01', '99-02'])
        self.assertEqual(Keyword.objects.count(), 3)

    def test_topics(self):
        self.assertEqual(sorted(str(t) for t in self.pub.publication_topics.all()),
                         ['Geotechnics', 'Hydrology'])
        geotechnics = Topic.objects.get(topic='Geotechnics')
        self.assertEqual(sorted(numbers(geotechnics.publication_set.all())), ['99-01', '99-02'])
        self.assertEqual(numbers(Topic.objects.get(topic='Hydrology').publication_set.all()),
                         ['99-01'])

    def test_deleting_a_report_keeps_keywords_and_topics(self):
        self.pub.delete()
        self.assertEqual(Keyword.objects.count(), 3)
        self.assertEqual(Topic.objects.count(), 2)
        self.assertEqual(list(self.other.publication_keywords.order_by('keyword')
                              .values_list('keyword', flat=True)), ['ice', 'permafrost'])


class ReportFeaturesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        pubtype = report_type()
        cls.pub = make_report(pubtype, '99-01', verified=True, confidential=False)
        cls.other = make_report(pubtype, '99-02', verified=True, confidential=False)
        date = datetime.date(1999, 7, 1)
        cls.borehole = Feature.objects.create(name='BH-1', type=Feature.BOREHOLE, date=date)
        cls.photo = Feature.objects.create(name='Photo-1', type=Feature.PHOTO, date=date)
        cls.borehole.publications.add(cls.pub)
        cls.photo.publications.add(cls.pub, cls.other)

    def test_features_of_a_report(self):
        self.assertEqual(sorted(f.name for f in self.pub.feature_set.all()), ['BH-1', 'Photo-1'])
        self.assertEqual([f.name for f in self.other.feature_set.all()], ['Photo-1'])

    def test_reports_of_a_feature(self):
        self.assertEqual(sorted(numbers(self.photo.publications.all())), ['99-01', '99-02'])
        self.assertEqual(self.borehole.type, 'BOREHOLE')
        self.assertIn(self.borehole.type, Feature.feature_type_list())

    def test_deleting_a_report_keeps_the_features(self):
        self.pub.delete()
        self.assertEqual(Feature.objects.count(), 2)
        self.assertEqual(list(self.borehole.publications.all()), [])
        self.assertEqual(numbers(self.photo.publications.all()), ['99-02'])


class ReportKeyTests(TestCase):
    """Publication.create_key: ``<last name of the first author>(<year>)`` for student reports,
    with a letter added when the key is taken; ``pk:<pk>`` (not saved) without authors."""

    @classmethod
    def setUpTestData(cls):
        cls.pubtype = report_type()
        cls.first = make_person('Kim', 'Keyholder')
        cls.second = make_person('Lee', 'Later')

    def test_key_from_first_author_and_year(self):
        pub = make_report(self.pubtype, '99-01', verified=True, confidential=False,
                          authors=[self.first, self.second])
        pub.create_key()
        pub.refresh_from_db()
        self.assertEqual(pub.key, 'Keyholder(1999)')

    def test_taken_key_gets_a_letter(self):
        keys = []
        for number in ('99-01', '99-02', '99-03'):
            pub = make_report(self.pubtype, number, verified=True, confidential=False,
                              authors=[self.first])
            pub.create_key()
            keys.append(Publication.objects.get(pk=pub.pk).key)
        self.assertEqual(keys, ['Keyholder(1999)', 'Keyholder(1999a)', 'Keyholder(1999b)'])

    def test_report_without_authors_keeps_an_empty_key(self):
        pub = make_report(self.pubtype, '99-01', verified=True, confidential=False)
        pub.create_key()
        pub.refresh_from_db()
        self.assertEqual(pub.key, '')
        self.assertEqual(str(pub), f'pk:{pub.pk}')


class PersonNameTests(TestCase):

    def test_name_argument_is_split_into_parts(self):
        person = Person(name='van der Berg, Jr, Anna Maria')
        self.assertEqual((person.first, person.middle, person.prelast, person.last,
                          person.lineage), ('Anna', 'Maria', 'van der', 'Berg', 'Jr'))
        self.assertEqual(person.get_full_name(), 'Anna Maria van der Berg, Jr')
        self.assertEqual((person.first_relaxed, person.last_relaxed), ('a', 'berg'))

    def test_first_last_order(self):
        person = Person(name='Søren Ærø')
        self.assertEqual((person.first, person.last), ('Søren', 'Ærø'))
        person.save()
        self.assertEqual(str(person), f'Søren Ærø [pk:{person.pk}]')
