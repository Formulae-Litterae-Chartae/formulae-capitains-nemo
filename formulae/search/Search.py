from flask import current_app, Markup, flash, session, g
from flask_babel import _
from tests.fake_es import FakeElasticsearch
from string import punctuation
import re
from copy import deepcopy
from typing import Dict, List, Union, Tuple, Set
from itertools import product
from Levenshtein import distance
from math import floor


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
corpus_agg = {'filters': {'filters': {'<b>Angers</b>: Angers': {'match': {'collection': 'form_lit_chart-andecavensis'}},
                                      "<b>Anjou</b>: Archives d’Anjou": {'match': {'collection': 'form_lit_chart-anjou_archives'}},
                                      "<b>Anjou</b>: Chroniques des comtes d’Anjou": {'match': {'collection': 'form_lit_chart-anjou_comtes_chroniques'}},
                                      '<b>Auvergne</b>: Auvergne': {'match': {'collection': 'form_lit_chart-auvergne'}},
                                      '<b>Bourges</b>: Bourges': {'match': {'collection': 'form_lit_chart-bourges'}},
                                      '<b>Catalunya</b>: Katalonien': {'match': {'collection': 'form_lit_chart-katalonien'}},
                                      '<b>Chartae Latinae</b>: Chartae Latinae X': {'match': {'collection': 'form_lit_chart-chartae_latinae_x'}},
                                      '<b>Chartae Latinae</b>: Chartae Latinae XI': {'match': {'collection': 'form_lit_chart-chartae_latinae_xi'}},
                                      '<b>Chartae Latinae</b>: Chartae Latinae XII': {'match': {'collection': 'form_lit_chart-chartae_latinae_xii'}},
                                      '<b>Chartae Latinae</b>: Chartae Latinae XLVI': {'match': {'collection': 'form_lit_chart-chartae_latinae_xlvi'}},
                                      '<b>Chartae Latinae</b>: Chartae Latinae XLVII': {'match': {'collection': 'form_lit_chart-chartae_latinae_xlvii'}},
                                      '<b>Chartae Latinae</b>: Chartae Latinae CXV': {'match': {'collection': 'form_lit_chart-chartae_latinae_cxv'}},
                                      '<b>Chartae Latinae</b>: Chartae Latinae CXVI': {'match': {'collection': 'form_lit_chart-chartae_latinae_cxvi'}},
                                      '<b>Dijon</b>: Saint-Bénigne de Dijon': {'match': {'collection': 'form_lit_chart-saint_bénigne'}},
                                      '<b>Echternach</b>: Echternach': {'match': {'collection': 'form_lit_chart-echternach'}},
                                      '<b>E-Lexikon</b>': {'match': {'collection': 'form_lit_chart-elexicon'}},
                                      '<b>Flavigny</b>: Flavigny': {'match': {'collection': 'form_lit_chart-flavigny'}},
                                      '<b>Formulae Marculfinae</b>: Formulae Marculfinae': {'match': {'collection': 'form_lit_chart-formulae_marculfinae'}},
                                      '<b>Freising</b>: Freising': {'match': {'collection': 'form_lit_chart-freising'}},
                                      '<b>Fulda</b>: Fulda (Dronke)': {'match': {'collection': 'form_lit_chart-fulda_dronke'}},
                                      '<b>Fulda</b>: Fulda (Stengel)': {'match': {'collection': 'form_lit_chart-fulda_stengel'}},
                                      '<b>Gorze</b>: Gorze': {'match': {'collection': 'form_lit_chart-gorze'}},
                                      '<b>Graubünden</b>: Bünden': {'match': {'collection': 'form_lit_chart-buenden'}},
                                      '<b>Hersfeld</b>: Hersfeld': {'match': {'collection': 'form_lit_chart-hersfeld'}},
                                      '<b>Herrscherurkunden</b>: Arnulfinger': {'match': {'collection': 'form_lit_chart-arnulfinger'}},
                                      '<b>Herrscherurkunden</b>: Codice Diplomatico Longobardo I': {'match': {'collection': 'form_lit_chart-langobardisch_1'}},
                                      '<b>Herrscherurkunden</b>: Codice Diplomatico Longobardo III,1': {'match': {'collection': 'form_lit_chart-langobardisch'}},
                                      '<b>Herrscherurkunden</b>: Karl der Große': {'match': {'collection': 'form_lit_chart-karl_der_grosse'}},
                                      '<b>Herrscherurkunden</b>: Karlmann': {'match': {'collection': 'form_lit_chart-karlmann_mgh'}},
                                      '<b>Herrscherurkunden</b>: Konrad': {'match': {'collection': 'form_lit_chart-konrad_mgh'}},
                                      '<b>Herrscherurkunden</b>: Lothar II.': {'match': {'collection': 'form_lit_chart-lothar_2'}},
                                      '<b>Herrscherurkunden</b>: Ludwig II.': {'match': {'collection': 'form_lit_chart-ludwig_2'}},
                                      '<b>Herrscherurkunden</b>: Ludwig der Jüngere': {'match': {'collection': 'form_lit_chart-ludwig_der_juengere'}},
                                      '<b>Herrscherurkunden</b>: Merowinger': {'match': {'collection': 'form_lit_chart-merowinger1'}},
                                      '<b>Herrscherurkunden</b>: Pippin III.': {'match': {'collection': 'form_lit_chart-pippin_3'}},
                                      '<b>Herrscherurkunden</b>: Rudolf I.': {'match': {'collection': 'form_lit_chart-rudolf_1_mgh'}},
                                      '<b>Herrscherurkunden</b>: Rudolf II.': {'match': {'collection': 'form_lit_chart-rudolf_2_mgh'}},
                                      '<b>Herrscherurkunden</b>: Rudolf III.': {'match': {'collection': 'form_lit_chart-rudolf_3'}},
                                      '<b>Lorsch</b>: Lorsch': {'match': {'collection': 'form_lit_chart-lorsch'}},
                                      '<b>Luzern</b>: Luzern': {'match': {'collection': 'form_lit_chart-luzern'}},
                                      '<b>Marculf</b>: Marculf': {'match': {'collection': 'form_lit_chart-marculf'}},
                                      '<b>Mondsee</b>: Mondsee': {'match': {'collection': 'form_lit_chart-mondsee'}},
                                      '<b>Papsturkunden</b>: Papsturkunden Frankreich': {'match': {'collection': 'form_lit_chart-papsturkunden_frankreich'}},
                                      '<b>Passau</b>: Passau': {'match': {'collection': 'form_lit_chart-passau'}},
                                      '<b>Rätien</b>: Rätien': {'match': {'collection': 'form_lit_chart-raetien'}},
                                      '<b>Redon</b>: Cartulaire de Redon': {'match': {'collection': 'form_lit_chart-redon'}},
                                      '<b>Regensburg</b>: Regensburg': {'match': {'collection': 'form_lit_chart-regensburg'}},
                                      '<b>Rheinland</b>: Mittelrheinisch': {'match': {'collection': 'form_lit_chart-mittelrheinisch'}},
                                      '<b>Rheinland</b>: Rheinisch': {'match': {'collection': 'form_lit_chart-rheinisch'}},
                                      '<b>Salzburg</b>: Salzburg': {'match': {'collection': 'form_lit_chart-salzburg'}},
                                      '<b>Schäftlarn</b>: Schäftlarn': {'match': {'collection': 'form_lit_chart-schaeftlarn'}},
                                      '<b>Sens</b>: Sens': {'match': {'collection': 'form_lit_chart-sens'}},
                                      '<b>Stavelot/Malmedy</b>: Stavelot-Malmedy': {'match': {'collection': 'form_lit_chart-stavelot_malmedy'}},
                                      '<b>St. Gallen</b>: St. Gallen': {'match': {'collection': 'form_lit_chart-stgallen'}},
                                      "<b>Touraine</b>: Accensement d'une vigne de Marmoutier": {'match': {'collection': 'form_lit_chart-marmoutier_barthelemy'}},
                                      '<b>Touraine</b>: Accord entre Bonneval et Marmoutier': {'match': {'collection': 'form_lit_chart-bonneval_marmoutier'}},
                                      '<b>Touraine</b>: Cormery (TELMA)': {'match': {'collection': 'form_lit_chart-telma_cormery'}},
                                      '<b>Touraine</b>: Accomodement entre Marmoutier et S.-Martin': {'match': {'collection': 'form_lit_chart-cartier_1841'}},
                                      '<b>Touraine</b>: Eudes': {'match': {'collection': 'form_lit_chart-eudes'}},
                                      '<b>Touraine</b>: Fragments de Saint-Julien de Tours': {'match': {'collection': 'form_lit_chart-tours_st_julien_fragments'}},
                                      '<b>Touraine</b>: Marmoutier Cartulaire blésois': {'match': {'collection': 'form_lit_chart-marmoutier_blésois'}},
                                      '<b>Touraine</b>: Marmoutier - Dunois': {'match': {'collection': 'form_lit_chart-marmoutier_dunois'}},
                                      '<b>Touraine</b>: Marmoutier - Fougères': {'match': {'collection': 'form_lit_chart-marmoutier_fougères'}},
                                      '<b>Touraine</b>: Marmoutier - Manceau': {'match': {'collection': 'form_lit_chart-marmoutier_manceau'}},
                                      '<b>Touraine</b>: Marmoutier - Pour le perche': {'match': {'collection': 'form_lit_chart-marmoutier_pour_le_perche'}},
                                      '<b>Touraine</b>: Marmoutier - Serfs': {'match': {'collection': 'form_lit_chart-marmoutier_serfs'}},
                                      '<b>Touraine</b>: Marmoutier - Trois actes faux ou interpolés': {'match': {'collection': 'form_lit_chart-marmoutier_leveque'}},
                                      '<b>Touraine</b>: Marmoutier - Vendômois': {'match': {'collection': 'form_lit_chart-marmoutier_vendomois'}},
                                      '<b>Touraine</b>: Marmoutier - Vendômois, Appendix': {'match': {'collection': 'form_lit_chart-marmoutier_vendomois_appendix'}},
                                      '<b>Touraine</b>: Marmoutier (TELMA)': {'match': {'collection': 'form_lit_chart-telma_marmoutier'}},
                                      '<b>Touraine</b>: Pancarte Noire': {'match': {'collection': 'form_lit_chart-pancarte_noire'}},
                                      '<b>Touraine</b>: Saint-Julien de Tours': {'match': {'collection': 'form_lit_chart-tours_st_julien_denis'}},
                                      '<b>Touraine</b>: Saint-Martin de Tours (TELMA)': {'match': {'collection': 'form_lit_chart-telma_martin_tours'}},
                                      '<b>Touraine</b>: Un acte faux de Marmoutier': {'match': {'collection': 'form_lit_chart-marmoutier_laurain'}},
                                      '<b>Touraine</b>: Une nouvelle charte de Théotolon': {'match': {'collection': 'form_lit_chart-tours_gasnault'}},
                                      '<b>Touraine</b>: Formeln von Tours': {'match': {'collection': 'form_lit_chart-tours'}},
                                      '<b>Touraine</b>: Tours-Überarbeitung': {'match': {'collection': 'form_lit_chart-tours_ueberarbeitung'}},
                                      '<b>Werden</b>: Werden': {'match': {'collection': 'form_lit_chart-werden'}},
                                      '<b>Wissembourg</b>: Weißenburg': {'match': {'collection': 'form_lit_chart-weissenburg'}},
                                      '<b>Zürich</b>: Zürich': {'match': {'collection': 'form_lit_chart-zuerich'}}}}}
