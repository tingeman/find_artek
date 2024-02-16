
source '/usr/src/project/.devcontainer/.env'

# curl -X POST "http://find-artek-elasticsearch-service:9200/_security/service/elastic/kibana_system/_create_token" \
# -H "Content-Type: application/json" \
# -u ${ELASTIC_USERNAME}:${ELASTIC_PASSWORD} \
# -d '{
#   "name": "kibana-service-token"
# }'



curl -X POST "http://find-artek-elasticsearch-service:9200/_security/service/elastic/kibana_system/credential/token/kibana-access-token" \
-H "Content-Type: application/json" \
-u ${ELASTIC_USERNAME}:${ELASTIC_PASSWORD} \
-d '{}'




    # # Connect to the Elasticsearch server with authentication
    # es = Elasticsearch(
    #     "http://find-artek-elasticsearch-service:9200",
    #     http_auth=('elastic', os.getenv('ELASTIC_PASSWORD'))  # Replace with your actual password
    # )
