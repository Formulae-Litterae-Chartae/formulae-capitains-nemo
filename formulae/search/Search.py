from flask import current_app, Markup, flash, session
from flask_babel import _
from flask_login import current_user
# This import is only needed for capturing the ES request. I could perhaps comment it out when it is not needed.
from tests.fake_es import FakeElasticsearch
from string import punctuation
import re
from copy import copy


PRE_TAGS = "</small><strong>"
POST_TAGS = "</strong><small>"
HIGHLIGHT_CHARS_BEFORE = 30
HIGHLIGHT_CHARS_AFTER = 30
AGGREGATIONS = {'range': {'date_range': {'field': 'min_date',
                                         'format': 'yyyy',
                                         'ranges': [{'key': '<499', 'from': '0002', 'to': '0499'},
                                                    {'key': '500-599', 'from': '0500', 'to': '0599'},
                                                    {'key': '600-699', 'from': '0600', 'to': '0699'},
                                                    {'key': '700-799', 'from': '0700', 'to': '0799'},
                                                    {'key': '800-899', 'from': '0800', 'to': '0899'},
                                                    {'key': '900-999', 'from': '0900', 'to': '0999'},
                                                    {'key': '>1000', 'from': '1000'}]}},
                'corpus': {'filters': {'filters': {'Angers': {'match': {'_type': 'andecavensis'}},
                                                   'Arnulfinger': {'match': {'_type': 'arnulfinger'}},
                                                   'Bünden': {'match': {'_type': 'buenden'}},
                                                   'Echternach': {'match': {'_type': 'echternach'}},
                                                   'Freising': {'match': {'_type': 'freising'}},
                                                   'Fulda (Dronke)': {'match': {'_type': 'fulda_dronke'}},
                                                   'Fulda (Stengel)': {'match': {'_type': 'fulda_stengel'}},
                                                   'Hersfeld': {'match': {'_type': 'hersfeld'}},
                                                   'Luzern': {'match': {'_type': 'luzern'}},
                                                   'Markulf': {'match': {'_type': 'markulf'}},
                                                   'Merowinger': {'match': {'_type': 'merowinger1'}},
                                                   'Mittelrheinisch': {'match': {'_type': 'mittelrheinisch'}},
                                                   'Mondsee': {'match': {'_type': 'mondsee'}},
                                                   'Passau': {'match': {'_type': 'passau'}},
                                                   'Rätien': {'match': {'_type': 'raetien'}},
                                                   'Regensburg': {'match': {'_type': 'regensburg'}},
                                                   'Rheinisch': {'match': {'_type': 'rheinisch'}},
                                                   'Salzburg': {'match': {'_type': 'salzburg'}},
                                                   'Schäftlarn': {'match': {'_type': 'schaeftlarn'}},
                                                   'St. Gallen': {'match': {'_type': 'stgallen'}},
                                                   'Weißenburg': {'match': {'_type': 'weissenburg'}},
                                                   'Werden': {'match': {'_type': 'werden'}},
                                                   'Zürich': {'match': {'_type': 'zuerich'}}}}},
                'no_date': {'missing': {'field': 'min_date'}}}
HITS_TO_READER = 10000


def build_sort_list(sort_str):
    if sort_str == 'urn':
        return 'urn'
    if sort_str == 'min_date_asc':
        return [{'all_dates': {'order': 'asc', 'mode': 'min'}}, 'urn']
    if sort_str == 'max_date_asc':
        return [{'all_dates': {'order': 'asc', 'mode': 'max'}}, 'urn']
    if sort_str == 'min_date_desc':
        return [{'all_dates': {'order': 'desc', 'mode': 'min'}}, 'urn']
    if sort_str == 'max_date_desc':
        return [{'all_dates': {'order': 'desc', 'mode': 'max'}}, 'urn']
    if sort_str == 'urn_desc':
        return [{'urn': {'order': 'desc'}}]