no_date_agg = {'missing': {'field': 'min_date'}}
forgery_agg = {'filter': {'term': {'forgery': True}}}
AGGREGATIONS = {'range': range_agg,
                'corpus': corpus_agg,
                'no_date': no_date_agg,
                'forgeries': forgery_agg,
                'all_docs': {'global': {},
                             'aggs': {
                                 'range': range_agg,
                                 'corpus': corpus_agg,
                                 'no_date': no_date_agg,
                                 'forgeries': forgery_agg
                             }}}
HITS_TO_READER = 10000
LEMMA_INDICES = {'normal': ['lemmas'], 'auto': ['autocomplete_lemmas']}


def check_open_texts(hit_id):
    """ Used for mock tests to return True for highlighting purposes"""
    nemo_app = current_app.config['nemo_app']
    open_text = hit_id in nemo_app.open_texts and hit_id not in nemo_app.closed_texts['closed']
    half_open_text = hit_id in nemo_app.half_open_texts or hit_id in nemo_app.closed_texts['half_closed']
    return open_text, half_open_text


def build_sort_list(sort_str: str) -> Union[str, List[Union[Dict[str, Dict[str, str]], str]]]:
    if sort_str == 'urn':
        return ['sort_prefix', 'urn']
    if sort_str == 'min_date_asc':
        return [{'all_dates': {'order': 'asc', 'mode': 'min'}}, 'urn']
    if sort_str == 'max_date_asc':
        return [{'all_dates': {'order': 'asc', 'mode': 'max'}}, 'urn']
    if sort_str == 'min_date_desc':
        return [{'all_dates': {'order': 'desc', 'mode': 'min'}}, 'urn']
    if sort_str == 'max_date_desc':
        return [{'all_dates': {'order': 'desc', 'mode': 'max'}}, 'urn']
    if sort_str == 'urn_desc':
        return ['sort_prefix', {'urn': {'order': 'desc'}}]


