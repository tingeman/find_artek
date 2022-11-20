from io import StringIO
from pybtex.database.input import bibtex


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


parser = bibtex.Parser()
bib_string = parser.parse_stream(string_file)
bib_file = parser.parse_file('TIN_Publications.bib')