from flask import current_app, Markup
# This import is only needed for capturing the ES request. I could perhaps comment it out when it is not needed.
from tests.fake_es import FakeElasticsearch


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
        return [], 0
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


def advanced_query_index(corpus='', field="text", q='', page=1, per_page=10, fuzzy_search='n', phrase_search=False,
                         year=0, month=0, day=0, year_start=0, month_start=0, day_start=0, year_end=0, month_end=0,
                         day_end=0, date_plus_minus=0, **kwargs):
    # all parts of the query should be appended to the 'must' list. This assumes AND and not OR at the highest level
    corpus = corpus.split('+')
    body_template = {"query": {"bool": {"must": []}}, "sort": 'urn',
                     'from': (page - 1) * per_page, 'size': per_page
                     }
    if not current_app.elasticsearch:
        return [], 0
    if field == 'lemmas' or fuzzy_search == 'n':
        fuzz = '0'
    else:
        fuzz = 'AUTO'
    if q:
        body_template['highlight'] = {'fields': {field: {}},
                                      'pre_tags': ["<strong>"],
                                      'post_tags': ["</strong>"],
                                      'order': 'score'
                                      }
        if phrase_search:
            body_template["query"]["bool"]["must"].append({'match_phrase': {field: {'query': q, "slop": 4}}})
        else:
            body_template["query"]["bool"]["must"].append({'match': {field: {'query': q, 'fuzziness': fuzz}}})
    if year or month or day:
        date_template = {"nested": {"path": "specific_date", "query": {"bool": {"must": []}}}}
        if not date_plus_minus:
            if year:
                date_template["nested"]["query"]['bool']['must'].append({"match": {"specific_date.year": year}})
            if month:
                date_template["nested"]["query"]['bool']['must'].append({"match": {"specific_date.month": month}})
            if day:
                date_template["nested"]["query"]['bool']['must'].append({"match": {"specific_date.day": day}})
            body_template["query"]["bool"]["must"].append(date_template)
        else:
            if year:
                date_template["nested"]["query"]['bool']['must'].append({"range":
                                                                             {"specific_date.year":
                                                                                  {"gte": year - date_plus_minus,
                                                                                   "lte": year + date_plus_minus}}})
            if month:
                date_template["nested"]["query"]['bool']['must'].append({"match": {"specific_date.month": month}})
            if day:
                date_template["nested"]["query"]['bool']['must'].append({"match": {"specific_date.day": day}})
            body_template["query"]["bool"]["must"].append(date_template)

    elif year_start or month_start or day_start or year_end or month_end or year_end:
        body_template["query"]["bool"]["must"].append(build_date_range_template(year_start - date_plus_minus,
                                                                                month_start, day_start,
                                                                                year_end + date_plus_minus, month_end,
                                                                                day_end))
    search = current_app.elasticsearch.search(index=corpus, doc_type="", body=body_template)
    if q:
        ids = [{'id': hit['_id'], 'info': hit['_source'], 'sents': [Markup(x) for x in hit['highlight'][field]]} for hit in search['hits']['hits']]
    else:
        ids = [{'id': hit['_id'], 'info': hit['_source'], 'sents': []} for hit in search['hits']['hits']]
    # It may be good to comment this block out when I am not saving requests, though it probably won't affect performance.
    if current_app.config["SAVE_REQUESTS"]:
        req_name = "corpus={corpus}&field={field}&q={q}&fuzzy_search={fuzz}&phrase_search={phrase}&year={y}&" \
                   "month={m}&day={d}&year_start={y_s}&month_start={m_s}&day_start={d_s}&year_end={y_e}&" \
                   "month_end={m_e}&day_end={d_e}".format(corpus=corpus, field=field, q=q.replace(' ', '+'),
                                                          fuzz=fuzzy_search, phrase=phrase_search, y=year, m=month,
                                                          d=day, y_s=year_start, m_s=month_start, d_s=day_start,
                                                          y_e=year_end, m_e=month_end, d_e=day_end)
        fake = FakeElasticsearch(req_name, "advanced_search")
        fake.save_request(body_template)
        # Remove the textual parts from the results
        fake.save_ids([{"id": x['id']} for x in ids])
        fake.save_response(search)
    return ids, search['hits']['total']


