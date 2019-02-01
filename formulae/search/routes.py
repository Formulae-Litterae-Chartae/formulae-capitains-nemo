from flask import redirect, request, url_for, g, flash, current_app, session
from flask_babel import _
from flask_login import login_required
from math import ceil
from .Search import query_index, advanced_query_index, suggest_composition_places, suggest_word_search
from .forms import AdvancedSearchForm
from formulae.search import bp
from json import dumps


@bp.route("/simple", methods=["GET"])
# @login_required
def r_simple_search():
    if not g.search_form.validate():
        for k, m in g.search_form.errors.items():
            flash(m[0])
        return redirect(url_for('.r_results', source='simple', q=g.search_form.data['q']))
    data = g.search_form.data
    data['q'] = data['q'].lower()
    corpus = '+'.join(data.pop("corpus"))
    return redirect(url_for('.r_results', source='simple', corpus=corpus, sort="urn", **data))


@bp.route("/results", methods=["GET"])
# @login_required
def r_results():
    from formulae.app import nemo
    source = request.args.get('source', None)
    corpus = request.args.get('corpus', '').split('+')
    # This means that someone simply navigated to the /results page without any search parameters
    if not source:
        return redirect(url_for('InstanceNemo.r_index'))
    page = request.args.get('page', 1, type=int)
    if request.args.get('lemma_search') == 'y':
        field = 'lemmas'
    else:
        field = 'text'
    # Unlike in the Flask Megatutorial, I need to specifically pass the field name
    if source == 'simple':
        posts, total, aggs = query_index(corpus, 'text',
                                   g.search_form.q.data,
                                   page, current_app.config['POSTS_PER_PAGE'],
                                   sort=request.args.get('sort', 'urn'))
        search_args = {"q": g.search_form.q.data, 'source': 'simple', 'corpus': '+'.join(corpus),
                       'sort': request.args.get('sort', 'urn')}
    else:
        posts, total, aggs = advanced_query_index(per_page=current_app.config['POSTS_PER_PAGE'], field=field,
                                            q=request.args.get('q'),
                                            fuzziness=request.args.get("fuzziness", "0"), page=page,
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
                                            corpus=corpus or ['all'],
                                            exclusive_date_range=request.args.get('exclusive_date_range', "False"),
                                            composition_place=request.args.get('composition_place', ''),
                                            sort=request.args.get('sort', 'urn'))
        search_args = dict(request.args)
        old_search = search_args.pop('old_search', None)
        search_args.pop('page', None)
        search_args['corpus'] = '+'.join(corpus)
    first_url = url_for('.r_results', **search_args, page=1) if page > 1 else None
    next_url = url_for('.r_results', **search_args, page=page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('.r_results', **search_args, page=page - 1) if page > 1 else None
    total_pages = int(ceil(total / current_app.config['POSTS_PER_PAGE']))
    page_urls = []
    if total_pages > 12:
        page_urls.append((1, url_for('.r_results', **search_args, page=1)))
        # page_num will be at most 12 members long. This should allow searches with many results to be displayed better.
        for page_num in range(max(page - 5, 2), min(page + 5, total_pages)):
            page_urls.append((page_num, url_for('.r_results', **search_args, page=page_num)))
        page_urls.append((total_pages, url_for('.r_results', **search_args, page=total_pages)))
    else:
        for page_num in range(1, total_pages + 1):
            page_urls.append((page_num, url_for('.r_results', **search_args, page=page_num)))
    last_url = url_for('.r_results', **search_args, page=total_pages) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    orig_sort = search_args.pop('sort', '')
    sort_urls = dict()
    for sort_param in ['min_date_asc', 'urn', 'max_date_asc', 'min_date_desc', 'max_date_desc', 'urn_desc']:
        sort_urls[sort_param] = url_for('.r_results', sort=sort_param, **search_args, page=1)
    search_args['sort'] = orig_sort
    if old_search is None:
        session['previous_search_args'] = search_args
    return nemo.render(template='search::search.html', title=_('Suche'), posts=posts,
                       next_url=next_url, prev_url=prev_url, page_urls=page_urls,
                       first_url=first_url, last_url=last_url, current_page=page,
                       search_string=g.search_form.q.data.lower(), url=dict(), open_texts=nemo.open_texts,
                       sort_urls=sort_urls, total_results=total, aggs=aggs)


@bp.route("/advanced_search", methods=["GET"])
# @login_required
def r_advanced_search():
    from formulae.app import nemo
    form = AdvancedSearchForm()
    colls = nemo.sub_colls
    form.corpus.choices = form.corpus.choices + [(x['id'].split(':')[-1], x['short_title'].strip()) for y in colls.values() for x in y if 'elexicon' not in x['id']]
    coll_cats = dict([(k, [(x['id'].split(':')[-1], x['short_title'].strip()) for x in v]) for k, v in colls.items() if k != 'lexicon_entries'])
    ignored_fields = ('exclusive_date_range', 'fuzziness', 'lemma_search', 'slop', 'in_order')
    data_present = [x for x in form.data if form.data[x] and form.data[x] != 'none' and x not in ignored_fields]
    if len(form.corpus.data) == 1:
        form.corpus.data = form.corpus.data[0].split(' ')
    if form.validate() and data_present and 'submit' in data_present:
        if data_present != ['submit']:
            data = form.data
            data['q'] = data['q'].lower()
            corpus = '+'.join(data.pop("corpus")) or 'all'
            data['lemma_search'] = request.args.get('lemma_search')
            data['corpus'] = corpus
            return redirect(url_for('.r_results', source="advanced", sort='urn', **data))
        flash(_('Bitte geben Sie Daten in mindestens einem Feld ein.'))
    for k, m in form.errors.items():
        flash(k + ': ' + m[0])
    return nemo.render(template='search::advanced_search.html', form=form, categories=coll_cats,
                       composition_places=suggest_composition_places(), url=dict())


@bp.route("/doc", methods=["GET"])
def r_search_docs():
    """ Route to the documentation page for the advanced search"""
    from formulae.app import nemo
    return nemo.render(template="search::documentation.html", url=dict())


@bp.route("/suggest/<word>", methods=["GET"])
def word_search_suggester(word):
    words = suggest_word_search(word, field=request.args.get('field', 'autocomplete'),
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
                                composition_place=request.args.get('composition_place', ''))
    return dumps(words)

