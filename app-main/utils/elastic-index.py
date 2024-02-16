# print("Hello from myscript.py")


def run():
    from elasticsearch import Elasticsearch
    from dotenv import load_dotenv
    import os
    dotenv_path = '/usr/src/project/.devcontainer/.env'
    load_dotenv(dotenv_path=dotenv_path)



    # Connect to the Elasticsearch server with authentication
    es = Elasticsearch(
        "http://find-artek-elasticsearch-service:9200",
        http_auth=('elastic', os.getenv('ELASTIC_PASSWORD'))  # Replace with your actual password
    )


    # Index documents
    es.index(index="texts", id=1, document={"content": "yada nada nana"})
    es.index(index="texts", id=2, document={"content": "yada pada lana"})
    es.index(index="texts", id=3, document={"content": "ayada bada sana"})



if __name__ == '__main__':
    run()
