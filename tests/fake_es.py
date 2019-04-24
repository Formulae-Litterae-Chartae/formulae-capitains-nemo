import os
import json

# Thanks to https://dev.to/jeffreymfarley/mocking-elasticsearch-5goj for this method of mocking ES


class FakeElasticsearch(object):
    def __init__(self,
                 short_name,
                 subdir,
                 endpoint='_search'):

        self.short_name = short_name
        self.path = os.path.join(
            os.path.dirname(__file__),
            "test_data",
            subdir,
            "__mocks__",
            endpoint
        )

    def buildPath(self, suffix):
        return os.path.join(
            self.path, self.short_name + suffix
        )

    def load_request(self):
        fileName = self.buildPath('_req.json')
        with open(fileName, 'r') as f:
            return json.load(f)

    def load_response(self):
        fileName = self.buildPath('_resp.json')
        with open(fileName, 'r') as f:
            return json.load(f)

    def save_request(self, body):
        fileName = self.buildPath('_req.json')
        with open(fileName, 'w') as f:
            return json.dump(body, f, indent=2)

    def save_response(self, resp):
        fileName = self.buildPath('_resp.json')
        for i, h in enumerate(resp['hits']['hits']):
            if 'buenden' not in h['_id']:
                resp['hits']['hits'][i]['_source']['text'] = 'text'
                resp['hits']['hits'][i]['_source']['lemmas'] = 'text'
                resp['hits']['hits'][i]['_source']['autocomplete'] = 'text'
                resp['hits']['hits'][i]['_source']['autocomplete_lemmas'] = 'text'
        with open(fileName, 'w') as f:
            return json.dump(resp, f, indent=2)

    def save_ids(self, ids):
        fileName = self.buildPath('_ids.json')
        with open(fileName, 'w') as f:
            return json.dump(ids, f, indent=2)

    def load_ids(self):
        fileName = self.buildPath('_ids.json')
        with open(fileName, 'r') as f:
            return json.load(f)