def build_date_range_template(year_start, month_start, day_start, year_end, month_end, day_end):
    date_template = {"bool": {"should": []}}
    # need to add another clause for the dating field
    gte = '-'.join([str(x).zfill(y) for x, y in [(year_start, 4), (month_start, 2), (day_start, 2)] if x])
    lte = '-'.join([str(x).zfill(y) for x, y in [(year_end, 4), (month_end, 2), (day_end, 2)] if x])
    dating_template = {"range": {"dating": {}}}
    if gte:
        dating_template["range"]["dating"].update({"gte": gte})
    if lte:
        dating_template["range"]["dating"].update({"lte": lte})
    date_template['bool']['should'].append(dating_template)
    if year_start and month_start and day_start:
        if year_start == year_end and month_start == month_end:
            date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "gte": year_start,
                                            "lte": year_start
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.month": {
                                            "gte": month_start,
                                            "lte": month_start
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.day": {
                                            "gte": day_start,
                                            "lte": day_end
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
            return date_template
        else:
            date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "gte": year_start,
                                            "lte": year_start
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.month": {
                                            "gte": month_start,
                                            "lte": month_start
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.day": {
                                            "gte": day_start
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
        if year_start != year_end and month_start + 1 != month_end:
            date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "gte": year_start,
                                            "lte": year_start
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.month": {
                                            "gte": month_start + 1
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
    elif year_start and month_start:
        # Here we only need a single clause because
        if year_start == year_end:
            date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "gte": year_start,
                                            "lte": year_start
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.month": {
                                            "gte": month_start,
                                            "lte": month_end
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
            return date_template
        else:
            date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "gte": year_start,
                                            "lte": year_start
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.month": {
                                            "gte": month_start
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
    if year_end and month_end and day_end:
        date_template['bool']['should'].append({
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "specific_date",
                            "query": {
                                "range": {
                                    "specific_date.year": {
                                        "gte": year_end,
                                        "lte": year_end
                                    }
                                }
                            }
                        }
                    },
                    {
                        "nested": {
                            "path": "specific_date",
                            "query": {
                                "range": {
                                    "specific_date.month": {
                                        "gte": month_end,
                                        "lte": month_end
                                    }
                                }
                            }
                        }
                    },
                    {
                        "nested": {
                            "path": "specific_date",
                            "query": {
                                "range": {
                                    "specific_date.day": {
                                        "lte": day_end
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        })
        if month_end - 1 != month_start:
            date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "gte": year_end,
                                            "lte": year_end
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.month": {
                                            "lte": month_end - 1
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
    elif year_end and month_end:
        date_template['bool']['should'].append({
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "specific_date",
                            "query": {
                                "range": {
                                    "specific_date.year": {
                                        "gte": year_end,
                                        "lte": year_end
                                    }
                                }
                            }
                        }
                    },
                    {
                        "nested": {
                            "path": "specific_date",
                            "query": {
                                "range": {
                                    "specific_date.month": {
                                        "lte": month_end
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        })
    if year_start and year_end:
        if month_start or day_start:
            new_year_start = year_start + 1
        else:
            new_year_start = year_start
        if month_end or day_end:
            new_year_end = year_end - 1
        else:
            new_year_end = year_end
        date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "gte": new_year_start,
                                            "lte": new_year_end
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
    elif year_start:
        if month_start or day_start:
            new_year_start = year_start + 1
        else:
            new_year_start = year_start
        date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "gte": new_year_start
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
    elif year_end:
        if month_end or day_end:
            new_year_end = year_end - 1
        else:
            new_year_end = year_end
        date_template['bool']['should'].append({
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "specific_date",
                                "query": {
                                    "range": {
                                        "specific_date.year": {
                                            "lte": new_year_end
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            })
    return date_template
