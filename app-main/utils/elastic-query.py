from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import os
import argparse
from elasticsearch import Elasticsearch
dotenv_path = '/usr/src/project/.devcontainer/.env'
load_dotenv(dotenv_path=dotenv_path)

def run():

    search('ayada')



    print("Hello from myscript.py")



def search(keyword):
    # Connect to the Elasticsearch server with authentication
    es = Elasticsearch(
        "http://find-artek-elasticsearch-service:9200",
        http_auth=('elastic', os.getenv('ELASTIC_PASSWORD'))  # Replace with your actual password
    )


    query = {"query": {"match": {"content": keyword}}}
    result = es.search(index="texts", body=query)
    hits = result['hits']['hits']
    if hits:
        for hit in hits:
            print(f"{keyword} is found in text{hit['_id']}")
    else:
        print(f"{keyword} is not found")




if __name__ == "__main__":
    search('pada')
    # parser = argparse.ArgumentParser(description='Search for keywords in Elasticsearch')
    # parser.add_argument('--keyword', required=True, help='Keyword to search for')
    # args = parser.parse_args()
    # search(args.keyword)