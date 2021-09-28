from flask import redirect, request, url_for, g, flash, current_app, session, Response
from flask_babel import _
from math import ceil
from .Search import advanced_query_index, suggest_word_search, AGGREGATIONS, lem_highlight_to_text
from .forms import AdvancedSearchForm, FORM_PARTS
from formulae.search import bp
from json import dumps
import re
from io import BytesIO
from reportlab.platypus import Paragraph, SimpleDocTemplate
from reportlab.lib.styles import getSampleStyleSheet
from datetime import date
from math import floor
from json import load
import roman
from copy import deepcopy


CORP_MAP = {y['match']['collection']: x for x, y in AGGREGATIONS['corpus']['filters']['filters'].items()}


def build_search_args(search_args: dict) -> dict:
    """
    Transfer request args to an appropriately keyed and valued dictionary
    :param search_args: the raw args from request.args
    :return: the converted args that can be sent to search.Search
    """
    if 'corpus' not in search_args:
        search_args['corpus'] = 'all'
    if 'bool_operator' not in search_args:
        search_args['bool_operator'] = 'must'
    if 'q' in search_args:
        search_args['q_1'] = search_args.get('q', '').lower()
    if 'search_field' in search_args:
        search_args['search_field_1'] = search_args.get('search_field', 'text')
    if 'fuzziness' in search_args:
        search_args['fuzziness_1'] = search_args.get('fuzziness', '')
    if 'in_order' in search_args:
        search_args['in_order_1'] = search_args.get('in_order', '')
    if 'slop' in search_args:
        search_args['slop_1'] = search_args.get('slop', '')
    lemma_search = search_args.get('lemma_search', '')
    if lemma_search in ['y', 'True', True]:
        search_args['search_field_1'] = 'lemmas'
    if search_args.get('regest_q', ''):
        search_args['q_2'] = search_args['regest_q'].lower()
        search_args['search_field_2'] = 'regest'
    if search_args.get('exclude_q', ''):
        search_args['exclude_q_1'] = search_args['exclude_q'].lower()
    if 'formulaic_parts' in search_args:
        search_args['formulaic_parts_1'] = search_args.get('formulaic_parts', '')
    if 'regex_search' in search_args:
        regex_search = search_args.get('regex_search')
        search_args['regex_search_1'] = 'False'
        if regex_search in ['y', 'True', True]:
            search_args['regex_search_1'] = 'True'
    if 'proper_name' in search_args:
        if isinstance(search_args['proper_name'], list):
            search_args['proper_name_1'] = '+'.join(search_args.get('proper_name')) or ''
        else:
            search_args['proper_name_1'] = search_args.get('proper_name', '')

    for arg, value in search_args.items():
        if ('formulaic_parts' in arg or 'proper_name' in arg) and value:
            if isinstance(value, list):
                search_args[arg] = '+'.join(value)
        elif 'regex_search' in arg:
            if value in ['y', 'True', True]:
                search_args[arg] = 'True'
            else:
                search_args[arg] = 'False'
        elif 'in_order' in arg:
            if value in ['y', 'True', True]:
                search_args[arg] = 'True'
            else:
                search_args[arg] = 'False'
    if isinstance(search_args['corpus'], list):
        search_args['corpus'] = '+'.join(search_args.get("corpus")) or 'all'
    if isinstance(search_args.get('special_days', ''), list):
        search_args['special_days'] = '+'.join(search_args.get('special_days')) or ''
    return search_args


def make_query_dict(search_args: dict = None) -> dict:
    query_keys = [x for x in search_args.keys() if x.startswith('q_')]
    query_val_keys = [("in_order", 'False'),
                      ("regex_search", False),
                      ("proper_name", ''),
                      ("formulaic_parts", ''),
                      ("slop", 0),
                      ("fuzziness", 0),
                      ("search_field", 'text'),
                      ("exclude_q", '')]
    query_dict = dict()
    for k in query_keys:
        k_num = k.split('_')[-1]
        query_val_dict = {'q': search_args.pop(k, '').lower()}
        for v, val_default in query_val_keys:
            arg_val = search_args.pop(v + '_' + k_num, None)
            query_val_dict[v] = arg_val if arg_val else val_default
        query_dict[k] = query_val_dict
    return query_dict