def query_index(index, field, query, page, per_page, sort='urn'):
    if not current_app.elasticsearch:
        return [], 0, {}
    if index in ['', ['']]:
        return [], 0, {}
    if not query:
        return [], 0, {}
    session.pop('previous_search', None)
    query_terms = query.split()
    clauses = []
    sort = build_sort_list(sort)
    for term in query_terms:
        if '*' in term or '?' in term:
            clauses.append({'span_multi': {'match': {'wildcard': {'text': term}}}})
        else:
            clauses.append({"span_term": {'text': term}})
    search_body = {'query': {'span_near': {'clauses': clauses, "slop": 0, 'in_order': True}},
                   "sort": sort,
                   'from': (page - 1) * per_page, 'size': per_page,
                   'highlight':
                       {'fields':
                            {field: {"fragment_size": 1000}
                             },
                        'pre_tags': [PRE_TAGS],
                        'post_tags': [POST_TAGS],
                        'encoder': 'html'
                        },
                   'aggs': AGGREGATIONS
                   }
    search = current_app.elasticsearch.search(index=index, doc_type="", body=search_body)
    set_session_token(index, search_body, field, query)
    ids = [{'id': hit['_id'], 'info': hit['_source'], 'sents': [Markup(highlight_segment(x)) for x in hit['highlight'][field]]} for hit in search['hits']['hits']]
    return ids, search['hits']['total'], search['aggregations']


def set_session_token(index, orig_template, field, q, regest_q=None):
    """ Sets session['previous_search'] to include the first X search results"""
    template = copy(orig_template)
    template.update({'from': 0, 'size': HITS_TO_READER})
    session_search = current_app.elasticsearch.search(index=index, doc_type="", body=template)
    search_hits = list()
    for hit in session_search['hits']['hits']:
        d = {'id': hit['_id'], 'title': hit['_source']['title']}
        open_text = hit['_id'] in current_app.config['nemo_app'].open_texts
        half_open_text = hit['_id'] in current_app.config['nemo_app'].half_open_texts
        if q:
            d['sents'] = [_('Text nicht zugänglich.')]
            if current_app.config['nemo_app'].check_project_team() is True or open_text:
                d['sents'] = [Markup(highlight_segment(x)) for x in hit['highlight'][field]]
        if regest_q:
            d['regest_sents'] = [_('Regest nicht zugänglich.')]
            if current_app.config['nemo_app'].check_project_team() is True or (open_text and not half_open_text):
                d['regest_sents'] = [Markup(highlight_segment(x)) for x in hit['highlight']['regest']]
        search_hits.append(d)
    session['previous_search'] = search_hits


def suggest_composition_places():
    """ To enable search-as-you-type for the place of composition field

    :return: sorted set of results
    """
    body = {'query': {'exists': {'field': 'comp_ort'}}}
    results = []
    for x in current_app.elasticsearch.search(index=['all'], doc_type='', size=10000, body=body)['hits']['hits']:
        results += x['_source']['comp_ort'].split('; ')
    return sorted(list(set(results)))


def suggest_word_search(**kwargs):
    """ To enable search-as-you-type for the text search

    :return: sorted set of results
    """
    results = []
    kwargs['fragment_size'] = 1000
    if kwargs['qSource'] == 'text':
        term = kwargs.get('q', '')
        if '*' in term or '?' in term:
            return None
        posts, total, aggs = advanced_query_index(per_page=1000, **kwargs)
        highlight = 'sents'
    elif kwargs['qSource'] == 'regest':
        term = kwargs.get('regest_q', '')
        if '*' in term or '?' in term:
            return None
        posts, total, aggs = advanced_query_index(per_page=1000, **kwargs)
        highlight = 'regest_sents'
    else:
        return None
    for post in posts:
        for sent in post[highlight]:
            r = str(sent[sent.find('</small><strong>'):])
            r = r.replace('</small><strong>', '').replace('</strong><small>', '')
            end_index = r.find(' ', len(term) + 30)
            results.append(re.sub(r'[{}]'.format(punctuation), '', r[:end_index] + r[end_index]).lower())
            """ind = 0
            while w in r[ind:]:
                i = r.find(w, ind)
                results.append(re.sub(r'[{}]'.format(punctuation), '', r[i:min(r.find(' ', i + len(word) + 30), len(r))]))
                ind = r.find(w, ind) + 1"""
    return [term] + sorted(list(set(results)), key=str.lower)[:10]


