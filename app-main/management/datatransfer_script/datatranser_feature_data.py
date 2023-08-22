import json
# from models_that_looks_like_old_models import Feature
from publications.models import Feature
import datetime
import os


def run():

    # print in green text "Loading json file"
    print("\033[92m" + "Loading json file" + "\033[0m")

    # Load exported features from file
    with open (os.path.dirname(os.path.realpath(__file__)) + '/datatransfer_feature_data.json', 'r') as f:  
        exported_features = json.load(f)

    # print in green text "Creating new Feature objects"
    print("\033[92m" + "Creating new Feature objects" + "\033[0m")

    # Loop through exported features and create new Feature objects
    for exported_feature in exported_features:
        # Print the feature name, if the name is empty print the id
        if exported_feature['fields']['name'] == '':
            print("id " + str(exported_feature['pk']))
        else:
            print("name " + str(exported_feature['fields']['name']))

        # q: does this create a new Feature entry?
        # a: yes, it does
        new_feature = Feature.objects.create(

            # Add fields
            id = exported_feature['pk'],
            created_date = exported_feature['fields']['created_date'],
            modified_date = exported_feature['fields']['modified_date'],


            name=exported_feature['fields']['name'],
            type=exported_feature['fields']['type'],
            area=exported_feature['fields']['area'],

            
            date=datetime.datetime.strptime(exported_feature['fields']['date'] if exported_feature['fields']['date'] != None else '2022-03-13', "%Y-%m-%d").date(),
            direction=exported_feature['fields']['direction'],
            description=exported_feature['fields']['description'],
            comment=exported_feature['fields']['comment'],
            pos_quality=exported_feature['fields']['pos_quality'],
            quality=exported_feature['fields']['quality'],
            points=exported_feature['fields']['points'],
            lines=exported_feature['fields']['lines'],
            polys=exported_feature['fields']['polys'],
        )
        
        # Add ManyToManyField relationships
        for publication_id in exported_feature['fields']['publications']:
            new_feature.publications.add(publication_id) 

        for url_id in exported_feature['fields']['URLs']:
            new_feature.URLs.add(url_id)

        for file_id in exported_feature['fields']['files']:
            new_feature.files.add(file_id)

        for image_id in exported_feature['fields']['images']:
            new_feature.images.add(image_id)



        # Save new Feature object
        new_feature.save()








if __name__ == '__main__':
    run()
