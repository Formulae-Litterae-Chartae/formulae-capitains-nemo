from flask import current_app, Markup, flash, session, g
from flask_babel import _
from tests.fake_es import FakeElasticsearch
from string import punctuation
import re
from copy import copy
from typing import Dict, List, Union, Tuple, Set
from itertools import product
from jellyfish import levenshtein_distance
from collections import defaultdict


PRE_TAGS = "</small><strong>"
POST_TAGS = "</strong><small>"
HIGHLIGHT_CHARS_BEFORE = 30
HIGHLIGHT_CHARS_AFTER = 30
range_agg = {'date_range': {'field': 'min_date', 'format': 'yyyy',
                            'ranges': [{'key': '<499', 'from': '0002', 'to': '0499'},
                                       {'key': '500-599', 'from': '0500', 'to': '0599'},
                                       {'key': '600-699', 'from': '0600', 'to': '0699'},
                                       {'key': '700-799', 'from': '0700', 'to': '0799'},
                                       {'key': '800-899', 'from': '0800', 'to': '0899'},
                                       {'key': '900-999', 'from': '0900', 'to': '0999'},
                                       {'key': '>1000', 'from': '1000'}]}}
corpus_agg = {'filters': {'filters': {'Angers': {'match': {'_type': 'andecavensis'}},
                                      'Arnulfinger': {'match': {'_type': 'arnulfinger'}},
                                      'Bünden': {'match': {'_type': 'buenden'}},
                                      'Echternach': {'match': {'_type': 'echternach'}},
                                      'Freising': {'match': {'_type': 'freising'}},
                                      'Fulda (Dronke)': {'match': {'_type': 'fulda_dronke'}},
                                      'Fulda (Stengel)': {'match': {'_type': 'fulda_stengel'}},
                                      'Hersfeld': {'match': {'_type': 'hersfeld'}},
                                      'Katalonien': {'match': {'_type': 'katalonien'}},
                                      'Lorsch': {'match': {'_type': 'lorsch'}},
                                      'Luzern': {'match': {'_type': 'luzern'}},
                                      'Marculf': {'match': {'_type': 'marculf'}},
                                      'Marmoutier - Fougères': {'match': {'_type': 'marmoutier_fougères'}},
                                      'Marmoutier - Serfs': {'match': {'_type': 'marmoutier_serfs'}},
                                      'Marmoutier - Vendômois': {'match': {'_type': 'marmoutier_vendomois'}},
                                      'Marmoutier - Vendômois, Saint-Marc': {'match': {'_type': 'marmoutier_vendomois_saintmarc'}},
                                      'Merowinger': {'match': {'_type': 'merowinger1'}},
                                      'Mittelrheinisch': {'match': {'_type': 'mittelrheinisch'}},
                                      'Mondsee': {'match': {'_type': 'mondsee'}},
                                      'Papsturkunden Frankreich': {'match': {'_type': 'papsturkunden_frankreich'}},
                                      'Passau': {'match': {'_type': 'passau'}},
                                      'Rätien': {'match': {'_type': 'raetien'}},
                                      'Regensburg': {'match': {'_type': 'regensburg'}},
                                      'Rheinisch': {'match': {'_type': 'rheinisch'}},
                                      'Salzburg': {'match': {'_type': 'salzburg'}},
                                      'Schäftlarn': {'match': {'_type': 'schaeftlarn'}},
                                      'St. Gallen': {'match': {'_type': 'stgallen'}},
                                      'Weißenburg': {'match': {'_type': 'weissenburg'}},
                                      'Werden': {'match': {'_type': 'werden'}},
                                      'Zürich': {'match': {'_type': 'zuerich'}}}}}
no_date_agg = {'missing': {'field': 'min_date'}}
AGGREGATIONS = {'range': range_agg,
                'corpus': corpus_agg,
                'no_date': no_date_agg,
                'all_docs': {'global': {},
                             'aggs': {
                                 'range': range_agg,
                                 'corpus': corpus_agg,
                                 'no_date': no_date_agg
                             }}}
HITS_TO_READER = 10000
LEMMA_INDICES = {'normal': ['lemmas'], 'auto': ['autocomplete_lemmas']}


def build_sort_list(sort_str: str) -> Union[str, List[Union[Dict[str, Dict[str, str]], str]]]:
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


