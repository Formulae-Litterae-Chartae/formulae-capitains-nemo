from flask import redirect, request, url_for, g, flash, current_app
from flask_babel import _
from flask_login import login_required
from math import ceil
from .Search import query_index, advanced_query_index
from .forms import AdvancedSearchForm
from formulae.search import bp


@bp.route("/simple", methods=["GET"])
@login_required
def r_simple_search():
    if not g.search_form.validate():
        for k, m in g.search_form.errors.items():
            flash(m[0])
        return redirect(url_for('.r_results', source='simple', q=g.search_form.data['q']))
    data = g.search_form.data
    data['q'] = data['q'].lower()
    corpus = '+'.join(data.pop("corpus"))
    return redirect(url_for('.r_results', source='simple', corpus=corpus, **data))


@bp.route("/results", methods=["GET"])
@login_required
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
        posts, total = query_index(corpus, 'text', g.search_form.q.data, page, current_app.config['POSTS_PER_PAGE'])
        search_args = {"q": g.search_form.q.data, 'source': 'simple', 'corpus': request.args.get('corpus', '')}
    else:
        posts, total = advanced_query_index(per_page=current_app.config['POSTS_PER_PAGE'], field=field,
                                            q=request.args.get('q').lower(),
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
                                            corpus=request.args.get('corpus', ''),
                                            exclusive_date_range=request.args.get('exclusive_date_range', "False"))
        search_args = dict(request.args)
        search_args.pop('page', None)
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
    return nemo.render(template='search::search.html', title=_('Search'), posts=posts,
                       next_url=next_url, prev_url=prev_url, page_urls=page_urls,
                       first_url=first_url, last_url=last_url, current_page=page,
                       search_string=g.search_form.q.data, url=dict())


@bp.route("/advanced_search", methods=["GET"])
@login_required
def r_advanced_search():
    from formulae.app import nemo
    form = AdvancedSearchForm()
    colls = get_all_corpora()
    form.corpus.choices = form.corpus.choices + [(x['id'].split(':')[-1], x['label'].strip()) for y in colls.values() for x in y if 'elexicon' not in x['id']]
    coll_cats = dict([(k, [(x['id'].split(':')[-1], x['label'].strip()) for x in v]) for k, v in colls.items() if k != 'lexicon_entries'])
    ignored_fields = ('exclusive_date_range', 'fuzziness', 'lemma_search', 'slop', 'in_order')
    data_present = [x for x in form.data if form.data[x] and form.data[x] != 'none' and x not in ignored_fields]
    if form.validate() and data_present:
        if data_present != ['submit']:
            data = form.data
            corpus = '+'.join(data.pop("corpus"))
            data['lemma_search'] = request.args.get('lemma_search')
            return redirect(url_for('.r_results', source="advanced", corpus=corpus, **data))
        flash(_('Please enter data in at least one field.'))
    for k, m in form.errors.items():
        flash(k + ': ' + m[0])
    return nemo.render(template='search::advanced_search.html', form=form, categories=coll_cats, url=dict())


def get_all_corpora():
    """ A convenience function to return all sub-corpora in all collections

    :return: dictionary with all the collections as keys and a list of the corpora in the collection as values
    """
    from formulae.app import nemo
    colls = {}
    for member in nemo.make_members(nemo.resolver.getMetadata(), lang=None):
        colls[member['id']] = nemo.make_members(nemo.resolver.getMetadata(member['id']))
    return colls