@bp.route("/simple", methods=["GET"])
def r_simple_search() -> redirect:
    data = deepcopy(g.search_form.data)
    data['q_1'] = data['q_1'].lower()
    lemma_search = data.pop('lemma_search')
    data['search_id'] = data.pop('simple_search_id')
    data['search_field_1'] = data.pop('search_field', 'text')
    if lemma_search in ['y', 'True', True]:
        data['search_field_1'] = 'lemmas'
    corpus = '+'.join(data.pop("corpus"))
    if not g.search_form.validate():
        for k, m in g.search_form.errors.items():
            if k == 'corpus':
                flash(_('Sie müssen mindestens eine Sammlung für die Suche auswählen ("Formeln" und/oder "Urkunden").') + _(' Resultate aus "Formeln" und "Urkunden" werden hier gezeigt.'))
                return redirect(url_for('.r_results', source='simple', corpus='formulae+chartae', **data))
            if k == 'q_1':
                flash(m[0] + _(' Die einfache Suche funktioniert nur mit einem Suchwort.'))
                return ('', 204)
    return redirect(url_for('.r_results', source='simple', corpus=corpus, sort="urn", **data))


@bp.route("/results", methods=["GET"])
def r_results():
    source = request.args.get('source', None)
    # This means that someone simply navigated to the /results page without any search parameters
    if not source:
        return redirect(url_for('InstanceNemo.r_index'))
    template = 'search::search.html'
    posts_per_page = 10000
    page = 1
    corpus = request.args.get('corpus', '').split('+')
    if len(corpus) == 1:
        corpus = corpus[0].split(' ')
    if 'elexicon' in corpus:
        corpus = ['elexicon']
        corps = ['elexicon']
    elif corpus in [['all'], ['formulae', 'chartae'], ['']]:
        corps = [x['id'].split(':')[-1] for x in g.sub_colls['formulae_collection']] + sorted([x['id'].split(':')[-1] for x in g.sub_colls['other_collection']])
    elif corpus == ['formulae']:
        corps = [x['id'].split(':')[-1] for x in g.sub_colls['formulae_collection']]
    elif corpus == ['chartae']:
        corps = sorted([x['id'].split(':')[-1] for x in g.sub_colls['other_collection']])
    else:
        corps = corpus
    g.corpora = [(CORP_MAP[x], x) for x in corps]
    g.form_parts = []
    if request.args.get('formulaic_parts'):
        g.form_parts = [(x, FORM_PARTS[x]) for x in request.args.get('formulaic_parts', '').split('+')]
    special_days = request.args.get('special_days')
    if special_days:
        special_days = special_days.split('+')
        if len(special_days) == 1:
            special_days = special_days[0].split(' ')
    old_search = False
    if request.args.get('old_search', None) == 'True':
        old_search = True
    search_args = build_search_args({x: y for x, y in request.args.items()})
    query_keys = [x for x in search_args.keys() if x.startswith('q_')]
    query_val_keys = [("in_order", 'False'),
                      ("regex_search", False),
                      ("proper_name", ''),
                      ("formulaic_parts", ''),
                      ("slop", 0),
                      ("fuzziness", 0),
                      ("search_field", 'text'),
                      ("exclude_q", '')]
    query_dict = dict()
    for k in query_keys:
        k_num = k.split('_')[-1]
        query_val_dict = {'q': search_args[k].lower()}
        for v, val_default in query_val_keys:
            query_val_dict[v] = search_args.get(v + '_' + k_num) if search_args.get(v + '_' + k_num) else val_default
        query_dict[k] = query_val_dict
    final_search_args = dict(per_page=posts_per_page,
                             page=page,
                             year=int(search_args.get('year')) if search_args.get('year') else 0,
                             month=int(search_args.get('month')) if search_args.get('month') else 0,
                             day=int(search_args.get('day')) if search_args.get('day') else 0,
                             year_start=int(search_args.get('year_start')) if search_args.get('year_start') else 0,
                             month_start=int(search_args.get('month_start', 0)) if search_args.get('month_start') else 0,
                             day_start=int(search_args.get('day_start')) if search_args.get('day_start') else 0,
                             year_end=int(search_args.get('year_end')) if search_args.get('year_end') else 0,
                             month_end=int(search_args.get('month_end')) if search_args.get('month_end') else 0,
                             day_end=int(search_args.get('day_end')) if search_args.get('day_end') else 0,
                             date_plus_minus=int(search_args.get("date_plus_minus")) if search_args.get('date_plus_minus') else 0,
                             corpus=corpus,
                             exclusive_date_range=search_args.get('exclusive_date_range', "False"),
                             composition_place=search_args.get('composition_place', ''),
                             sort=search_args.get('sort', 'urn'),
                             special_days=special_days,
                             old_search=old_search,
                             source=search_args.get('source', 'advanced'),
                             search_id=search_args.get('search_id', ''),
                             forgeries=search_args.get('forgeries', 'include'),
                             query_dict=query_dict,
                             bool_operator=search_args.get('bool_operator', 'must')
                             )
    posts, total, aggs, g.previous_search = advanced_query_index(**final_search_args)
    old_search_args = {k: v for k, v in request.args.items()}
    old_search_args.pop('page', None)
    old_search_args['corpus'] = '+'.join(corpus)
    if 'special_days' in search_args:
        old_search_args['special_days'] = '+'.join(special_days)
    old_search_args.pop('old_search', None)
    if old_search is False:
        g.previous_search_args = old_search_args
        g.previous_aggregations = aggs
        g.previous_search_args['corpus'] = '+'.join(corps)
    inf_to_lemmas = []
    for k, v in sorted(final_search_args['query_dict'].items()):
        if v['search_field'] != 'lemmas':
            search_terms = v.get('q', '').split()
            for token in search_terms:
                terms = {token}
                if re.search(r'[?*]', token):
                    terms = set()
                    new_token = token.replace('?', '\\w').replace('*', '\\w*')
                    for term in getattr(g, 'highlighted_words', session.get('highlighted_words', [])):
                        if re.fullmatch(r'{}'.format(new_token), term):
                            terms.add(term)
                lem_possibilites = set()
                for inflected in terms:
                    try:
                        lem_possibilites.update(current_app.config['nemo_app'].inflected_to_lemma_mapping[inflected])
                    except KeyError:
                        continue
                inf_to_lemmas.append(lem_possibilites)
    if not all(inf_to_lemmas):
        inf_to_lemmas = []
    return current_app.config['nemo_app'].render(template=template, title=_('Suche'), posts=posts, current_page=page,
                                                 url=dict(), open_texts=g.open_texts, total_results=total, aggs=aggs,
                                                 searched_lems=inf_to_lemmas)


