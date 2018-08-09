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
        return redirect(url_for('.r_index'))
    return redirect(url_for('.r_results', source='simple', **request.args))


@bp.route("/results", methods=["GET"])
@login_required
def r_results():
    from formulae.app import nemo
    source = request.args.get('source', None)
    # This means that someone simply naviageted to the /results page without any search parameters
    if not source:
        return redirect(url_for('InstanceNemo.r_index'))
    page = request.args.get('page', 1, type=int)
    if request.args.get('fuzzy_search'):
        fuzziness = 'y'
    else:
        fuzziness = 'n'
    if request.args.get('lemma_search') == 'y':
        field = 'lemmas'
    else:
        field = 'text'
    # Unlike in the Flask Megatutorial, I need to specifically pass the field name
    # The index value is ignored for the simple search since all indices are searched
    if source == 'simple':
        posts, total = query_index('', field, g.search_form.q.data, page, current_app.config['POSTS_PER_PAGE'],
                                   fuzziness, request.args.get('phrase_search'))
        search_args = {"q": g.search_form.q.data, "lemma_search": request.args.get('lemma_search'),
                       "fuzzy_search": request.args.get('fuzzy_search'),
                       "phrase_search": request.args.get('phrase_search'), 'source': 'simple'}
    else:
        posts, total = advanced_query_index(per_page=current_app.config['POSTS_PER_PAGE'], field=field,
                                            q=request.args.get('q'), fuzzy_search=fuzziness, page=page,
                                            phrase_search=request.args.get('phrase_search'),
                                            year=int(request.args.get('year')), month=int(request.args.get('month')),
                                            day=int(request.args.get('day')),
                                            year_start=int(request.args.get('year_start')),
                                            month_start=int(request.args.get('month_start')),
                                            day_start=int(request.args.get('day_start')),
                                            year_end=int(request.args.get('year_end')),
                                            month_end=int(request.args.get('month_end')),
                                            day_end=int(request.args.get('day_end')))
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
    form.corpus.choices = form.corpus.choices + [(x['id'].split(':')[-1], x['label'].strip()) for y in colls.values() for x in y if x['label'] != 'eLexicon']
    coll_cats = dict([(k, [(x['id'].split(':')[-1], x['label'].strip()) for x in v]) for k, v in colls.items() if k != 'E-Lexikon'])
    data_present = [x for x in form.data if form.data[x] and form.data[x] != 'none']
    if form.validate() and data_present:
        if data_present != ['submit']:
            return redirect(url_for('.r_results', source="advanced", **request.args))
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
        colls[member['semantic'].title()] = nemo.make_members(nemo.resolver.getMetadata(member['id']))
    return colls
