from flask import current_app, Markup


def add_to_index(index, model):
    if not current_app.elasticsearch:
        return
    payload = {}
    for field in model.__searchable__:
        payload[field] = getattr(model, field)
    current_app.elasticsearch.index(index=index, doc_type=index, id=model.id, body=payload)


def remove_from_index(index, model):
    if not current_app.elasticsearch:
        return
    current_app.elasticsearch.delete(index=index, doc_type=index, id=model.id)


def query_index(index, field, query, page, per_page, fuzzy_search, phrase):
    if not current_app.elasticsearch:
        return [current_app.config], 0
    if field == 'lemmas' or fuzzy_search == 'n':
        fuzz = '0'
    else:
        fuzz = 'AUTO'
    if phrase:
        search = current_app.elasticsearch.search(
        index="", doc_type="",
        body={'query': {'match_phrase': {field: {'query': query, "slop": 4}}},
              "sort": 'urn',
              'from': (page - 1) * per_page, 'size': per_page,
              'highlight':
                  {'fields':
                       {field: {}
                        },
                   'pre_tags': ["<strong>"],
                   'post_tags': ["</strong>"],
                   'order': 'score'
                   },
              }
    )
    else:
        search = current_app.elasticsearch.search(
        index="", doc_type="",
        body={'query': {'match': {field: {'query': query, 'fuzziness': fuzz}}},
              "sort": 'urn',
              'from': (page - 1) * per_page, 'size': per_page,
              'highlight':
                  {'fields':
                       {field: {}
                        },
                   'pre_tags': ["<strong>"],
                   'post_tags': ["</strong>"],
                   'order': 'score'
                   },
              }
    )
    ids = [{'id': hit['_id'], 'info': hit['_source'], 'sents': [Markup(x) for x in hit['highlight'][field]]} for hit in search['hits']['hits']]
    return ids, search['hits']['total']


def advanced_query_index(index, field, query, page, per_page, fuzzy_search, phrase):
    if not current_app.elasticsearch:
        return [current_app.config], 0
    if field == 'lemmas' or fuzzy_search == 'n':
        fuzz = '0'
    else:
        fuzz = 'AUTO'
    if phrase:
        search = current_app.elasticsearch.search(
        index="", doc_type="",
        body={'query': {'match_phrase': {field: {'query': query, "slop": 4}}},
              "sort": 'urn',
              'from': (page - 1) * per_page, 'size': per_page,
              'highlight':
                  {'fields':
                       {field: {}
                        },
                   'pre_tags': ["<strong>"],
                   'post_tags': ["</strong>"],
                   'order': 'score'
                   },
              }
    )
    else:
        search = current_app.elasticsearch.search(
        index="", doc_type="",
        body={'query': {'match': {field: {'query': query, 'fuzziness': fuzz}}},
              "sort": 'urn',
              'from': (page - 1) * per_page, 'size': per_page,
              'highlight':
                  {'fields':
                       {field: {}
                        },
                   'pre_tags': ["<strong>"],
                   'post_tags': ["</strong>"],
                   'order': 'score'
                   },
              }
    )
    ids = [{'id': hit['_id'], 'info': hit['_source'], 'sents': [Markup(x) for x in hit['highlight'][field]]} for hit in search['hits']['hits']]
    return ids, search['hits']['total']
