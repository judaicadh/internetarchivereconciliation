from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from operator import itemgetter
from fuzzywuzzy import fuzz
import requests

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Internet Archive API URL
INTERNET_ARCHIVE_SEARCH_URL = 'https://archive.org/advancedsearch.php'
INTERNET_ARCHIVE_ITEM_URL = 'https://archive.org/details/{identifier}'

# Helper function to construct the Internet Archive URL
def make_uri(identifier):
    uri = INTERNET_ARCHIVE_ITEM_URL.format(identifier=identifier)
    app.logger.debug(f"Constructed URI: {uri}")
    return uri

# Metadata for the reconciliation service
metadata = {
    "name": "Internet Archive Reconciliation Service",
    "identifierSpace": "https://archive.org/",
    "schemaSpace": "http://schema.org/",
    "view": {
        "url": "https://archive.org/details/{{id}}"
    }
}

def search_internet_archive(query):
    params = {
        'q': query,
        'fl[]': 'identifier,title,creator,year,mediatype',
        'rows': 5,
        'output': 'json'
    }
    try:
        response = requests.get(INTERNET_ARCHIVE_SEARCH_URL, params=params)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
        app.logger.debug(f"Request URL: {response.url}")
        app.logger.debug(f"Response Status Code: {response.status_code}")
        app.logger.debug(f"Response Content: {response.text}")
        return response.json().get('response', {}).get('docs', [])
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error querying Internet Archive: {e}")
        return []

def format_results(docs, query):
    results = []
    for doc in docs:
        name = doc.get('title', 'No Title')
        identifier = doc['identifier']
        fast_uri = make_uri(identifier)
        score = fuzz.token_sort_ratio(query, name)
        resource = {
            "id": identifier,  # Use the identifier here
            "name": name,
            "score": score,
            "match": query == name  # Adjust matching logic as needed
        }
        app.logger.debug(f"Resource: {resource}")
        results.append(resource)
    sorted_out = sorted(results, key=itemgetter('score'), reverse=True)
    return sorted_out[:3]

@app.route("/reconcile", methods=['POST', 'GET'])
def reconcile():
    try:
        query = request.form.get('query')
        if query is None:
            query = request.args.get('query')
        if query:
            if query.startswith("{"):
                query = json.loads(query)['query']
            results = search_internet_archive(query)
            formatted_results = format_results(results, query)
            return jsonify({"result": formatted_results})
        
        queries = request.form.get('queries')
        if queries:
            queries = json.loads(queries)
            results = {}
            for key, query in queries.items():
                data = search_internet_archive(query['query'])
                formatted_results = format_results(data, query['query'])
                results[key] = {"result": formatted_results}
            return jsonify(results)
        
        return jsonify(metadata)
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    from optparse import OptionParser
    oparser = OptionParser()
    oparser.add_option('-d', '--debug', action='store_true', default=False)
    opts, args = oparser.parse_args()
    app.debug = opts.debug
    app.run(host='0.0.0.0', port=9000)