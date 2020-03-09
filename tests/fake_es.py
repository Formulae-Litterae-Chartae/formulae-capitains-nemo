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

    def build_path(self, suffix: str) -> str:
        return os.path.join(
            self.path, self.short_name + suffix
        )

    def load_request(self) -> dict:
        file_name = self.build_path('_req.json')
        with open(file_name, 'r') as f:
            return json.load(f)

    def load_response(self) -> dict:
        file_name = self.build_path('_resp.json')
        with open(file_name, 'r') as f:
            return json.load(f)

    def save_request(self, body: dict):
        file_name = self.build_path('_req.json')
        with open(file_name, 'w') as f:
            json.dump(body, f, indent=2, ensure_ascii=False)

    def save_response(self, resp: dict):
        file_name = self.build_path('_resp.json')
        for i, h in enumerate(resp['hits']['hits']):
            if 'buenden' not in h['_id']:
                resp['hits']['hits'][i]['_source']['text'] = 'some real text'
                resp['hits']['hits'][i]['_source']['lemmas'] = 'lemma text'
                resp['hits']['hits'][i]['_source']['autocomplete'] = 'autocomplete text'
                resp['hits']['hits'][i]['_source']['autocomplete_lemmas'] = 'autocomplete lemma text'
                resp['hits']['hits'][i]['_source']['regest'] = 'regest text'
                resp['hits']['hits'][i]['_source']['autocomplete_regest'] = 'autocomplete regest text'
                if 'highlight' in resp['hits']['hits'][i]:
                    resp['hits']['hits'][i]['highlight']['text'] = ['text']
                    resp['hits']['hits'][i]['highlight']['lemmas'] = ['lemma text']
                    resp['hits']['hits'][i]['highlight']['autocomplete'] = ['autocomplete text']
                    resp['hits']['hits'][i]['highlight']['autocomplete_lemmas'] = ['autocomplete lemma text']
                    resp['hits']['hits'][i]['highlight']['regest'] = ['regest text']
                    resp['hits']['hits'][i]['highlight']['autocomplete_regest'] = ['autocomplete regest text']
        with open(file_name, 'w') as f:
            json.dump(resp, f, indent=2, ensure_ascii=False)

    def save_ids(self, ids: list):
        file_name = self.build_path('_ids.json')
        with open(file_name, 'w') as f:
            json.dump(ids, f, indent=2, ensure_ascii=False)

    def load_ids(self) -> dict:
        file_name = self.build_path('_ids.json')
        with open(file_name, 'r') as f:
            return json.load(f)