def query_index(index: list, field: str, query: str, page: int, per_page: int,
                sort: str = 'urn', old_search: bool = False) -> Tuple[List[Dict[str,
                                                                                Union[str, list]]],
                                                                      int,
                                                                      dict,
                                                                      List[Dict[str,
                                                                                Union[str,
                                                                                      List[str]]]]]:
    prev_search = dict()
    if not current_app.elasticsearch:
        return [], 0, {}, []
    if index in ['', ['']]:
        return [], 0, {}, []
    if not query:
        return [], 0, {}, []
    if old_search is False:
        session.pop('previous_search', None)
    query_terms = query.split()
    clauses = []
    sort = build_sort_list(sort)
    if field == 'lemmas':
        if '*' in query or '?' in query:
            flash(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."))
            return [], 0, {}, []
    for term in query_terms:
        if '*' in term or '?' in term:
            clauses.append([{'span_multi': {'match': {'wildcard': {field: term}}}}])
        else:
            if field == 'lemmas' and term in current_app.config['nemo_app'].lem_to_lem_mapping:
                sub_clauses = [{'span_term': {field: term}}]
                for other_lem in current_app.config['nemo_app'].lem_to_lem_mapping[term]:
                    sub_clauses.append({'span_term': {field: other_lem}})
                clauses.append(sub_clauses)
            else:
                clauses.append([{'span_term': {field: term}}])
    bool_clauses = []
    for clause in product(*clauses):
        bool_clauses.append({'span_near': {'clauses': list(clause), 'slop': 0, 'in_order': True}})
    search_body = {'query': {'bool': {'should': bool_clauses, 'minimum_should_match': 1}},
                   "sort": sort,
                   'from': (page - 1) * per_page, 'size': per_page,
                   'highlight':
                       {'fields': {field: {"fragment_size": 1000}},
                        'pre_tags': [PRE_TAGS],
                        'post_tags': [POST_TAGS],
                        'encoder': 'html'
                        },
                   'aggs': AGGREGATIONS
                   }
    search = current_app.elasticsearch.search(index=index, doc_type="", body=search_body)
    if old_search is False:
        prev_search = set_session_token(index, search_body, field, query, fuzz='0')
    ids, highlighted_terms = lem_highlight_to_text(search, query, False, 0, 'regest', field, 'text', fuzz=0)
    return ids, search['hits']['total'], search['aggregations'], prev_search


def set_session_token(index: list, orig_template: dict, field: str, q: str, regest_q: str = None,
                      ordered_terms: bool = False, slop: int = 0,
                      regest_field: str = 'regest', fuzz: str = '0') -> List[Dict[str, Union[str, List[str]]]]:
    """ Sets previous search to include the first X search results"""
    template = copy(orig_template)
    template.update({'from': 0, 'size': HITS_TO_READER})
    session_search = current_app.elasticsearch.search(index=index, doc_type="", body=template)
    search_hits = list()
    highlighted_terms = set()
    if q:
        search_hits, highlighted_terms = lem_highlight_to_text(session_search, q, ordered_terms, slop, regest_field,
                                                               field, 'text', fuzz)
    g.highlighted_words = highlighted_terms
    return search_hits


def suggest_composition_places() -> List[str]:
    """ To enable search-as-you-type for the place of composition field

    :return: sorted set of results
    """
    body = {'query': {'exists': {'field': 'comp_ort'}}}
    results = []
    for x in current_app.elasticsearch.search(index=['all'], doc_type='', size=10000, body=body)['hits']['hits']:
        results += x['_source']['comp_ort'].split('; ')
    return sorted(list(set(results)))


def suggest_word_search(**kwargs) -> Union[List[str], None]:
    """ To enable search-as-you-type for the text search

    :return: sorted set of results
    """
    results = set()
    kwargs['fragment_size'] = 1000
    field_mapping = {'autocomplete': 'text', 'autocomplete_lemmas': 'lemmas'}
    if kwargs['qSource'] == 'text':
        highlight_field = field_mapping[kwargs.get('field', 'autocomplete')]
        term = kwargs.get('q', '')
        if '*' in term or '?' in term:
            return None
        posts, total, aggs, prev_search = advanced_query_index(per_page=1000, **kwargs)
    elif kwargs['qSource'] == 'regest':
        highlight_field = 'regest'
        term = kwargs.get('regest_q', '')
        if '*' in term or '?' in term:
            return None
        posts, total, aggs, prev_search = advanced_query_index(per_page=1000, **kwargs)
    else:
        return None
    for post in posts:
        r = re.sub(r'[{}]'.format(punctuation), '', post['info'][highlight_field]).lower()
        ind = 0
        sep = ''
        while term in r[ind:]:
            if ind > 0:
                sep = ' '
            i = r.find(sep + term, ind)
            if i == -1:
                ind = i
                continue
            results.add(r[i:min(r.find(' ', i + len(term) + 30), len(r))].strip())
            ind = i + len(sep + term)
    return sorted(results, key=str.lower)[:10]


def highlight_segment(orig_str: str) -> str:
    """ returns only a section of the highlighting returned by Elasticsearch. This should keep highlighted phrases
        from breaking over lines

    :param orig_str: the original highlight string that should be shortened
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


def lem_highlight_to_text(search: dict, q: str, ordered_terms: bool, slop: int, regest_field: str, search_field: str,
                          highlight_field: str, fuzz: str) -> Tuple[List[Dict[str, Union[str, list]]], Set[str]]:
    """ Transfer ElasticSearch highlighting from segments in the lemma field to segments in the text field

    :param search:
    :param q:
    :param ordered_terms:
    :param slop:
    :param regest_field:
    :return:
    """
    ids = []
    all_highlighted_terms = set()
    for hit in search['hits']['hits']:
        sentences = [_('Text nicht zugänglich.')]
        sentence_spans = [range(0, 1)]
        open_text = hit['_id'] in current_app.config['nemo_app'].open_texts
        half_open_text = hit['_id'] in current_app.config['nemo_app'].half_open_texts
        if current_app.config['nemo_app'].check_project_team() is True or hit['_id'] in current_app.config['nemo_app'].open_texts:
            text = hit['_source'][highlight_field]
            sentences = []
            sentence_spans = []
            vectors = current_app.config['nemo_app'].all_term_vectors[hit['_id']]
            highlight_offsets = dict()
            searched_positions = dict()
            for v in vectors['term_vectors'][highlight_field]['terms'].values():
                for o in v['tokens']:
                    highlight_offsets[o['position']] = (o['start_offset'], o['end_offset'])
            for k, v in vectors['term_vectors'][search_field]['terms'].items():
                for o in v['tokens']:
                    searched_positions[o['position']] = k
            highlighted_words = set()
            for highlight in hit['highlight'][search_field]:
                for m in re.finditer(r'{}(\w+){}'.format(PRE_TAGS, POST_TAGS), highlight):
                    highlighted_words.add(m.group(1).lower())
            all_highlighted_terms.update(highlighted_words)
            if ' ' in q:
                q_words = q.split()
                positions = {k: [] for k in q_words}
                for token in q_words:
                    terms = {token}
                    if re.search(r'[?*]', token):
                        terms = set()
                        new_token = token.replace('?', '\\w').replace('*', '\\w*')
                        for term in highlighted_words:
                            if re.fullmatch(r'{}'.format(new_token), term):
                                terms.add(term)
                    elif fuzz != '0':
                        terms = set()
                        if fuzz == 'AUTO':
                            fuzz = min(len(token) // 3, 2)
                        else:
                            fuzz = int(fuzz)
                        for term in highlighted_words:
                            if levenshtein_distance(term, token) <= fuzz:
                                terms.add(term)
                    for w in terms:
                        if search_field == 'lemmas':
                            if w in vectors['term_vectors']['lemmas']['terms']:
                                positions[token] += [i['position'] for i in vectors['term_vectors']['lemmas']['terms'][w]['tokens']]
                            for other_lem in current_app.config['nemo_app'].lem_to_lem_mapping.get(w, {}):
                                if other_lem in vectors['term_vectors']['lemmas']['terms']:
                                    positions[token] += [i['position'] for i in vectors['term_vectors']['lemmas']['terms'][other_lem]['tokens']]
                            positions[token] = sorted(positions[w])
                        else:
                            positions[token] += [i['position'] for i in vectors['term_vectors'][search_field]['terms'][w]['tokens']]
                search_range_start = int(slop) + len(q_words)
                search_range_end = int(slop) + len(q_words) + 1
                if ordered_terms:
                    search_range_start = -1
                for pos in positions[q_words[0]]:
                    index_range = range(max(pos - search_range_start - 1, 0), pos + search_range_end + 1)
                    used_q_words = {q_words[0]}
                    span = {pos}
                    for w in q_words[1:]:
                        for next_pos in positions[w]:
                            if next_pos in index_range and next_pos not in span:
                                span.add(next_pos)
                                used_q_words.add(w)
                                break
                    if set(q_words) == used_q_words and len(span) == len(q_words):
                        ordered_span = sorted(span)
                        if (ordered_span[-1] - ordered_span[0]) - (len(ordered_span) - 1) <= int(slop):
                            start_offsets = [highlight_offsets[x][0] for x in ordered_span]
                            end_offsets = [highlight_offsets[x][1] for x in ordered_span]
                            start_index = highlight_offsets[max(0, ordered_span[0] - 10)][0]
                            end_index = highlight_offsets[min(len(highlight_offsets) - 1, ordered_span[-1] + 10)][1] + 1
                            sentence = ''
                            for i, x in enumerate(text[start_index:end_index]):
                                if i + start_index in start_offsets:
                                    sentence += PRE_TAGS + x
                                elif i + start_index in end_offsets:
                                    sentence += x + POST_TAGS
                                else:
                                    sentence += x
                            marked_sent = Markup(sentence)
                            if marked_sent not in sentences:
                                sentences.append(marked_sent)
                                sentence_spans.append(range(max(0, ordered_span[0] - 10),
                                                            min(len(highlight_offsets), ordered_span[-1] + 11)))
            else:
                terms = {q}
                if re.search(r'[?*]', q) or fuzz != '0':
                    terms = highlighted_words
                positions = []
                for w in terms:
                    if search_field == 'lemmas':
                        if w in vectors['term_vectors']['lemmas']['terms']:
                            positions += [i['position'] for i in vectors['term_vectors']['lemmas']['terms'][w]['tokens']]
                        for other_lem in current_app.config['nemo_app'].lem_to_lem_mapping.get(w, {}):
                            if other_lem in vectors['term_vectors']['lemmas']['terms']:
                                positions += [i['position'] for i in vectors['term_vectors']['lemmas']['terms'][other_lem]['tokens']]
                    else:
                        positions += [i['position'] for i in vectors['term_vectors'][search_field]['terms'][w]['tokens']]
                positions = sorted(positions)
                for pos in positions:
                    start_offset = highlight_offsets[pos][0]
                    end_offset = highlight_offsets[pos][1]
                    start_index = highlight_offsets[max(0, pos - 10)][0]
                    end_index = highlight_offsets[min(len(highlight_offsets) - 1, pos + 10)][1] + 1
                    sentence = ''
                    for i, x in enumerate(text[start_index:end_index]):
                        if i + start_index == start_offset:
                            sentence += PRE_TAGS + x
                        elif i + start_index == end_offset:
                            sentence += x + POST_TAGS
                        else:
                            sentence += x
                    sentences.append(Markup(sentence))
                    sentence_spans.append(range(max(0, pos - 10), min(len(highlight_offsets), pos + 11)))
        regest_sents = []
        show_regest = current_app.config['nemo_app'].check_project_team() is True or (open_text and not half_open_text)
        if 'highlight' in hit and regest_field in hit['highlight']:
            if show_regest is False:
                regest_sents = [_('Regest nicht zugänglich.')]
            else:
                regest_sents = [Markup(highlight_segment(x)) for x in hit['highlight'][regest_field]]
        ordered_sentences = list()
        ordered_sentence_spans = list()
        for x, y in sorted(zip(sentences, sentence_spans), key=lambda z: (z[1].start, z[1].stop)):
            ordered_sentences.append(x)
            ordered_sentence_spans.append(y)
        ids.append({'id': hit['_id'],
                    'info': hit['_source'], 
                    'sents': ordered_sentences,
                    'sentence_spans': ordered_sentence_spans,
                    'title': hit['_source']['title'],
                    'regest_sents': regest_sents})
    return ids, all_highlighted_terms


def advanced_query_index(corpus: list = None, field: str = "text", q: str = '', page: int = 1, per_page: int = 10,
                         fuzziness: str = '0', year: int = 0, month: int = 0, day: int = 0, year_start: int = 0,
                         month_start: int = 0, day_start: int = 0, year_end: int = 0, month_end: int = 0, day_end: int = 0,
                         date_plus_minus: int = 0, exclusive_date_range: str = "False", slop: int = 4, in_order: str = 'False',
                         composition_place: str = '', sort: str = 'urn', special_days: list = None, regest_q: str = '',
                         regest_field: str = 'regest', old_search: bool = False,
                         **kwargs) -> Tuple[List[Dict[str, Union[str, list, dict]]],
                                            int,
                                            dict,
                                            List[Dict[str, Union[str, List[str]]]]]:
    # all parts of the query should be appended to the 'must' list. This assumes AND and not OR at the highest level
    prev_search = dict()
    if corpus is None:
        corpus = ['all']
    if special_days is None:
        special_days = []
    old_sort = sort
    sort = build_sort_list(sort)
    if old_search is False:
        session.pop('previous_search', None)
    body_template = dict({"query": {"bool": {"must": []}}, "sort": sort, 'from': (page - 1) * per_page,
                          'size': per_page, 'aggs': AGGREGATIONS})

    body_template['highlight'] = {'fields': {field: {"fragment_size": 1000},
                                             regest_field: {"fragment_size": 1000}},
                                  'pre_tags': [PRE_TAGS],
                                  'post_tags': [POST_TAGS],
                                  'encoder': 'html'
                                  }
    if not current_app.elasticsearch:
        return [], 0, {}, []
    ordered_terms = True
    if in_order == 'False':
        ordered_terms = False
    if field == 'lemmas':
        fuzz = '0'
        if '*' in q or '?' in q:
            flash(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."))
            return [], 0, {}, []
    else:
        fuzz = fuzziness
    if composition_place:
        body_template['query']['bool']['must'].append({'match': {'comp_ort': composition_place}})
    if q:
        clauses = []
        for term in q.split():
            if '*' in term or '?' in term:
                clauses.append([{'span_multi': {'match': {'wildcard': {field: term}}}}])
            else:
                if field == 'lemmas' and term in current_app.config['nemo_app'].lem_to_lem_mapping:
                    sub_clauses = [{'span_multi': {'match': {'fuzzy': {field: {"value": term, "fuzziness": fuzz}}}}}]
                    for other_lem in current_app.config['nemo_app'].lem_to_lem_mapping[term]:
                        sub_clauses.append({'span_multi': {'match': {'fuzzy': {field: {"value": other_lem, "fuzziness": fuzz}}}}})
                    clauses.append(sub_clauses)
                else:
                    clauses.append([{'span_multi': {'match': {'fuzzy': {field: {"value": term, "fuzziness": fuzz}}}}}])
        bool_clauses = []
        for clause in product(*clauses):
            bool_clauses.append({'span_near': {'clauses': list(clause), 'slop': slop, 'in_order': ordered_terms}})
        body_template['query']['bool']['must'].append({'bool': {'should': bool_clauses, 'minimum_should_match': 1}})

    if regest_q:
        clauses = []
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
                date_template['bool']['must'].append({"range": {"specific_date.year": {"gte": year - date_plus_minus,
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
        date_template['bool']['should'].append({"nested": {"path": "specific_date",
                                                           "query": {"bool": {"should": should_clause}}}})
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
    if q:
        # The following lines transfer "highlighting" to the text field so that the user sees the text instead of
        # a series of lemmata.
        if field in ('lemmas', 'text'):
            ids, highlighted_terms = lem_highlight_to_text(search, q, ordered_terms, slop, regest_field, field, 'text',
                                                           fuzz)
        else:
            ids = [{'id': hit['_id'],
                    'info': hit['_source'],
                    'sents': [Markup(highlight_segment(x)) for x in hit['highlight'][field]] if 'highlight' in hit else [],
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
    if field not in ['autocomplete_lemmas', 'autocomplete'] and old_search is False:
        prev_search = set_session_token(corpus, body_template, field, q if field in ['text', 'lemmas'] else '',
                          regest_q if regest_field == 'regest' else '', ordered_terms, slop, regest_field, fuzz=fuzz)
    if current_app.config["SAVE_REQUESTS"]:
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
    return ids, search['hits']['total'], search['aggregations'], prev_search


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
    date_template.append({'range': {'specific_date.year': {"gte": spec_year_start, 'lte': spec_year_end}}})
    if spec_month_start != spec_month_end:
        day_template = {"bool": {"should": [{'bool': {'must': [{"match": {"specific_date.month": spec_month_start}},
                                                               {"range":  {"specific_date.day": {
                                                                   'gte': spec_day_start}}}]}},
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
    date_template = [{"nested": {'path': "specific_date",  "query": {"bool": {"should": should_clause}}}}]
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
