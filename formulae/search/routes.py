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


CORP_MAP = {y['match']['_type']: x for x, y in AGGREGATIONS['corpus']['filters']['filters'].items()}


@bp.route("/simple", methods=["GET"])
def r_simple_search() -> redirect:
    if not g.search_form.validate():
        for k, m in g.search_form.errors.items():
            if k == 'corpus':
                flash(_('Sie müssen mindestens eine Sammlung für die Suche auswählen ("Formeln" und/oder "Urkunden").') + _(' Resultate aus "Formeln" und "Urkunden" werden hier gezeigt.'))
            elif k == 'q':
                flash(m[0] + _(' Die einfache Suche funktioniert nur mit einem Suchwort.'))
        return redirect(url_for('.r_results', source='simple', corpus='formulae+chartae', q=g.search_form.data['q']))
    data = g.search_form.data
    data['q'] = data['q'].lower()
    lemma_search = data.pop('lemma_search')
    data['lemma_search'] = 'False'
    data['search_id'] = data.pop('simple_search_id')
    if lemma_search in ['y', 'True', True]:
        data['lemma_search'] = 'True'
    corpus = '+'.join(data.pop("corpus"))
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
    if corpus in [['all'], ['formulae', 'chartae'], ['']]:
        corps = [x['id'].split(':')[-1] for x in g.sub_colls['formulae_collection']] + sorted([x['id'].split(':')[-1] for x in g.sub_colls['other_collection']])
    elif corpus == ['formulae']:
        corps = [x['id'].split(':')[-1] for x in g.sub_colls['formulae_collection']]
    elif corpus == ['chartae']:
        corps = sorted([x['id'].split(':')[-1] for x in g.sub_colls['other_collection']])
    else:
        corps = corpus
    g.corpora = [(x, CORP_MAP[x]) for x in corps]
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
    search_args = dict(per_page=posts_per_page,
                       lemma_search=request.args.get('lemma_search', 'False') or 'False',
                       q=request.args.get('q'),
                       fuzziness=request.args.get("fuzziness", "0"),
                       page=page,
                       in_order=request.args.get('in_order', 'False'),
                       slop=request.args.get('slop', '0'),
                       regest_q=request.args.get('regest_q'),
                       year=request.args.get('year', 0, type=int),
                       month=request.args.get('month', 0, type=int),
                       day=request.args.get('day', 0, type=int),
                       year_start=request.args.get('year_start', 0, type=int),
                       month_start=request.args.get('month_start', 0, type=int),
                       day_start=request.args.get('day_start', 0, type=int),
                       year_end=request.args.get('year_end', 0, type=int),
                       month_end=request.args.get('month_end', 0, type=int),
                       day_end=request.args.get('day_end', 0, type=int),
                       date_plus_minus=request.args.get("date_plus_minus", 0, type=int),
                       corpus=corpus or ['all'],
                       exclusive_date_range=request.args.get('exclusive_date_range', "False"),
                       composition_place=request.args.get('composition_place', ''),
                       sort=request.args.get('sort', 'urn'),
                       special_days=special_days,
                       old_search=old_search,
                       source=request.args.get('source', 'advanced'),
                       regest_field=request.args.get('regest_field', 'regest'),
                       formulaic_parts=request.args.get('formulaic_parts', ''),
                       search_id=request.args.get('search_id', ''))
    posts, total, aggs, g.previous_search = advanced_query_index(**search_args)
    search_args = {k: v for k, v in search_args.items() if v}
    search_args.pop('page', None)
    search_args['corpus'] = '+'.join(corpus)
    if 'special_days' in search_args:
        search_args['special_days'] = '+'.join(special_days)
    search_args.pop('old_search', None)
    if old_search is False:
        g.previous_search_args = search_args
        g.previous_aggregations = aggs
        g.previous_search_args['corpus'] = '+'.join(corps)
    inf_to_lemmas = []
    if search_args['lemma_search'] != 'True':
        search_terms = search_args.get('q', '').split()
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
    return current_app.config['nemo_app'].render(template=template, title=_('Suche'), posts=posts,
                                                 current_page=page, search_string=g.search_form.q.data.lower(),
                                                 url=dict(), open_texts=g.open_texts, total_results=total, aggs=aggs,
                                                 searched_lems=inf_to_lemmas)