@bp.route("/advanced_search", methods=["GET"])
def r_advanced_search():
    def sort_collections(t):
        sort_key = t[0]
        if ": Chartae Latinae" in t[0]:
            key_parts = sort_key.split()
            key_parts[-1] = '{:04}'.format(roman.fromRoman(key_parts[-1]))
            sort_key = ' '.join(key_parts)
        return sort_key
    form = AdvancedSearchForm()
    colls = g.sub_colls
    form.corpus.choices = form.corpus.choices + [(x['id'].split(':')[-1], x['short_title'].strip()) for y in colls.values() for x in y if 'elexicon' not in x['id']]
    coll_cats = dict()
    for k, v in colls.items():
        if k != 'lexicon_entries':
            coll_cats[k] = list()
            for x in v:
                if x['coverage'] != 'None':
                    coll_cats[k].append(('<b>' + x['coverage'] + '</b>: ' + x['short_title'].strip(), x['id'].split(':')[-1], x['lemmatized']))
                else:
                    coll_cats[k].append((x['short_title'].strip(), x['id'].split(':')[-1], x['lemmatized']))
            coll_cats[k] = sorted(coll_cats[k], key=sort_collections)
    ignored_fields = ('exclusive_date_range',
                      'fuzziness',
                      'fuzziness_1',
                      'fuzziness_2',
                      'fuzziness_3',
                      'fuzziness_4',
                      'search_field',
                      'search_field_1',
                      'search_field_2',
                      'search_field_3',
                      'search_field_4',
                      'slop',
                      'slop_1',
                      'slop_2',
                      'slop_3',
                      'slop_4',
                      'in_order',
                      'in_order_1',
                      'in_order_2',
                      'in_order_3',
                      'in_order_4',
                      'regex_search',
                      'regex_search_1',
                      'regex_search_2',
                      'regex_search_3',
                      'regex_search_4',
                      'date_plus_minus',
                      'search_id',
                      'simple_search_id',
                      'bool_operator')
    if form.corpus.data and len(form.corpus.data) == 1:
        form.corpus.data = form.corpus.data[0].split(' ')
    if form.special_days.data and len(form.special_days.data) == 1:
        form.special_days.data = form.special_days.data[0].split(' ')
    form_data = deepcopy(form.data)
    if 'q' in request.args:
        form_data['q_1'] = request.args.get('q', '').lower()
        for form_arg in ['regex_search', 'fuzziness', 'slop', 'in_order', 'formulaic_parts', 'proper_name', 'exclude_q']:
            form_data[form_arg + '_1'] = request.args.get(form_arg, '')
        form_data['lemma_search'] = request.args.get('lemma_search', 'False')
    data_present = [x for x in form_data if form_data[x] and form_data[x] != 'none' and x not in ignored_fields]
    if 'forgeries' in data_present and form_data['forgeries'] in ['include', 'exclude']:
        data_present.remove('forgeries')
    if form.validate() and data_present and 'submit' in data_present:
        if data_present != ['submit']:
            data = build_search_args(form_data)
            return redirect(url_for('.r_results', source="advanced", sort='urn', **data))
        flash(_('Bitte geben Sie Daten in mindestens einem Feld ein.'))
    for k, m in form.errors.items():
        flash(k + ': ' + m[0])
    return current_app.config['nemo_app'].render(template='search::advanced_search.html', form=form, categories=coll_cats,
                                                 composition_places=current_app.config['nemo_app'].comp_places, url=dict())


