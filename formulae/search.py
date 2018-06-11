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


def query_index(index, field, query, page, per_page):
    if not current_app.elasticsearch:
        return [current_app.config], 0
    search = current_app.elasticsearch.search(
        index=index, doc_type="",
        body={'query': {'match': {field: {'query': query, 'fuzziness': 'AUTO'}}},
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
