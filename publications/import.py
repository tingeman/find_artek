from find_artek.ext_modules.pybtex.database.input import bibtex
from find_artek.ext_modules.pybtex.database import Person as pybtexPerson
from find_artek.ext_modules.pybtex.bibtex import utils as pybtex_utils     # functions for splitting strings in a tex aware fashion etc.
from io import StringIO


# Test string (emulates a file) to test module
test_string_file = StringIO(u'''
@String{SCI = "Science"}

@String{JFernandez = "Fernandez, Julio M."}
@String{HGaub = "Gaub, Hermann E."}
@String{MGautel = "Gautel, Mathias"}
@String{FOesterhelt = "Oesterhelt, Filipp"}
@String{MRief = "Rief, Matthias"}

@Article{rief97b,
  author =       MRief #" and "# MGautel #" and "# FOesterhelt
                 #" and "# JFernandez #" and "# HGaub,
  title =        "Reversible Unfolding of Individual Titin
                 Immunoglobulin Domains by {AFM}",
  journal =      SCI,
  volume =       276,
  number =       5315,
  pages =        "1109--1112",
  year =         1997,
  doi =          "10.1126/science.276.5315.1109",
  URL =          "http://www.sciencemag.org/cgi/content/abstract/276/5315/1109",
  eprint =       "http://www.sciencemag.org/cgi/reprint/276/5315/1109.pdf",
}
''')




bib_data.entries.keys()
[u'ruckenstein-diffusion', u'viktorov-metodoj', u'test-inbook', u'test-booklet']
print bib_data.entries['ruckenstein-diffusion'].fields['title']



def read_bibtex(filename=None, text=None):
    '''
    Function to populate database from bibtex file or string.
    '''
    parser = bibtex.Parser()
    if filename is not None:
        bib_data = parser.parse_file(filename)
    elif text is not None:
        bib_data = parser.parse_stream(text)
    else:
        raise ValueError('No data passed to bibtex reader')
    
    for k,e in bib_data.items():
        # 1) Check if publication is already in database
        # 2) Process persons, author, editor, supervisor
        # 3) See if persons are already in database
        # 4) Create publication entry
        
        

    
    
def create_person_from_string(self, string, check=True):
    p = pybtexPerson(string)

    pure_first_initial = utils.bibtex_first_letter(person.first()[0])
    pure_first_initial = purify_bibtex_str(pure_first_initial)
    
    last_unescaped = purify_bibtex_str(person.last()[0])

    qs = get_person(pure_first_initial=pure_first_initial,
                    last_unescaped=last_unescaped)
    if qs is None:
        myp = Person(first=p.first()[0],middle=p.middle()[0],
                        prelast=p.prelast()[0], last=p.last()[0],
                        lineage=p.lineage()[0],
                        first_initial=pure_first_initial,
                        last_unescaped=last_unescaped)
        myp.save()
    elif qs.count() > 1:
        # Handle the fact that we have more than one matches!
        pass
    else:
        # return the one matching entry...
        pass


def get_person(self, string='',person=None,
                pure_first_initial=None,
                last_unescaped=None):
    
    if pure_first_initial is None:
        if person is None:
            person = pybtexPerson(string)
        pure_first_initial = utils.bibtex_first_letter(person.first()[0])
        pure_first_initial = purify_bibtex_str(pure_first_initial)
    
    if last_unescaped is None:
        if person is None:
            person = pybtexPerson(string)
        last_unescaped = purify_bibtex_str(person.last()[0])
    
    # Query: last name matches, first name matches first letter
    q1 = Q(first_initial__iexact=first_abbr) & Q(last_unescaped__iexact=last_unescaped)
    # Query: last name matches, first name matches
    q2 = Q(first__iexact=u' '.join(person.first()[0])) & Q(last__iexact=person.last()[0])
    
    # apply query:
    queryset = Person.objects.get(q1 | q2)
    if queryset.count() >= 1:
        return queryset
    else:
        return None

