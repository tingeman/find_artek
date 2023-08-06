from publications.models import Publication
import os
# pub_list = Publication.objects.all()
# pub_list = pub_list.extra(select={'year_int': 'CAST(year AS INTEGER)'}).extra(order_by=['-year_int', '-number'])
# for p in publist:
#     print p.year

import json

def run():
    # delete publications.txt if it exists
    if os.path.exists('publications_fileobject_assoc.json'):
        os.remove('publications_fileobject_assoc.json')

    # print info from all publications
    file_object_assoc = []
    publications = Publication.objects.all()
    publications = publications.extra(select={'year_int': 'CAST(year AS INTEGER)'}).extra(order_by=['-year_int', '-number'])

    for p in publications:
        # put all the file objects file names into a list
        file_names = []

        # print p.file
        # print p.id
        if p.file is not None:
            file_object_assoc.append({"id": str(p.id), "filename": p.file.filename()})
        else:
            file_object_assoc.append({"id": str(p.id), "filename": None})


# [
#     {
#         "publication": {
#             "id": "1",
#             "title": "The Lord of the Rings"
#         }
#     }
# ]

    # convert file_object_assoc to json and write to file
    with open('publications_fileobject_assoc.json', 'w') as f:
        json.dump(file_object_assoc, f)


    # file_object_assoc.append({str(p.id): file_names})


    #     for f in p.file:
            
    #         file_names.append(f.file.filename())
        
    #     # Create an object like the following: p.id: [file_names]
    #     # e.g. 1: ['file1.pdf', 'file2.pdf']

    #     file_object_assoc.append({str(p.id): file_names})

    # # print the publication info
    # print(file_object_assoc)

    # # convert file_object_assoc to json and write to file
    # with open('publications_fileobject_assoc.json', 'w') as f:
    #     json.dump(file_object_assoc, f)

    
    



            

                


        # print p.year + ' ' + p.number
        # if p.year is not at year in this format 'YYYY' then create it based on the number. e.g 96-01 -> 1996 or 02-07 -> 2002
        # if len(p.year) != 4:
        #     year = p.number.split('-')[0]
        #     p.year = '19' + year
        #     p.save()
        #     print 'changed year to ' + p.year



        # print all properties of file








if __name__ == '__main__':
    run()