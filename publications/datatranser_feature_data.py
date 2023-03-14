import json
from .models import Feature
import datetime


def run():



    # Load exported features from file
    with open('/usr/src/app/find_artek/publications/datatransfer_feature_data.json', 'r') as f:
        exported_features = json.load(f)

    # Loop through exported features and create new Feature objects
    for exported_feature in exported_features:
        new_feature = Feature.objects.create(

            # Add fields
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
        for url_id in exported_feature['fields']['URLs']:
            new_feature.URLs.add(url_id)
        for file_id in exported_feature['fields']['files']:
            new_feature.files.add(file_id)
        for image_id in exported_feature['fields']['images']:
            new_feature.images.add(image_id)
        for publication_id in exported_feature['fields']['publications']:
            new_feature.publications.add(publication_id)
        
        # Save new Feature object
        new_feature.save()








if __name__ == '__main__':
    run()