def highlight_segment(orig_str):
    """ returns only a section of the highlighting returned by Elasticsearch. This should keep highlighted phrases
        from breaking over lines

    :param orig_str: the original highlight string that should be shortened
    :param chars_before: the number of characters to include before the pre_tag
    :param chars_after: the number of characters to include after the post_tag
    :param pre_tag: the tag(s) that mark the beginning of the highlighted section
    :param post_tag: the tag(s) that mark the end of the highlighted section
    :return: the string to show in the search results
    """
    init_index = 0
    end_index = len(orig_str)
    chars_before, chars_after = HIGHLIGHT_CHARS_BEFORE, HIGHLIGHT_CHARS_AFTER
    pre_tag, post_tag = PRE_TAGS, POST_TAGS
    if orig_str.find(pre_tag) - chars_before > 0:
        init_index = max(orig_str.rfind(' ', 0, orig_str.find(pre_tag) - chars_before), 0)
    if orig_str.rfind(post_tag) + chars_after + len(post_tag) < len(orig_str):
        end_index = min(orig_str.find(' ', orig_str.rfind(post_tag) + chars_after + len(post_tag)), len(orig_str))
    if end_index == -1:
        end_index = len(orig_str)
    return orig_str[init_index:end_index]


def advanced_query_index(corpus=['all'], field="text", q='', page=1, per_page=10, fuzziness='0', phrase_search=False,
                         year=0, month=0, day=0, year_start=0, month_start=0, day_start=0, year_end=0, month_end=0,
                         day_end=0, date_plus_minus=0, exclusive_date_range="False", slop=4, in_order='False',
                         composition_place='', sort='urn', special_days=[], regest_q='', regest_field='regest',
                         **kwargs):
    # all parts of the query should be appended to the 'must' list. This assumes AND and not OR at the highest level
    old_sort = sort
    sort = build_sort_list(sort)
    session.pop('previous_search', None)
    body_template = {"query": {"bool": {"must": []}}, "sort": sort,
                     'from': (page - 1) * per_page, 'size': per_page,
                     'aggs': AGGREGATIONS
                     }
    body_template['highlight'] = {'fields': {field: {"fragment_size": 1000},
                                             regest_field: {"fragment_size": 1000}},
                                  'pre_tags': [PRE_TAGS],
                                  'post_tags': [POST_TAGS],
                                  'encoder': 'html'
                                  }
    if not current_app.elasticsearch:
        return [], 0, {}
    if field == 'lemmas':
        fuzz = '0'
        if '*' in q or '?' in q:
            flash(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."))
            return [], 0, {}
    else:
        fuzz = fuzziness
    if composition_place:
        body_template['query']['bool']['must'].append({'match': {'comp_ort': composition_place}})
    if q:
        clauses = []
        ordered_terms = True
        if in_order == 'False':
            ordered_terms = False
        for term in q.split():
            if '*' in term or '?' in term:
                clauses.append({'span_multi': {'match': {'wildcard': {field: term}}}})
            else:
                clauses.append({'span_multi': {'match': {'fuzzy': {field: {"value": term, "fuzziness": fuzz}}}}})
        body_template['query']['bool']['must'].append({'span_near': {'clauses': clauses, 'slop': slop,
                                                                     'in_order': ordered_terms}})

    if regest_q:
        clauses = []
        ordered_terms = True
        if in_order == 'False':
            ordered_terms = False
        for term in regest_q.split():
            if '*' in term or '?' in term:
                clauses.append({'span_multi': {'match': {'wildcard': {regest_field: term}}}})
            else:
                clauses.append({'span_multi': {'match': {'fuzzy': {regest_field: {"value": term, "fuzziness": fuzz}}}}})
        body_template['query']['bool']['must'].append({'span_near': {'clauses': clauses, 'slop': slop,
                                                                     'in_order': ordered_terms}})

    if year or month or day:
        date_template = {"bool": {"must": []}}
        if not date_plus_minus:
            if year:
                date_template['bool']['must'].append({"match": {"specific_date.year": year}})
            if month:
                date_template['bool']['must'].append({"match": {"specific_date.month": month}})
            if day:
                date_template['bool']['must'].append({"match": {"specific_date.day": day}})
        else:
            if year:
                date_template['bool']['must'].append({"range": {"specific_date.year":
                                                                                       {"gte": year - date_plus_minus,
                                                                                        "lte": year + date_plus_minus}
                                                                                   }
                                                                         })
            if month:
                date_template['bool']['must'].append({"match": {"specific_date.month": month}})
            if day:
                date_template['bool']['must'].append({"match": {"specific_date.day": day}})
        if not month and not day:
            # This line should return True for all formulae
            should_clause = [date_template, {"match": {"specific_date.year": "0001"}}]
        else:
            should_clause = [date_template]
        date_template = {'bool': {'should': []}}
        if year:
            if not date_plus_minus:
                date_template['bool']['should'].append({'match':
                                                        {'dating':
                                                            '{:04}{}{}'.format(year,
                                                                               '-{:02}'.format(month) if month else '',
                                                                               '-{:02}'.format(day) if month and day else '')}})
            else:
                date_template['bool']['should'].append({'range':
                                                        {'dating':
                                                            {'gte': '{:04}{}{}'.format(year - date_plus_minus,
                                                                                       '-{:02}'.format(month) if month else '',
                                                                                       '-{:02}'.format(day) if month and day else ''),
                                                             'lte': '{:04}{}{}'.format(year + date_plus_minus,
                                                                                       '-{:02}'.format(month) if month else '',
                                                                                       '-{:02}'.format(day) if month and day else '')}}})
        date_template['bool']['should'].append({"nested":
                                                    {"path": "specific_date",
                                                     "query":
                                                         {"bool":
                                                              {"should": should_clause}}}})
        body_template["query"]["bool"]["must"].append(date_template)
    elif year_start or month_start or day_start or year_end or month_end or year_end:
        if exclusive_date_range != 'False':
            body_template["query"]["bool"]["must"] += build_spec_date_range_template(year_start, month_start,
                                                                                     day_start, year_end,
                                                                                     month_end, day_end)
        else:
            body_template["query"]["bool"]["must"].append(build_date_range_template(year_start, month_start, day_start,
                                                                                    year_end, month_end, day_end))
    if any(special_days):
        s_d_template = {'bool': {'should': []}}
        for s_d in special_days:
            s_d_template['bool']['should'].append({'match': {'days': s_d}})
        body_template["query"]["bool"]["must"].append(s_d_template)
    search = current_app.elasticsearch.search(index=corpus, doc_type="", body=body_template)
    set_session_token(corpus, body_template, field, q if field == 'text' else '',
                      regest_q if regest_field == 'regest' else '')
    if q:
        # The following lines transfer "highlighting" to the text field so that the user sees the text instead of
        # a series of lemmata. The problem is that there is no real highlighting since the text and lemmas fields don't
        # match up 1-to-1.
        if field == 'lemmas':
            ids = []
            for hit in search['hits']['hits']:
                sentences = []
                start = 0
                lems = hit['_source']['lemmas'].split()
                inflected = hit['_source']['text'].split()
                ratio = len(inflected)/len(lems)
                if ' ' in q:
                    addend = 0 if ordered_terms else 1
                    query_words = q.split()
                    for i, w in enumerate(lems):
                        if w == query_words[0] and set(query_words).issubset(lems[max(i - (int(slop) + addend), 0):min(i + (int(slop) + len(query_words)), len(lems))]):
                            rounded = round(i * ratio)
                            sentences.append(' '.join(inflected[max(rounded - 15, 0):min(rounded + 15, len(inflected))]))
                else:
                    while q in lems[start:]:
                        i = lems.index(q, start)
                        start = i + 1
                        rounded = round(i * ratio)
                        sentences.append(' '.join(inflected[max(rounded - 10, 0):min(rounded + 10, len(inflected))]))
                ids.append({'id': hit['_id'], 'info': hit['_source'], 'sents': sentences,
                            'regest_sents': [Markup(highlight_segment(x)) for x in hit['highlight'][regest_field]]
                            if 'highlight' in hit and regest_field in hit['highlight'] else []})
        else:
            ids = [{'id': hit['_id'],
                    'info': hit['_source'],
                    'sents': [Markup(highlight_segment(x)) for x in hit['highlight'][field]],
                    'regest_sents': [Markup(highlight_segment(x)) for x in hit['highlight'][regest_field]]
                    if 'highlight' in hit and regest_field in hit['highlight'] else []}
                   for hit in search['hits']['hits']]
    elif regest_q:
        ids = [{'id': hit['_id'],
                'info': hit['_source'],
                'sents': [],
                'regest_sents': [Markup(highlight_segment(x)) for x in hit['highlight'][regest_field]]}
               for hit in search['hits']['hits']]
    else:
        ids = [{'id': hit['_id'], 'info': hit['_source'], 'sents': [], 'regest_sents': []}
               for hit in search['hits']['hits']]
    # It may be good to comment this block out when I am not saving requests, though it probably won't affect performance.
    if current_app.config["SAVE_REQUESTS"] and 'autocomplete' not in field and 'autocomplete_regest' not in regest_field:
        req_name = "{corpus}&{field}&{q}&{fuzz}&{in_order}&{y}&{slop}&" \
                   "{m}&{d}&{y_s}&{m_s}&{d_s}&{y_e}&" \
                   "{m_e}&{d_e}&{d_p_m}&" \
                   "{e_d_r}&{c_p}&" \
                   "{sort}&{spec_days}&{regest_q}&{regest_field}".format(corpus='+'.join(corpus), field=field,
                                                                         q=q.replace(' ', '+'), fuzz=fuzziness,
                                                                         in_order=in_order, slop=slop, y=year, m=month,
                                                                         d=day, y_s=year_start,
                                                                         m_s=month_start, d_s=day_start, y_e=year_end,
                                                                         m_e=month_end, d_e=day_end,
                                                                         d_p_m=date_plus_minus,
                                                                         e_d_r=exclusive_date_range,
                                                                         c_p=composition_place, sort=old_sort,
                                                                         spec_days='+'.join(special_days),
                                                                         regest_q=regest_q.replace(' ', '+'),
                                                                         regest_field=regest_field)
        fake = FakeElasticsearch(req_name, "advanced_search")
        fake.save_request(body_template)
        # Remove the textual parts from the results
        fake.save_ids([{"id": x['id']} for x in ids])
        fake.save_response(search)
    return ids, search['hits']['total'], search['aggregations']


def build_spec_date_range_template(spec_year_start, spec_month_start, spec_day_start, spec_year_end, spec_month_end,
                                   spec_day_end):
    """ Builds the date template for the specific date range search.
        Currently it only works with 'specific_date'. I will need to think about whether it should work with 'dating'.

    :param spec_year_start: the beginning year in which to search
    :param spec_month_start: the beginning month to search within each year in the year range
    :param spec_day_start: the beginning day in which to search within each month in the month range
    :param spec_year_end: the ending year in which to search
    :param spec_month_end: the ending month to search within each year in the year range
    :param spec_day_end: the ending day to search within each month in the month range
    :return: list of query-part dictionaries
    """
    date_template = []
    if (spec_year_start or spec_year_end) and spec_year_end != spec_year_start and not spec_month_end \
            and not spec_month_start and not spec_day_start and not spec_day_end:
        should_clause = [{"match": {"specific_date.year": "0001"}}]
    else:
        should_clause = []
    spec_year_start = spec_year_start or 0
    spec_year_end = spec_year_end or 2000
    spec_month_start = spec_month_start or 1
    spec_month_end = spec_month_end or 12
    spec_day_start = spec_day_start or 1
    spec_day_end = spec_day_end or 31
    date_template.append({'range': {'specific_date.year':
                                                 {"gte": spec_year_start, 'lte': spec_year_end}
                                             }})
    if spec_month_start != spec_month_end:
        day_template = {"bool": {"should": [{'bool': {'must': [{"match": {"specific_date.month": spec_month_start}},
                                                           {"range": {"specific_date.day": {'gte': spec_day_start}}}]}},
                                            {"range": {"specific_date.month": {"gt": spec_month_start,
                                                                               "lt": spec_month_end}}},
                                            {'bool': {'must': [{"match": {"specific_date.month": spec_month_end}},
                                                               {"range": {"specific_date.day": {'lte': spec_day_end}}}]}}]}}
    else:
        day_template = {"bool": {"should": [{'bool': {'must': [{"match": {"specific_date.month": spec_month_end}},
                                                               {"range": {"specific_date.day": {'lte': spec_day_end,
                                                                                                'gte': spec_day_start}}}]}}]}}
    date_template.append(day_template)
    should_clause.append({"bool": {"must": date_template}})
    date_template = [{"nested":
                         {'path': "specific_date",
                          "query":
                              {"bool":
                                   {"should": should_clause}}}}]
    return date_template


def build_date_range_template(year_start, month_start, day_start, year_end, month_end, day_end):
    date_template = {"bool": {"should": []}}
    gte = '-'.join([str(x).zfill(y) for x, y in [(year_start, 4), (month_start, 2), (day_start, 2)] if x])
    lte = '-'.join([str(x).zfill(y) for x, y in [(year_end, 4), (month_end, 2), (day_end, 2)] if x])
    dating_template = {"range": {"dating": {}}}
    if gte:
        dating_template["range"]["dating"].update({"gte": gte})
    if lte:
        dating_template["range"]["dating"].update({"lte": lte})
    date_template['bool']['should'].append(dating_template)
    if (year_end or year_start) and year_start != year_end:
        date_template['bool']['should'].append({"nested": {"path": "specific_date",
                                                           "query": {"match": {"specific_date.year": "0001"}}}})
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