def suggest_word_search(**kwargs) -> Union[List[str], None]:
    """ To enable search-as-you-type for the text search

    :return: sorted set of results
    """
    if 'qSource' not in kwargs or not kwargs['qSource'].startswith('q_'):
        return None
    results = set()
    kwargs['fragment_size'] = 0
    kwargs['corpus'] = kwargs['corpus'].split(' ')
    posts, total, aggs, prev_search = advanced_query_index(per_page=1000, **kwargs)
    highlight_field = kwargs['query_dict'][kwargs['qSource']]['search_field']
    s = kwargs['query_dict'][kwargs['qSource']]['q']
    if '*' in s or '?' in s:
        return None
    regex_search_string = PRE_TAGS + '.{,' + str(len(PRE_TAGS + POST_TAGS) * len(re.findall(r'\w+', s)) + 40) + '}(?=\s|$)'
    for post in posts:
        sents = post['highlight'][highlight_field]
        for sent in sents:
            results.update([re.sub(r'{}|{}|[{}]'.format(PRE_TAGS, POST_TAGS, punctuation), '', x) for x in re.findall(r'{}'.format(regex_search_string), sent)])
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


def lem_highlight_to_text(args_plus_results: List[List[Union[str, Dict]]] = None,
                          result_ids: Set[Tuple[str, str]] = None,
                          download_id: str = '') -> Tuple[List[Dict[str, Union[str, list]]], Set[str]]:
    """ Transfer ElasticSearch highlighting from segments in the lemma field to segments in the text field

    :param search:
    :param q:
    :param ordered_terms:
    :param slop:
    :param regest_field:
    :return:
    """
    # Experimental highlighter does not work with span queries so it is out of the question.
    if len(result_ids) == 0:
        return [], set()
    if download_id:
        current_app.redis.set(download_id, '20%')
    nemo_app = current_app.config['nemo_app']
    id_dict = dict()
    all_highlighted_terms = set()
    mvectors_body = {'docs': [{'_index': h[1], '_id': h[0], 'term_statistics': False, 'field_statistics': False} for h in result_ids]}
    corp_vectors = dict()
    for d in current_app.elasticsearch.mtermvectors(**mvectors_body)['docs']:
        corp_vectors[d['_id']] = {'term_vectors': d['term_vectors']}
    if download_id:
        current_app.redis.set(download_id, '50%')
    for query_terms, query_results in args_plus_results:
        for list_index, hit in enumerate(query_results['hits']['hits']):
            hit_highlight_positions = list()
            open_text, half_open_text = check_open_texts(hit['_id'])
            show_regest = (open_text and not half_open_text) or nemo_app.check_project_team() is True
            text = hit['_source']['text']
            sentences = []
            sentence_spans = []
            regest_sents = []
            part_sentences = []
            other_sentences = []
            vectors = corp_vectors[hit['_id']]['term_vectors']
            if query_terms.get('compare_field', None) and query_terms['compare_field'] not in vectors:
                continue
            for s_field in hit['highlight']:
                if s_field in ('text', 'lemmas'):
                    highlight_field = s_field
                    if s_field == 'lemmas':
                        highlight_field = 'text'
                    highlight_offsets = dict()
                    for x in (highlight_field, s_field, query_terms['compare_field']):
                        if x:
                            highlight_offsets[x] = dict()
                    if s_field in [highlight_field, query_terms['compare_field']]:
                        for k, v in vectors[s_field]['terms'].items():
                            for o in v['tokens']:
                                highlight_offsets[s_field][o['position']] = (o['start_offset'], o['end_offset'], k)
                    if s_field != highlight_field:
                        for k, v in vectors[highlight_field]['terms'].items():
                            for o in v['tokens']:
                                highlight_offsets[highlight_field][o['position']] = (o['start_offset'], o['end_offset'], k)
                    if query_terms['compare_field'] and query_terms['compare_field'] not in [highlight_field, s_field]:
                        for k, v in vectors[query_terms['compare_field']]['terms'].items():
                            for o in v['tokens']:
                                highlight_offsets[query_terms['compare_field']][o['position']] = (o['start_offset'], o['end_offset'], k)
                    highlighted_words = set(query_terms['q'].split())
                    for highlight in hit['highlight'][s_field]:
                        for m in re.finditer(r'{}(\w+){}'.format(PRE_TAGS, POST_TAGS), highlight):
                            highlighted_words.add(m.group(1).lower())
                    all_highlighted_terms.update(highlighted_words)
                    if ' ' in query_terms['q']:
                        q_words = query_terms['q'].split()
                        positions = {k: [] for k in q_words}
                        for token in q_words:
                            terms = {token}
                            u_term = token
                            if s_field != 'lemmas':
                                u_term = re.sub(r'[ij]', '[ij]', re.sub(r'(?<![uv])[uv](?![uv])', r'[uv]', re.sub(r'w|uu|uv|vu|vv', '(w|uu|vu|uv|vv)', token)))
                            if u_term == token:
                                if re.search(r'[?*]', token):
                                    terms = set()
                                    new_token = token.replace('?', '\\w').replace('*', '\\w*')
                                    for term in highlighted_words:
                                        if re.fullmatch(r'{}'.format(new_token), term):
                                            terms.add(term)
                                elif query_terms['fuzziness'] != '0':
                                    terms = set()
                                    if query_terms['fuzziness'] == 'AUTO':
                                        fuzz = min(len(token) // 3, 2)
                                    else:
                                        fuzz = int(query_terms['fuzziness'])
                                    for term in highlighted_words:
                                        if distance(term, token) <= fuzz:
                                            terms.add(term)
                            else:
                                new_token = u_term.replace('?', '.').replace('*', '.+')
                                for term in highlighted_words:
                                    if re.fullmatch(r'{}'.format(new_token), term):
                                        terms.add(term)
                                if not re.search(r'[?*]', token) and query_terms['fuzziness'] != 0:
                                    fuzz_terms = set()
                                    if query_terms['fuzziness'] == 'AUTO':
                                        fuzz = min(len(token) // 3, 2)
                                    else:
                                        fuzz = int(query_terms['fuzziness'])
                                    for term, t in product(highlighted_words, terms):
                                        if distance(term, token) <= fuzz:
                                            terms.add(term)
                                    terms.update(fuzz_terms)
                            for w in terms:
                                if s_field == 'lemmas':
                                    if w in vectors['lemmas']['terms']:
                                        positions[token] += [i['position'] for i in vectors['lemmas']['terms'][w]['tokens']]
                                    for other_lem in nemo_app.lem_to_lem_mapping.get(w, {}):
                                        if other_lem in vectors['lemmas']['terms']:
                                            positions[token] += [i['position'] for i in vectors['lemmas']['terms'][other_lem]['tokens']]
                                    positions[token] = sorted(positions[w])
                                else:
                                    if w in vectors[s_field]['terms']:
                                        positions[token] += [i['position'] for i in vectors[s_field]['terms'][w]['tokens']]
                        search_range_start = int(query_terms['slop']) + len(q_words)
                        search_range_end = int(query_terms['slop']) + len(q_words) + 1
                        if query_terms['ordered_terms']:
                            search_range_start = -1
                        for pos in positions[q_words[0]]:
                            index_range = range(max(pos - search_range_start - 1, 0), pos + search_range_end + 1)
                            used_q_words = {q_words[0]}
                            matching_positions = [[pos]]
                            # This now works for 'non est incognetum' in Angers 5 'HIC EST Dum non est incognetum'
                            # Need to write a test for it
                            for w in q_words[1:]:
                                this_pos = list()
                                for next_pos in positions[w]:
                                    if next_pos in index_range and next_pos not in this_pos:
                                        this_pos.append(next_pos)
                                        used_q_words.add(w)
                                matching_positions.append(this_pos)
                            for span in product(*matching_positions):
                                span = set(span)
                                compare_true = True
                                if query_terms['compare_term']:
                                    compare_true = False
                                    for position in span:
                                        if highlight_offsets[query_terms['compare_field']][position][-1] in query_terms['compare_term'] + [x for y in query_terms['compare_term'] for x in nemo_app.lem_to_lem_mapping.get(y, None)]:
                                            compare_true = True
                                            break
                                if set(q_words) == used_q_words and len(span) == len(q_words) and compare_true:
                                    ordered_span = sorted(span)
                                    if (ordered_span[-1] - ordered_span[0]) - (len(ordered_span) - 1) <= int(query_terms['slop']):
                                        hit_highlight_positions.append(ordered_span)
                                        start_offsets = [highlight_offsets[highlight_field][x][0] for x in ordered_span]
                                        end_offsets = [highlight_offsets[highlight_field][x][1] - 1 for x in ordered_span]
                                        start_index = highlight_offsets[highlight_field][max(0, ordered_span[0] - 10)][0]
                                        end_index = highlight_offsets[highlight_field][min(len(highlight_offsets[highlight_field]) - 1, ordered_span[-1] + 10)][1] + 1
                                        sentence = ''
                                        for i, x in enumerate(text[start_index:end_index]):
                                            if i + start_index in start_offsets and i + start_index in end_offsets:
                                                sentence += PRE_TAGS + x + POST_TAGS
                                            elif i + start_index in start_offsets:
                                                sentence += PRE_TAGS + x
                                            elif i + start_index in end_offsets:
                                                sentence += x + POST_TAGS
                                            else:
                                                sentence += x
                                        marked_sent = Markup(sentence)
                                        if marked_sent not in sentences:
                                            sentences.append(marked_sent)
                                            sentence_spans.append(range(max(0, ordered_span[0] - 10),
                                                                        min(len(highlight_offsets[highlight_field]), ordered_span[-1] + 11)))
                    else:
                        terms = highlighted_words
                        positions = set()
                        for w in terms:
                            if s_field == 'lemmas':
                                if w in vectors['lemmas']['terms']:
                                    positions.update([i['position'] for i in vectors['lemmas']['terms'][w]['tokens']])
                                for other_lem in nemo_app.lem_to_lem_mapping.get(w, {}):
                                    if other_lem in vectors['lemmas']['terms']:
                                        positions.update([i['position'] for i in vectors['lemmas']['terms'][other_lem]['tokens']])
                            else:
                                if w in vectors[s_field]['terms']:
                                    positions.update([i['position'] for i in vectors[s_field]['terms'][w]['tokens']])
                        hit_highlight_positions = sorted(positions)
                        for pos in hit_highlight_positions:
                            if query_terms['compare_term'] and highlight_offsets[query_terms['compare_field']][pos][-1] not in query_terms['compare_term'] + [x for y in query_terms['compare_term'] for x in nemo_app.lem_to_lem_mapping.get(y, None)]:
                                continue
                            start_offset = highlight_offsets[highlight_field][pos][0]
                            end_offset = highlight_offsets[highlight_field][pos][1] - 1
                            start_index = highlight_offsets[highlight_field][max(0, pos - 10)][0]
                            end_index = highlight_offsets[highlight_field][min(len(highlight_offsets[highlight_field]) - 1, pos + 10)][1] + 1
                            sentence = ''
                            for i, x in enumerate(text[start_index:end_index]):
                                if i + start_index == start_offset and i + start_index == end_offset:
                                    sentence += PRE_TAGS + x + POST_TAGS
                                elif i + start_index == start_offset:
                                    sentence += PRE_TAGS + x
                                elif i + start_index == end_offset:
                                    sentence += x + POST_TAGS
                                else:
                                    sentence += x
                            sentences.append(Markup(sentence))
                            sentence_spans.append(range(max(0, pos - 10), min(len(highlight_offsets[highlight_field]), pos + 11)))
                elif 'regest' in s_field:
                    if show_regest is False:
                        regest_sents = [_('Regest nicht zugänglich.')]
                    else:
                        regest_sents = [Markup(highlight_segment(x)) for x in hit['highlight'][s_field]]
                if download_id and list_index % 500 == 0:
                    current_app.redis.set(download_id, str(50 + floor((list_index / len(query_results['hits']['hits'])) * 50)) + '%')

            ordered_sentences = list()
            ordered_sentence_spans = list()
            for x, y in sorted(zip(sentences, sentence_spans), key=lambda z: (z[1].start, z[1].stop)):
                ordered_sentences.append(x)
                ordered_sentence_spans.append(y)
            if ordered_sentences or regest_sents:
                if not open_text and nemo_app.check_project_team() is False:
                    ordered_sentences = [_('Text nicht zugänglich.')]
                    ordered_sentence_spans = [range(0, 1)]
                if hit['_id'] in id_dict:
                    id_dict[hit['_id']]['sents'] += ordered_sentences
                    id_dict[hit['_id']]['sentence_spans'] += ordered_sentence_spans
                    id_dict[hit['_id']]['regest_sents'] += regest_sents
                else:
                    id_dict[hit['_id']] = {'id': hit['_id'],
                                           'info': hit['_source'],
                                           'sents': ordered_sentences,
                                           'sentence_spans': ordered_sentence_spans,
                                           'title': hit['_source']['title'],
                                           'regest_sents': regest_sents,
                                           'highlight': ordered_sentences
                                           }

    ids = [v for v in id_dict.values()]
    if download_id:
        current_app.redis.setex(download_id, 60, '100%')
    return ids, all_highlighted_terms


def advanced_query_index(corpus: list = None,
                         query_dict: dict = None,
                         page: int = 1,
                         per_page: int = 10000,
                         year: int = 0,
                         month: int = 0,
                         day: int = 0,
                         year_start: int = 0,
                         month_start: int = 0,
                         day_start: int = 0,
                         year_end: int = 0,
                         month_end: int = 0,
                         day_end: int = 0,
                         date_plus_minus: int = 0,
                         exclusive_date_range: str = "False",
                         composition_place: str = '',
                         sort: str = 'urn',
                         special_days: list = None,
                         old_search: bool = False,
                         source: str = 'advanced',
                         search_id: str = '',
                         forgeries: str = 'include',
                         bool_operator: str = 'must',
                         qSource: str = '',
                         **kwargs) -> Tuple[List[Dict[str, Union[str, list, dict]]],
                                            int,
                                            dict,
                                            List[Dict[str, Union[str, List[str]]]]]:
    # all parts of the query should be appended to the 'must' list. This assumes AND and not OR at the highest level
    if not current_app.elasticsearch:
        return [], 0, {}, []
    nemo_app = current_app.config['nemo_app']
    prev_search = None
    if search_id:
        search_id = 'search_progress_' + search_id
    old_sort = sort
    sort = build_sort_list(sort)
    if old_search is False:
        session.pop('previous_search', None)
    base_body_template = dict({"query": {"bool": {'must': []}}, "sort": sort, 'from': (page - 1) * per_page,
                               'size': per_page, 'highlight': {'number_of_fragments': 0,
                                                               'fields': {'text': {}},
                                                               'pre_tags': [PRE_TAGS],
                                                               'post_tags': [POST_TAGS],
                                                               'encoder': 'html'}})
    if 'q_1' not in query_dict and source == 'simple':
        return [], 0, {}, []
    if corpus is None or not any(corpus) or corpus in [['all'], 'all']:
        corpus = ['form_lit_chart']
    if special_days is None:
        special_days = []
    search_highlight = set()
    args_plus_results = list()
    searched_templates = list()

    # Function to control the replacement of uu, vu, vv, uv, and w when in brackets
    def repl(m):
        first = ''
        if m.group(1):
            if len(m.group(1)) > 1:
                first = '[' + m.group(1) + ']|'
            else:
                first = m.group(1) + '|'
        second = 'w|uu|vu|uv|vv'
        third = '|[' + m.group(2) + m.group(3) + ']'
        return '(' + ''.join([first, second, third]) + ')'
    if 'elexicon' in corpus:
        elex_search = deepcopy(base_body_template)
        elex_search['highlight'] = {'fields': {'text': {}},
                                    'pre_tags': [PRE_TAGS],
                                    'post_tags': [POST_TAGS],
                                    'encoder': 'html'}
        corpus = ['elexicon']
        clauses = []
        for query_key, query_vals in query_dict.items():
            query_clauses = []
            elex_search['highlight']['fields'][query_vals['search_field']] = {}
            if 'autocomplete' in query_vals['search_field']:
                elex_search['highlight']['number_of_fragments'] = 0
            for term in query_vals['q'].split():
                if '*' in term or '?' in term:
                    query_clauses.append({'wildcard': {query_vals['search_field']: {'value': term}}})
                else:
                    query_clauses.append({'match': {query_vals['search_field']: {'query': term, 'fuzziness': query_vals['fuzziness']}}})
            clauses.append({'bool': {'must': query_clauses}})
        elex_search['query']['bool']['must'] = clauses

        searched_templates.append(elex_search)
        search = [current_app.elasticsearch.search(index=corpus,
                                                   **elex_search)]
    else:
        if composition_place:
            base_body_template['query']['bool']['must'].append({'match': {'comp_ort': composition_place}})
        if forgeries == 'exclude':
            base_body_template['query']['bool']['must'].append({'term': {'forgery': False}})
        elif forgeries == 'only':
            base_body_template['query']['bool']['must'].append({'term': {'forgery': True}})
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
            base_body_template["query"]["bool"]["must"].append(date_template)
        elif year_start or month_start or day_start or year_end or month_end or year_end:
            if exclusive_date_range != 'False':
                base_body_template["query"]["bool"]["must"] += build_spec_date_range_template(year_start, month_start,
                                                                                         day_start, year_end,
                                                                                         month_end, day_end)
            else:
                base_body_template["query"]["bool"]["must"].append(build_date_range_template(year_start, month_start, day_start,
                                                                                        year_end, month_end, day_end))
        if any(special_days):
            s_d_template = {'bool': {'should': []}}
            for s_d in special_days:
                s_d_template['bool']['should'].append({'match': {'days': s_d}})
            base_body_template["query"]["bool"]["must"].append(s_d_template)
        # I may need to run each query separately and then bring the results together so that I can do things like
        # proper name searches.
        for query_key, query_vals in query_dict.items():
            if not any([query_vals['q'], query_vals['proper_name']]):  # , query_vals['formulaic_parts']]):
                continue
            search_part_template = deepcopy(base_body_template)
            search_highlight.add(query_vals['search_field'])
            for s_highlight in search_highlight:
                search_part_template['highlight']['fields'][s_highlight] = {}
            query_vals['ordered_terms'] = True
            if query_vals['in_order'] == 'False':
                query_vals['ordered_terms'] = False
            if query_vals['search_field'] == 'lemmas':
                query_vals['fuzziness'] = '0'
                if ('*' in query_vals['q'] or '?' in query_vals['q']) and query_vals['regex_search'] == 'False':
                    flash(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."))
                    return [], 0, {}, []
            if query_vals['proper_name'] != '':
                query_vals['proper_name'] = re.split(r'\+|\s+', query_vals['proper_name'])
            else:
                query_vals['proper_name'] = []
            if query_vals['proper_name'] and query_vals['q'] == '':
                query_vals['search_field'] = 'lemmas'
                query_vals['compare_term'] = []
                query_vals['compare_field'] = ''
                search_part_template['highlight']['fields'].update({'lemmas': {}})
                clauses = list()
                for term in query_vals['proper_name']:
                    sub_clauses = [{'span_multi': {'match': {'fuzzy': {"lemmas": {"value": term, "fuzziness": query_vals['fuzziness']}}}}}]
                    for other_lem in nemo_app.lem_to_lem_mapping[term]:
                        sub_clauses.append({'span_multi': {'match': {'fuzzy': {"lemmas": {"value": other_lem, "fuzziness": query_vals['fuzziness']}}}}})
                    clauses += sub_clauses
                search_part_template['query']['bool']['must'].append({'bool': {'should': clauses, 'minimum_should_match': 1}})
            elif query_vals['q']:
                query_vals['compare_term'] = []
                query_vals['compare_field'] = ''
                if query_vals['proper_name']:
                    query_vals['compare_term'] = query_vals['proper_name']
                    query_vals['compare_field'] = 'lemmas'
                clauses = []
                for term in query_vals['q'].split():
                    u_term = term
                    if query_vals['search_field'] not in ['lemmas', 'regest', 'autocomplete', 'autocomplete_lemmas', 'autocomplete_regest']:
                        if query_vals['regex_search'] == 'True':
                            # Replace these characters if they are within brackets
                            temp_term = re.sub(r'[ij](?=[^\[]*\])',
                                               r'ij',
                                               re.sub(r'(?<![uv])[uv](?![uv])(?=[^\[]*\])',
                                                      r'uv',
                                                      re.sub(r'\[([^\]]*)(w|uu|uv|vu|vv)([^\[]*)\]',
                                                             repl,
                                                             term)))
                            # And then to replace the characters if they are not in brackets
                            u_term = re.sub(r'[ij](?![^[]*])',
                                            '[ij]',
                                            re.sub(r'(?<![uv])[uv](?![uv])(?![^[]*])',
                                                   r'[uv]',
                                                   re.sub(r'(w|uu|uv|vu|vv)(?![^\(]*\))(?![^[]*])',
                                                          '(w|uu|vu|uv|vv)',
                                                          temp_term)))
                        else:
                            u_term = re.sub(r'[ij]', '[ij]', re.sub(r'(?<![uv])[uv](?![uv])', r'[uv]', re.sub(r'w|uu|uv|vu|vv', '(w|uu|vu|uv|vv)', term)))
                    exclude_ending = ''
                    if query_vals['exclude_q']:
                        exclude_ending = '&~({})'.format(query_vals['exclude_q'].replace('*', '.+').replace('?', '.'))
                    if query_vals['regex_search'] == 'True':
                        clauses.append([{'span_multi': {'match': {'regexp': {query_vals['search_field']: {'value': u_term + exclude_ending,
                                                                                            'flags': 'ALL',
                                                                                            'case_insensitive': True}}}}}])
                    elif '*' in term or '?' in term:
                        clauses.append([{'span_multi': {'match': {'regexp': {query_vals['search_field']: {'value': u_term.replace('*', '.+').replace('?', '.') + exclude_ending,
                                                                                            'flags': 'ALL',
                                                                                            'case_insensitive': True}}}}}])
                    else:
                        if query_vals['search_field'] == 'lemmas' and term in nemo_app.lem_to_lem_mapping:
                            sub_clauses = [{'span_multi': {'match': {'fuzzy': {query_vals['search_field']: {"value": term, "fuzziness": query_vals['fuzziness']}}}}}]
                            for other_lem in nemo_app.lem_to_lem_mapping[term]:
                                sub_clauses.append({'span_multi': {'match': {'fuzzy': {query_vals['search_field']: {"value": other_lem, "fuzziness": query_vals['fuzziness']}}}}})
                            clauses.append(sub_clauses)
                        else:
                            if u_term + exclude_ending != term:
                                words = [u_term]
                                sub_clauses = {'span_or': {'clauses': []}}
                                if query_vals['fuzziness'] == 'AUTO':
                                    if len(term) < 3:
                                        term_fuzz = 0
                                    elif len(term) < 6:
                                        term_fuzz = 1
                                    else:
                                        term_fuzz = 2
                                else:
                                    term_fuzz = int(query_vals['fuzziness']) if query_vals['fuzziness'] else 0
                                if term_fuzz != 0:
                                    suggest_body = {'suggest':
                                                        {'fuzzy_suggest':
                                                             {'text': term,
                                                              'term':
                                                                  {'field': query_vals['search_field'],
                                                                   'suggest_mode': 'always',
                                                                   'max_edits': term_fuzz,
                                                                   'min_word_length': 3,
                                                                   'max_term_freq': 20000}}}}
                                    suggests = current_app.elasticsearch.search(index=corpus, **suggest_body)
                                    if 'suggest' in suggests:
                                        for s in suggests['suggest']['fuzzy_suggest'][0]['options']:
                                            words.append(re.sub(r'[ij]', '[ij]', re.sub(r'(?<![uv])[uv](?![uv])', r'[uv]', re.sub(r'w|uu|uv|vu|vv', '(w|uu|vu|uv|vv)', s['text']))))
                                for w in words:
                                    sub_clauses['span_or']['clauses'].append({'span_multi': {'match': {'regexp': {query_vals['search_field']: {
                                        'value': w + exclude_ending, 'flags': 'ALL', 'case_insensitive': True}}}}})
                                clauses.append([sub_clauses])
                            else:
                                clauses.append([{'span_multi': {'match': {'fuzzy': {query_vals['search_field']: {"value": term, "fuzziness": query_vals['fuzziness']}}}}}])
                    bool_clauses = []
                    for clause in product(*clauses):
                        bool_clauses.append({'span_near': {'clauses': list(clause), 'slop': query_vals['slop'], 'in_order': query_vals['ordered_terms']}})
                if source == 'simple':
                    regest_clauses = []
                    for term in query_vals['q'].split():
                        if '*' in term or '?' in term:
                            regest_clauses.append({'wildcard': {'regest': {'value': term}}})
                        else:
                            regest_clauses.append({'match': {'regest': {'query': term, 'fuzziness': query_vals['fuzziness']}}})
                    bool_clauses.append({'bool': {'must': regest_clauses}})
                    search_part_template['highlight']['fields'].update({'regest': {}})
                search_part_template['query']['bool']['must'].append({'bool': {'should': bool_clauses, 'minimum_should_match': 1}})
            # elif query_vals['formulaic_parts']:
            #     bool_clauses = [{'exists': {'field': x}} for x in query_vals['formulaic_parts'].split('+')]
            #     for form_part in query_vals['formulaic_parts'].split('+'):
            #         search_part_template['highlight']['fields'][form_part]['no_match_size'] = 1000
            #     search_part_template['query']['bool']['must'].append({'bool': {'should': bool_clauses, 'minimum_should_match': 1}})

            searched_templates.append(search_part_template)

            args_plus_results.append([query_vals, current_app.elasticsearch.search(index=corpus, **search_part_template)])

        if args_plus_results:
            combined_results = list()
            for v, r in args_plus_results:
                combined_results.append({(hit['_id'], hit['_index']) for hit in r['hits']['hits']})
            shared_ids = combined_results[0]
            if len(args_plus_results) > 1:
                if len(combined_results) > 1:
                    if bool_operator == 'must':
                        for single_results in combined_results[1:]:
                            shared_ids = shared_ids.intersection(single_results)
                        for i, r in enumerate(args_plus_results):
                            pruned_hits = list()
                            for h in r[1]['hits']['hits']:
                                if (h['_id'], h['_index']) in shared_ids:
                                    pruned_hits.append(h)
                            args_plus_results[i][1]['hits']['hits'] = pruned_hits
                    elif bool_operator == 'must_not':
                        for single_results in combined_results[1:]:
                            shared_ids = shared_ids.difference(single_results)
                        pruned_hits = list()
                        for h in args_plus_results[0][1]['hits']['hits']:
                            if (h['_id'], h['_index']) in shared_ids:
                                pruned_hits.append(h)
                        args_plus_results[0][1]['hits']['hits'] = pruned_hits
                        args_plus_results = [args_plus_results[0]]
                    # If bool_operator is should, all results from all searches should be used
                    else:
                        shared_ids.update(*combined_results[1:])
            first = []
            second = []
            for q_v, q_r in args_plus_results:
                if 'autocomplete' in q_v['search_field']:
                    first.append(q_r)
                else:
                    second.append(q_r)
            search = first + second
        else:
            searched_templates.append(base_body_template)
            search = [current_app.elasticsearch.search(index=corpus, **base_body_template)]
    if qSource:
        ids = [{'id': hit['_id'],
                'info': hit['_source'],
                'sents': [],
                'regest_sents': [],
                'highlight': hit['highlight']}
               for hit in search[0]['hits']['hits']]
    elif corpus == ['elexicon']:
        def sort_lexicon(d):
            keywords = set(re.sub(r'[{}]'.format(punctuation), ' ',
                                  ' '.join([d['info']['title'], d['info']['keywords']]).lower()).split())
            found_words = set()
            for key_sent in d['sents']:
                found_words.update([x.lower() for x in re.findall(r'(?<=<strong>)\w+(?=</strong>)', key_sent)])
            return (found_words.isdisjoint(keywords), d['id'])
        ids = [{'id': hit['_id'],
                'info': hit['_source'],
                'sents': [Markup(x) for x in hit['highlight']['text']] if 'highlight' in hit and 'text' in hit['highlight'] else [],
                'regest_sents': [],
                'highlight': []}
               for hit in search[0]['hits']['hits']]
        ids = sorted(ids, key=sort_lexicon)
    elif args_plus_results:
        # The following lines transfer "highlighting" to the text field so that the user sees the text instead of
        # a series of lemmata.
        # Weeding out how each hit is highlighted needs to be done by the lem_highlight_to_text function
        # Essentially it will need to cycle through the key, value pairs in every hit and
        # implement the process below depending on what the key is
        # Change the highlight parameters for each field to include number_of_fragments: 0. That will return the whole field
        # Then lem_highlight_to_text will just need to find the position of the highlighted terms and then transfer if need be
        ids, g.highlighted_terms = lem_highlight_to_text(args_plus_results=args_plus_results,
                                                         result_ids=shared_ids,
                                                         download_id=search_id)
    else:
        ids = [{'id': hit['_id'], 'info': hit['_source'], 'sents': [], 'regest_sents': [], 'highlight': []}
               for hit in search[0]['hits']['hits']]
    aggregations = {}
    if not qSource:
        if old_search is False:
            prev_search = ids
        agg_search_body = {'query': {'ids': {'values': [x['id'] for x in ids]}}, 'size': 0, 'aggs': AGGREGATIONS}
        aggregations = current_app.elasticsearch.search(index=corpus,
                                                        **agg_search_body)['aggregations']
    if current_app.config["SAVE_REQUESTS"]:
        q = []
        for k in ('q_1', 'q_2', 'q_3', 'q_4'):
            d_vals = []
            for s_arg in ("search_field",
                          "q",
                          "fuzziness",
                          "in_order",
                          "slop",
                          "regex_search",
                          "exclude_q",
                          # "formulaic_parts",
                          "proper_name"):
                d_vals.append(str('+'.join(query_dict[k][s_arg]) if isinstance(query_dict[k][s_arg], list) else query_dict[k][s_arg]).replace(' ', '+'))
            q.append('&'.join(d_vals))

        req_name = "{corpus}&{q}&{y}&" \
                   "{m}&{d}&{y_s}&{m_s}&{d_s}&{y_e}&" \
                   "{m_e}&{d_e}&{d_p_m}&" \
                   "{e_d_r}&{c_p}&" \
                   "{sort}&{spec_days}&" \
                   "{forgeries}&{source}&{bool_op}".format(
            corpus='+'.join(corpus) if isinstance(corpus, list) else corpus,
            q='&'.join(q), y=year, m=month, d=day, y_s=year_start,
            m_s=month_start, d_s=day_start, y_e=year_end,
            m_e=month_end, d_e=day_end, d_p_m=date_plus_minus, e_d_r=exclusive_date_range, c_p=composition_place,
            sort=old_sort, spec_days='+'.join(special_days), forgeries=forgeries, source=source, bool_op=bool_operator)
        req_name = req_name.replace('/', '-')
        fake = FakeElasticsearch(req_name, "advanced_search")
        fake.save_request(searched_templates)
        # Remove the textual parts from the results
        fake.save_ids([{"id": x['id']} for x in ids])
        fake.save_response(search)
        fake.save_aggs(aggregations)
    return ids, len(ids), aggregations, prev_search


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