@bp.route("/doc", methods=["GET"])
def r_search_docs():
    """ Route to the documentation page for the advanced search"""
    return current_app.config['nemo_app'].render(template="search::documentation.html", url=dict())


@bp.route("/suggest/<qSource>", methods=["GET"])
def word_search_suggester(qSource: str):
    # This needs to be brought into line with the new args for search.Search
    search_args = build_search_args({x: y for x, y in request.args.items()})
    search_args['qSource'] = qSource
    for month_arg in ['month', 'month_start', 'month_end']:
        if month_arg in search_args:
            search_args[month_arg] = int(search_args[month_arg])
    query_keys = [x for x in search_args.keys() if x.startswith('q_')]
    query_val_keys = [("in_order", 'False'),
                      ("regex_search", False),
                      ("proper_name", ''),
                      ("formulaic_parts", ''),
                      ("slop", 0),
                      ("fuzziness", 0),
                      ("search_field", 'text'),
                      ("exclude_q", '')]
    query_dict = dict()
    for k in query_keys:
        k_num = k.split('_')[-1]
        query_val_dict = {'q': search_args.pop(k, '').lower()}
        for v, val_default in query_val_keys:
            arg_val = search_args.pop(v + '_' + k_num, None)
            query_val_dict[v] = arg_val if arg_val else val_default
        query_dict[k] = query_val_dict
    if query_dict[qSource]['search_field'] == 'text':
        query_dict[qSource]['search_field'] = 'autocomplete'
    else:
        query_dict[qSource]['search_field'] = 'autocomplete_' + query_dict[qSource]['search_field']
    search_args['query_dict'] = query_dict
    words = suggest_word_search(**search_args)
    return dumps(words)