@bp.route("/advanced_search", methods=["GET"])
def r_advanced_search():
    form = AdvancedSearchForm()
    colls = g.sub_colls
    form.corpus.choices = form.corpus.choices + [(x['id'].split(':')[-1], x['short_title'].strip()) for y in colls.values() for x in y if 'elexicon' not in x['id']]
    coll_cats = dict([(k, [(x['id'].split(':')[-1], x['short_title'].strip()) for x in v]) for k, v in colls.items() if k != 'lexicon_entries'])
    ignored_fields = ('exclusive_date_range', 'fuzziness', 'lemma_search', 'slop', 'in_order', 'date_plus_minus',
                      'search_id', 'simple_search_id')
    data_present = [x for x in form.data if form.data[x] and form.data[x] != 'none' and x not in ignored_fields]
    if form.corpus.data and len(form.corpus.data) == 1:
        form.corpus.data = form.corpus.data[0].split(' ')
    if form.special_days.data and len(form.special_days.data) == 1:
        form.special_days.data = form.special_days.data[0].split(' ')
    if form.formulaic_parts.data and len(form.formulaic_parts.data) == 1:
        form.formulaic_parts.data = form.formulaic_parts.data[0].split(' ')
    if form.validate() and data_present and 'submit' in data_present:
        if data_present != ['submit']:
            data = form.data
            data['q'] = data['q'].lower()
            data['regest_q'] = data['regest_q'].lower()
            data['corpus'] = '+'.join(data.pop("corpus")) or 'all'
            data['formulaic_parts'] = '+'.join(data.pop('formulaic_parts')) or ''
            lemma_search = data.pop('lemma_search')
            data['lemma_search'] = 'False'
            if lemma_search in ['y', 'True', True]:
                data['lemma_search'] = 'True'
            data['special_days'] = '+'.join(data.pop('special_days')) or ''
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