@bp.route('/download/<download_id>', methods=["GET"])
def download_search_results(download_id: str) -> Response:
    if 'previous_search' not in session or 'previous_search_args' not in session:
        flash(_('Keine Suchergebnisse zum Herunterladen.'))
        return redirect(url_for('InstanceNemo.r_index'))
    else:
        download_id = 'pdf_download_' + str(download_id)
        resp = list()
        arg_list = list()
        special_day_dict = dict([('', ''),
                                 ('Easter', _('Ostern')),
                                 ('Lent', _('Fastenzeit')),
                                 ('Pentecost', _('Pfingsten')),
                                 ('Sunday', _('Sonntag')),
                                 ('Monday', _('Montag')),
                                 ('Tuesday', _('Dienstag')),
                                 ('Wednesday', _('Mittwoch')),
                                 ('Thursday', _('Donnerstag')),
                                 ('Friday', _('Freitag')),
                                 ('Saturday', _('Samstag'))])
        search_arg_mapping = [('year', _('Jahr')),
                              ('month', _('Monat')),
                              ('day', _('Tag')),
                              ('year_start', _('Anfangsjahr')),
                              ('month_start', _('Anfangsmonat')),
                              ('day_start', _('Anfangstag')),
                              ('year_end', _('Endjahr')),
                              ('month_end', _('Endmonat')),
                              ('day_end', _('Endtag')),
                              ('date_plus_minus', _('Datum Plus-Minus')),
                              ('exclusive_date_range', _('Exklusiv')),
                              ('composition_place', _('Ausstellungsort')),
                              ('special_days', _('Besondere Tage')),
                              ('corpus', _('Corpora'))]
        query_dict_mapping = [('q', _('Suchbegriff')),
                              ('search_field', _('Suchfeld')),
                              ('fuzziness', _('Unschärfegrad')),
                              ('slop', _('Suchradius')),
                              ('in_order', _('Wortreihenfolge beachten?')),
                              ('formulaic_parts', _('Urkundenteile')),
                              ('proper_name', _('Eigenname'))]
        search_value_dict = {'False': _('Nein'), 'True': _('Ja'), False: _('Nein'), True: _('Ja')}
        query_dict = make_query_dict(build_search_args(session['previous_search_args']))
        for k, v in query_dict.items():
            if v['q'] or v['formulaic_parts']:
                arg_list.append('<b>{}</b>:'.format(k.replace('q_', _('Suchterminus '))))
                for query_arg, s in query_dict_mapping:
                    value = v[query_arg]
                    if query_arg in ['formulaic_parts', 'proper_name']:
                        value = ' - '.join([x.title() for x in re.split(r'\+|\s+', value)])
                    arg_list.append('- <b>{}</b>: {}'.format(s, value if value != '0' else ''))
        for arg, s in search_arg_mapping:
            if arg in session['previous_search_args']:
                value = search_value_dict.get(session['previous_search_args'][arg], session['previous_search_args'][arg])
            else:
                value = ''
            if arg == 'corpus':
                value = ' - '.join([CORP_MAP[x] for x in value.split('+')])
            if arg == 'special_days':
                value = ' - '.join([special_day_dict[x] for x in value.split('+')])
            arg_list.append('<b>{}</b>: {}'.format(s, value if value != '0' else ''))
        prev_args = session['previous_search_args']
        if prev_args.get('formulaic_parts', None):
            ids = []
            for list_index, hit in enumerate(session['previous_search']):
                sents = []
                if 'highlight' in hit:
                    for highlight in hit['highlight']:
                        sents.append(re.sub(r'(</?)strong(>)', r'\1b\2', str(highlight)))
                regest_sents = []
                if 'regest_sents' in hit:
                    for s in hit['regest_sents']:
                        regest_sents.append(re.sub(r'(</?)strong(>)', r'\1b\2', str(s)))
                ids.append({'id': hit['id'],
                            'info': hit['info'],
                            'sents': sents,
                            'regest_sents': regest_sents})
                current_app.redis.set(download_id, str(floor((list_index / len(session['previous_search'])) * 100)) + '%')
            current_app.redis.setex(download_id, 60, '99%')
        else:
            try:
                ids = session['previous_search']
            # This finally statement makes sure that the JS function to get the progress halts on an error.
            finally:
                current_app.redis.setex(download_id, 60, '99%')
        for d in ids:
            r = {'title': d['info']['title'], 'sents': [], 'regest_sents': []}
            if 'sents' in d and d['sents'] != []:
                r['sents'] = ['- {}'.format(re.sub(r'(?:</small>)?<strong>(.*?)</strong>(?:<small>)?', r'<b>\1</b>',
                                                   str(s)))
                              for s in d['sents']]
            if 'regest_sents' in d and d['regest_sents'] != []:
                r['regest_sents'] = ['<u>' + _('Aus dem Regest') + '</u>']
                r['regest_sents'] += ['- {}'.format(re.sub(r'(?:</small>)?<strong>(.*?)</strong>(?:<small>)?',
                                                           r'<b>\1</b>',
                                                           str(s)))
                                      for s in d['regest_sents']]
            resp.append(r)
        pdf_buffer = BytesIO()
        description = 'Formulae-Litterae-Chartae Suchergebnisse ({})'.format(date.today().isoformat())
        my_doc = SimpleDocTemplate(pdf_buffer, title=description)
        sample_style_sheet = getSampleStyleSheet()
        flowables = list([Paragraph(_('Suchparameter'), sample_style_sheet['Heading3'])])
        for a in arg_list:
            flowables.append(Paragraph(a, sample_style_sheet['Normal']))
        flowables.append(Paragraph(_('Suchergebnisse'), sample_style_sheet['Heading3']))
        for p in resp:
            flowables.append(Paragraph(p['title'], sample_style_sheet['Heading4']))
            for sentence in p['sents']:
                flowables.append(Paragraph(sentence, sample_style_sheet['Normal']))
            for r_sentence in p['regest_sents']:
                flowables.append(Paragraph(r_sentence, sample_style_sheet['Normal']))
        my_doc.build(flowables)
        pdf_value = pdf_buffer.getvalue()
        pdf_buffer.close()
        session.pop(download_id, None)
        return Response(pdf_value, mimetype='application/pdf',
                        headers={'Content-Disposition': 'attachment;filename={}.pdf'.format(description.replace(' ', '_'))})


@bp.route('/pdf_progress/<download_id>', methods=["GET"])
def pdf_download_progress(download_id: str) -> str:
    """ Function periodically called by JS from client to check progress of PDF download"""
    if not download_id.startswith('search_progress_'):
        download_id = 'pdf_download_' + str(download_id)
    if current_app.redis.get(download_id):
        return current_app.redis.get(download_id).decode('utf-8') or '0%'
    return '0%'

@bp.route('/lemmata', methods=['GET'])
def lemma_list():
    """ Function to compile the data for the lists of lemmata"""
    def roman_to_int(s):
        result = s
        if isinstance(s, str):
            s = s.lower()
            # map of (numeral, value) tuples
            roman_numeral_map = (('m', 1000), ('cm', 900),
                                 ('d', 500), ('cd', 400),
                                 ('c', 100), ('xc', 90),
                                 ('l', 50), ('xl', 40),
                                 ('x', 10), ('ix', 9),
                                 ('v', 5), ('iv', 4), ('i', 1))
            result, index = 0, 0
            for numeral, value in roman_numeral_map:
                while s[index: index+len(numeral)] == numeral:
                    result += value
                    index += len(numeral)
        return result

    def sort_int(x):
        if x.isdigit():
            return (0, int(x))
        return (1, roman_to_int(x))

    all_lemmas = set()
    for l in current_app.config['LEMMA_LISTS']:
        with open(l) as f:
            new_lemmas = load(f)
        all_lemmas.update(new_lemmas)
    nums = set()
    lems = set()
    for t in all_lemmas:
        if re.fullmatch(r'[ivxlcdm]+', t.lower()) or t.isdigit():
            nums.add(t)
        else:
            lems.add(t)
    return current_app.config['nemo_app'].render(template='search::lemma_list.html',
                                                 lemmas=sorted(lems),
                                                 numbers=sorted(nums, key=sort_int),
                                                 url=dict())