@bp.route("/suggest/<word>", methods=["GET"])
def word_search_suggester(word: str):
    qSource = request.args.get('qSource', 'text')
    words = suggest_word_search(q=word.lower() if qSource == 'text' else request.args.get('q', '').lower(),
                                lemma_search=request.args.get('lemma_search', 'autocomplete'),
                                fuzziness=request.args.get("fuzziness", "0"),
                                in_order=request.args.get('in_order', 'False'),
                                slop=request.args.get('slop', '0'),
                                year=request.args.get('year', 0, type=int),
                                month=request.args.get('month', 0, type=int),
                                day=request.args.get('day', 0, type=int),
                                year_start=request.args.get('year_start', 0, type=int),
                                month_start=request.args.get('month_start', 0, type=int),
                                day_start=request.args.get('day_start', 0, type=int),
                                year_end=request.args.get('year_end', 0, type=int),
                                month_end=request.args.get('month_end', 0, type=int),
                                day_end=request.args.get('day_end', 0, type=int),
                                date_plus_minus=request.args.get("date_plus_minus", 0, type=int),
                                corpus=request.args.get('corpus', '').split() or ['all'],
                                exclusive_date_range=request.args.get('exclusive_date_range', "False"),
                                composition_place=request.args.get('composition_place', ''),
                                special_days=request.args.get('special_days', '').split(),
                                regest_q=word.lower() if qSource == 'regest' else request.args.get('regest_q', '').lower(),
                                regest_field=request.args.get('regest_field', 'regest'),
                                qSource=request.args.get('qSource', 'text'))
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
        search_arg_mapping = [('q', _('Suchbegriff')), ('lemma_search', _('Lemma?')),
                              ('regest_q', _('Regesten Suchbegriff')), ('fuzziness', _('Unschärfegrad')),
                              ('slop', _('Suchradius')), ('in_order', _('Wortreihenfolge beachten?')), ('year', _('Jahr')),
                              ('month', _('Monat')), ('day', _('Tag')), ('year_start', _('Anfangsjahr')),
                              ('month_start', _('Anfangsmonat')), ('day_start', _('Anfangstag')), ('year_end', _('Endjahr')),
                              ('month_end', _('Endmonat')), ('day_end', _('Endtag')), ('date_plus_minus', _('Datum Plus-Minus')),
                              ('exclusive_date_range', _('Exklusiv')), ('composition_place', _('Ausstellungsort')),
                              ('special_days', _('Besondere Tage')), ('corpus', _('Corpora')), ('formulaic_parts', _('Urkundenteile'))]
        search_value_dict = {'False': _('Nein'), 'True': _('Ja'), False: _('Nein'), True: _('Ja')}
        for arg, s in search_arg_mapping:
            if arg in session['previous_search_args']:
                value = search_value_dict.get(session['previous_search_args'][arg], session['previous_search_args'][arg])
            else:
                value = ''
            if arg == 'corpus':
                value = ' - '.join([CORP_MAP[x] for x in value.split('+')])
            if arg == 'special_days':
                value = ' - '.join([special_day_dict[x] for x in value.split('+')])
            if arg == 'formulaic_parts':
                value = ' - '.join([x for x in value.split('+')])
            arg_list.append('<b>{}</b>: {}'.format(s, value if value != '0' else ''))
        prev_args = session['previous_search_args']
        search_field = 'text'
        if prev_args.get('formulaic_parts', None):
            ids = []
            for list_index, hit in enumerate(session['previous_search']):
                sents = []
                if 'highlight' in hit:
                    for k, v in hit['highlight'].items():
                        for t in v:
                            sents.append('<b>{part}</b>: {text}'.format(part=k, text=t))
                else:
                    for p in prev_args.get('formulaic_parts').split('+'):
                        if p in hit['_source']:
                            sents.append('<b>{part}</b>: {text}'.format(part=p, text=hit['_source'][p]))
                regest_sents = []
                open_text = hit['_id'] in current_app.config['nemo_app'].open_texts
                half_open_text = hit['_id'] in current_app.config['nemo_app'].half_open_texts
                show_regest = current_app.config['nemo_app'].check_project_team() is True or (open_text and not half_open_text)
                regest_field=prev_args.get('regest_field', 'regest')
                if 'highlight' in hit and regest_field in hit['highlight']:
                    if show_regest is False:
                        regest_sents = [_('Regest nicht zugänglich.')]
                    else:
                        regest_sents = hit['highlight'][regest_field]
                ids.append({'id': hit['_id'],
                            'info': hit['_source'],
                            'sents': sents,
                            'title': hit['_source']['title'],
                            'regest_sents': regest_sents})
                current_app.redis.set(download_id, str(floor((list_index / len(session['previous_search'])) * 100)) + '%')
            current_app.redis.setex(download_id, 60, '99%')
        else:
            if prev_args.get('lemma_search', None) == "True":
                search_field = 'lemmas'
            try:
                ids, words = lem_highlight_to_text(search={'hits': {'hits': session['previous_search']}},
                                                   q=prev_args.get('q', ''),
                                                   ordered_terms=prev_args.get('ordered_terms', False),
                                                   slop=prev_args.get('slop', 0),
                                                   regest_field=prev_args.get('regest_field', 'regest'),
                                                   search_field=search_field,
                                                   highlight_field='text',
                                                   fuzz=prev_args.get('fuzz', '0'),
                                                   download_id=download_id)
            # This finally statement makes sure that the JS function to get the progress halts on an error.
            finally:
                current_app.redis.setex(download_id, 60, '99%')
        for d in ids:
            r = {'title': d['title'], 'sents': [], 'regest_sents': []}
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
