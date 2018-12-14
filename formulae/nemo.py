from flask import url_for, Markup, g, session, flash, request
from flask_login import current_user, login_required
from flask_babel import _, refresh, get_locale
from flask_babel import lazy_gettext as _l
from werkzeug.utils import redirect
from flask_nemo import Nemo
from rdflib.namespace import DCTERMS, Namespace
from MyCapytain.common.constants import Mimetypes
from MyCapytain.resources.prototypes.cts.inventory import CtsWorkMetadata, CtsEditionMetadata
from MyCapytain.errors import UnknownCollection
from formulae.search.forms import SearchForm
from lxml import etree
from .errors.handlers import e_internal_error, e_not_found_error, e_unknown_collection_error
import re
from datetime import date
from string import punctuation


class NemoFormulae(Nemo):

    ROUTES = [
        ("/", "r_index", ["GET"]),
        ("/collections", "r_collections", ["GET"]),
        ("/collections/<objectId>", "r_collection", ["GET"]),
        ("/corpus/<objectId>", "r_corpus", ["GET"]),
        ("/text/<objectId>/references", "r_references", ["GET"]),
        ("/texts/<objectIds>/passage/<subreferences>", "r_multipassage", ["GET"]),
        ("/add_collections/<objectIds>/<reffs>", "r_add_text_collections", ["GET"]),
        ("/add_collection/<objectId>/<objectIds>/<reffs>", "r_add_text_collection", ["GET"]),
        ("/add_text/<objectId>/<objectIds>/<reffs>", "r_add_text_corpus", ["GET"]),
        ("/lexicon/<objectId>", "r_lexicon", ["GET"]),
        ("/lang", "r_set_language", ["GET", "POST"]),
        ("/sub_elements/<coll>/<objectIds>/<reffs>", "r_add_sub_elements", ["GET"]),
        ("/sub_elements/<coll>", "r_get_sub_elements", ["GET"]),
        ("/imprint", "r_impressum", ["GET"])
    ]
    SEMANTIC_ROUTES = [
        "r_collection", "r_references", "r_multipassage"
    ]

    FILTERS = [
        "f_formatting_passage_reference",
        "f_i18n_iso",
        "f_order_resource_by_lang",
        "f_hierarchical_passages",
        "f_is_str",
        "f_i18n_citation_type",
        "f_slugify",
        "f_make_members"
    ]

    CACHED = [
        # Routes
        "r_index", # "r_collection", "r_collections", "r_references", "r_assets", "r_multipassage",
        # Controllers
        "get_inventory", "get_collection", "get_reffs", "get_passage", "get_siblings", "get_open_texts", "get_all_corpora",
        # Translater
        "semantic", "make_coins", "expose_ancestors_or_children", "make_members", "transform",
        # Business logic
        # "view_maker", "route", #"render",
    ]

    PROTECTED = [
        # "r_index", "r_collections", "r_collection", "r_references", "r_multipassage", "r_lexicon",
        # "r_add_text_collections", "r_add_text_collection", "r_corpus", "r_add_text_corpus"
    ]

    OPEN_COLLECTIONS = ['urn:cts:formulae:buenden', 'urn:cts:formulae:passau', 'urn:cts:formulae:schaeftlarn',
                        'urn:cts:formulae:stgallen','urn:cts:formulae:zuerich', 'urn:cts:formulae:elexicon',
                        'urn:cts:formulae:mondsee', 'urn:cts:formulae:regensburg', 'urn:cts:formulae:salzburg',
                        'urn:cts:formulae:werden', 'urn:cts:formulae:rheinisch'] #, 'urn:cts:formulae:andecavensis.form001'] + ['urn:cts:formulae:andecavensis']

    HALF_OPEN_COLLECTIONS = ['urn:cts:formulae:mondsee', 'urn:cts:formulae:regensburg', 'urn:cts:formulae:salzburg',
                             'urn:cts:formulae:werden', 'urn:cts:formulae:rheinisch']

    OPEN_NOTES = []

    LANGUAGE_MAPPING = {"lat": _l('Latein'), "deu": _l("Deutsch"), "fre": _l("Französisch"),
                        "eng": _l("Englisch")}

    BIBO = Namespace('http://bibliotek-o.org/1.0/ontology/')

    SALZBURG_MAPPING = {'a': 'Codex Odalberti', 'b': 'Codex Fridarici', 'c': 'Codex Hartuuici', 'd': 'Codex Tietmari II',
                        'e': 'Codex Balduuini', 'bn': 'Breves Notitiae', 'na': 'Notitia Arnonis',
                        'bna': 'Breves Notitiae Anhang'}

    def __init__(self, *args, **kwargs):
        if "pdf_folder" in kwargs:
            self.pdf_folder = kwargs["pdf_folder"]
            del kwargs["pdf_folder"]
        super(NemoFormulae, self).__init__(*args, **kwargs)
        self.open_texts, self.half_open_texts = self.get_open_texts()
        self.sub_colls = self.get_all_corpora()
        self.app.jinja_env.filters["remove_from_list"] = self.f_remove_from_list
        self.app.jinja_env.filters["join_list_values"] = self.f_join_list_values
        self.app.jinja_env.filters["replace_indexed_item"] = self.f_replace_indexed_item
        self.app.register_error_handler(404, e_not_found_error)
        self.app.register_error_handler(500, e_internal_error)
        self.app.before_request(self.before_request)
        self.app.after_request(self.after_request)

    def get_all_corpora(self):
        """ A convenience function to return all sub-corpora in all collections

        :return: dictionary with all the collections as keys and a list of the corpora in the collection as values
        """
        colls = {}
        for member in self.make_members(self.resolver.getMetadata(), lang=None):
            members = self.make_members(self.resolver.getMetadata(member['id']))
            for m in members:
                m.update({'short_title':
                              str(self.resolver.getMetadata(m['id']).metadata.get_single(self.BIBO.AbbreviatedTitle))})
            colls[member['id']] = members
        return colls

    def get_open_texts(self):
        """ Creates the lists of open and half-open texts to be used later. I have moved this to a function to try to
            cache it.

        :return: list of open texts and half-open texts
        """
        open_texts = []
        half_open_texts = []
        for c in self.OPEN_COLLECTIONS: # [-1]: Add this once andecavensis is added back into OPEN_COLLECTIONS
            try:
                open_texts += [x.id for x in self.resolver.getMetadata(c).readableDescendants]
            except UnknownCollection:
                continue
        for c in self.HALF_OPEN_COLLECTIONS:
            try:
                half_open_texts += [x.id for x in self.resolver.getMetadata(c).readableDescendants]
            except UnknownCollection:
                continue
        return open_texts, half_open_texts

    def check_project_team(self):
        """ A convenience function that checks if the current user is a part of the project team"""
        try:
            return current_user.project_team is True
        except AttributeError:
            return False

    def create_blueprint(self):
        """ Enhance original blueprint creation with error handling

        :rtype: flask.Blueprint
        """
        blueprint = super(NemoFormulae, self).create_blueprint()
        blueprint.register_error_handler(UnknownCollection, e_unknown_collection_error)
        # blueprint.register_error_handler(500, self.e_internal_error)
        # blueprint.register_error_handler(404, self.e_not_found_error)
        return blueprint

    def get_locale(self):
        """ Retrieve the best matching locale using request headers

        .. note:: Probably one of the thing to enhance quickly.

        :rtype: str
        """
        best_match = str(get_locale())
        lang = self.__default_lang__
        if best_match == "de":
            lang = "ger"
        elif best_match == "fr":
            lang = "fre"
        elif best_match == "en":
            lang = "eng"
        return lang

    def f_remove_from_list(self, l, i):
        """ remove item "i" from list "l"

        :param l: the list
        :param i: the item
        :return: the list without the item
        """
        l.remove(i)
        return l

    def f_join_list_values(self, l, s):
        """ join the values of "l" user the separator "s"

        :param l: the list of values
        :param s: the separator
        :return: a string of the values joined by the separator
        """
        return s.join(l).strip(s)

    def f_replace_indexed_item(self, l, i, v):
        """

        :param l: the list of values
        :param i: the index to be replace
        :param v: the value with which the indexed value will be replaced
        :return: new list
        """
        l[i] = v
        return l

    def r_set_language(self, code):
        """ Sets the seseion's language code which will be used for all requests

        :param code: The 2-letter language code
        :type code: str
        """
        session['locale'] = code
        refresh()

    def before_request(self):
        g.search_form = SearchForm()

    def after_request(self, response):
        """ Currently used only for the Cache-Control header
            max_age calculates days, hours, minutes and seconds and adds them together.
            First number after '+' is the respective number for each value.
        """
        response.cache_control.max_age = self.app.config['CACHE_MAX_AGE']
        response.cache_control.public = True
        return response

    def view_maker(self, name, instance=None):
        """ Create a view

        :param name: Name of the route function to use for the view.
        :type name: str
        :return: Route function which makes use of Nemo context (such as menu informations)
        :rtype: function
        """
        # Avoid copy-pasta and breaking upon Nemo inside code changes by reusing the original view_maker function
        # Super will go to the parent class and you will use it's "view_maker" function
        route = super(NemoFormulae, self).view_maker(name, instance)
        if name in self.PROTECTED:
            route = login_required(route)
        return route

    def r_collection(self, objectId, lang=None):
        data = super(NemoFormulae, self).r_collection(objectId, lang=lang)
        if self.check_project_team() is False:
            data['collections']['members'] = [x for x in data['collections']['members'] if x['id'] in self.OPEN_COLLECTIONS]
        if len(data['collections']['members']) == 0:
            if "formulae" in objectId:
                flash(_('Die Formulae Andecavensis sind in der Endredaktion und werden bald zur Verfügung stehen.'))
            else:
                flash(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
        elif len(data['collections']['members']) == 1:
            return redirect(url_for('.r_corpus', objectId=data['collections']['members'][0]['id'], lang=lang))
        data['template'] = "main::sub_collections.html"
        return data

    def r_corpus(self, objectId, lang=None):
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template and collections contained in given collection
        :rtype: {str: Any}
        """
        collection = self.resolver.getMetadata(objectId)
        r = {}
        if 'elexicon' in objectId:
            template = "main::elex_collection.html"
        elif 'salzburg' in objectId:
            template = "main::salzburg_collection.html"
        else:
            template = "main::sub_collection.html"
        for m in list(self.resolver.getMetadata(collection.id).readableDescendants):
            if self.check_project_team() is True or m.id in self.open_texts:
                if "salzburg" in m.id:
                    par = m.parent.id.split('-')[1:]
                    if len(par) == 2:
                        full_par = (self.SALZBURG_MAPPING[par[0]], 'Einleitung' if par[1] == 'intro' else 'Vorrede')
                    else:
                        p = re.match(r'(\D+)(\d+)', par[0])
                        if p:
                            full_par = (self.SALZBURG_MAPPING[p.group(1)], p.group(2).lstrip('0'))
                        else:
                            full_par = (self.SALZBURG_MAPPING[par[0]], self.SALZBURG_MAPPING[par[0]])
                    par = '-'.join(par)
                    if 'n' in par:
                        par = 'z' + par
                    par = (par, full_par)
                    metadata = (m.id, self.LANGUAGE_MAPPING[m.lang])
                elif "elexicon" in m.id:
                    par = m.parent.id.split('.')[-1][0].capitalize()
                    metadata = (m.id, m.parent.id.split('.')[-1], self.LANGUAGE_MAPPING[m.lang])
                else:
                    par = re.sub(r'.*?(\d+)', r'\1', m.parent.id)
                    metadata = (m.id, self.LANGUAGE_MAPPING[m.lang])
                if par in r.keys():
                    r[par]["versions"].append(metadata)
                else:
                    r[par] = {"short_regest": str(m.get_description()).split(':')[0] if 'andecavensis' in m.id else '',
                              # short_regest will change to str(m.get_cts_property('short-regest')) and
                              # regest will change to str(m.get_description()) once I have reconverted the texts
                              "regest": [':'.join(str(m.get_description()).split(':')[1:])] if 'andecavensis' in m.id else str(m.get_description()).split('***'),
                              "dating": str(m.metadata.get_single(DCTERMS.temporal)),
                              "ausstellungsort": str(m.metadata.get_single(DCTERMS.spatial)),
                              "versions": [metadata], 'name': par.lstrip('0') if type(par) is str else ''}
        for k, v in r.items():
            r[k]['versions'] = sorted(v['versions'], reverse=True)
        if len(r) == 0:
            flash(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
        return {
            "template": template,
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                    "open_regesten": collection.id not in self.HALF_OPEN_COLLECTIONS
                },
                "readable": r,
                "parents": self.make_parents(collection, lang=lang)
            }
        }

    def r_add_text_collections(self, objectIds, reffs, lang=None):
        """ Retrieve the top collections of the inventory

        :param lang: Lang in which to express main data
        :type lang: str
        :return: Collections information and template
        :rtype: {str: Any}
        """
        collection = self.resolver.getMetadata()
        return {
            "template": "main::collection.html",
            "current_label": collection.get_label(lang),
            "collections": {
                "members": self.make_members(collection, lang=lang)
            },
            "prev_texts": objectIds,
            "prev_reffs": reffs
        }

    def r_add_text_collection(self, objectId, objectIds, reffs, lang=None):
        """ Route to browse a top-level collection and add another text to the view

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template and collections contained in given collection
        :rtype: {str: Any}
        """
        collection = self.resolver.getMetadata(objectId)
        members = self.make_members(collection, lang=lang)
        if self.check_project_team() is False:
            members = [x for x in members if x['id'] in self.OPEN_COLLECTIONS]
        if len(members) == 1:
            return redirect(url_for('.r_add_text_corpus', objectId=members[0]['id'],
                                    objectIds=objectIds, reffs=reffs, lang=lang))
        elif len(members) == 0:
            flash(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
        return {
            "template": "main::sub_collections.html",
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                },
                "members": members,
                "parents": self.make_parents(collection, lang=lang)
            },
            "prev_texts": objectIds,
            "prev_reffs": reffs
        }

    def r_add_text_corpus(self, objectId, objectIds, reffs, lang=None):
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template and collections contained in given collection
        :rtype: {str: Any}
        """
        initial = self.r_corpus(objectId)
        initial.update({'prev_texts': objectIds, 'prev_reffs': reffs})
        return initial

    def get_first_passage(self, objectId):
        """ Provides a redirect to the first passage of given objectId

        :param objectId: Collection identifier
        :type objectId: str
        :return: Redirection to the first passage of given text
        """
        collection, reffs = self.get_reffs(objectId=objectId, export_collection=True)
        first, _ = reffs[0]
        return str(first)

    def r_passage(self, objectId, subreference, lang=None):
        """ Retrieve the text of the passage

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :param subreference: Reference identifier
        :type subreference: str
        :return: Template, collections metadata and Markup object representing the text
        :rtype: {str: Any}
        """
        # pdf_path = ''
        collection = self.get_collection(objectId)
        if isinstance(collection, CtsWorkMetadata):
            editions = [t for t in collection.children.values() if isinstance(t, CtsEditionMetadata)]
            if len(editions) == 0:
                raise UnknownCollection('{}.{}'.format(collection.get_label(lang), subreference) + _l(' wurde nicht gefunden.'))
            return redirect(url_for(".r_passage", objectId=str(editions[0].id), subreference=subreference))
        try:
            text = self.get_passage(objectId=objectId, subreference=subreference)
        except IndexError:
            new_subref = self.get_reffs(objectId)[0][0]
            text = self.get_passage(objectId=objectId, subreference=new_subref)
            flash('{}.{}'.format(collection.get_label(lang), subreference) + _l(' wurde nicht gefunden. Der ganze Text wird angezeigt.'))
            subreference = new_subref
        passage = self.transform(text, text.export(Mimetypes.PYTHON.ETREE), objectId)
        if 'notes' in self._transform:
            notes = self.extract_notes(passage)
        else:
            notes = ''
        prev, next = self.get_siblings(objectId, subreference, text)
        # if current_user.project_team is False and str(text.get_creator(lang)) not in self.OPEN_COLLECTIONS:
        #     pdf_path = self.pdf_folder + objectId.split(':')[-1] + '.pdf'
        return {
            "template": "main::text.html",
            "objectId": objectId,
            "subreference": subreference,
            "collections": {
                "current": {
                    "label": collection.get_label(lang),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                    "author": text.get_creator(lang),
                    "title": text.get_title(lang),
                    "description": text.get_description(lang),
                    "citation": collection.citation,
                    "coins": self.make_coins(collection, text, subreference, lang=lang)
                },
                "parents": self.make_parents(collection, lang=lang)
            },
            "text_passage": Markup(passage),
            "notes": Markup(notes),
            "prev": prev,
            "next": next,
            "open_regest": objectId not in self.half_open_texts,
            "show_notes": objectId in self.OPEN_NOTES,
            "date": "{:04}-{:02}-{:02}".format(date.today().year, date.today().month, date.today().day)
        }

    def r_multipassage(self, objectIds, subreferences, lang=None, result_sents=''):
        """ Retrieve the text of the passage

        :param objectIds: Collection identifiers separated by '+'
        :type objectIds: str
        :param lang: Lang in which to express main data
        :type lang: str
        :param subreferences: Reference identifiers separated by '+'
        :type subreferences: str
        :param result_sents: The list of sentences from elasticsearch results
        :type result_sents: str
        :return: Template, collections metadata and Markup object representing the text
        :rtype: {str: Any}
        """
        ids = objectIds.split('+')
        translations = {}
        for i in ids:
            p = self.resolver.getMetadata(self.resolver.getMetadata(i).parent.id)
            translations[i] = [m for m in p.readableDescendants if m.id not in ids]
        passage_data = {'template': 'main::multipassage.html', 'objects': [], "translation": translations}
        subrefers = subreferences.split('+')
        result_sents = request.args.get('result_sents')
        for i, id in enumerate(ids):
            if self.check_project_team() is True or id in self.open_texts:
                if subrefers[i] in ["all", 'first']:
                    subref = self.get_reffs(id)[0][0]
                else:
                    subref = subrefers[i]
                d = self.r_passage(id, subref, lang=lang)
                del d['template']
                if result_sents:
                    intermediate = result_sents.replace('+', ' ').replace('%2C', '')
                    intermediate = re.sub('strong|small', '', intermediate)
                    intermediate = re.sub('\s+', ' ', intermediate)
                    intermediate = intermediate.split('$')
                    new_sents = [re.sub('[{}„“…]'.format(punctuation), '', x) for x in intermediate]
                    d['text_passage'] = self.highlight_found_sents(d['text_passage'], new_sents)
                passage_data['objects'].append(d)
        if len(ids) > len(passage_data['objects']):
            flash(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
        return passage_data

    def highlight_found_sents(self, html, sents):
        """ Adds "searched" to the classList of words in "sents" from elasticsearch results

        :param html: the marked-up text to be searched
        :param sents: list of the "sents" strings
        :return: transformed html
        """
        root = etree.fromstring(html)
        spans = root.xpath('//span[contains(@class, "w")]')
        texts = [re.sub('[{}„“…]'.format(punctuation), '', re.sub(r'&[lg]t;', '', x.text)) for x in spans if re.sub('[{}„“…]'.format(punctuation), '', x.text) != '']
        for sent in sents:
            words = sent.split()
            for i in range(len(spans)):
                if words == texts[i:i + len(words)]:
                    spans[i].set('class', spans[i].get('class') + ' searched-start')
                    spans[i + len(words) - 1].set('class', spans[i + len(words) - 1].get('class') + ' searched-end')
                    for span in spans[i:i + len(words)]:
                        if span.getparent().index(span) == 0 and 'searched-start' not in span.get('class'):
                            span.set('class', span.get('class') + ' searched-start')
                        if span == span.getparent().findall('span')[-1] and 'searched-end' not in span.get('class'):
                            span.set('class', span.get('class') + ' searched-end')
                    break
        xml_string = etree.tostring(root, encoding=str, method='html', xml_declaration=None, pretty_print=False,
                                    with_tail=True, standalone=None)
        span_pattern = re.compile(r'(<span class="w \w*\s?searched-start.*?searched-end".*?</span>)', re.DOTALL)
        xml_string = re.sub(span_pattern, r'<span class="searched">\1</span>', xml_string)
        return Markup(xml_string)

    def r_lexicon(self, objectId, lang=None):
        """ Retrieve the eLexicon entry for a word

        :param objectId: Collection identifiers separated by '+'
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template, collections metadata and Markup object representing the text
        :rtype: {str: Any}
        """
        subreference = "1"
        d = self.r_passage(objectId, subreference, lang=lang)
        d['template'] = 'main::lexicon_modal.html'
        return d

    def r_impressum(self):
        """ Impressum route function

        :return: Template to use for Impressum page
        :rtype: {str: str}
        """
        return {"template": "main::impressum.html"}

    def extract_notes(self, text):
        """ Constructs a dictionary that contains all notes with their ids. This will allow the notes to be
        rendered anywhere on the page and not only where they occur in the text.

        :param text: the string to be transformed
        :return: dict('note_id': 'note_content')
        """
        with open(self._transform['notes']) as f:
            xslt = etree.XSLT(etree.parse(f))

        return str(xslt(etree.fromstring(text)))

    def r_add_sub_elements(self, coll, objectIds, reffs, lang=None):
        """ A convenience function to return all sub-corpora in all collections

        :return: dictionary with all the collections as keys and a list of the corpora in the collection as values
        """
        texts = self.r_add_text_collection(coll, objectIds, reffs, lang=lang)
        texts["template"] = 'main::sub_element_snippet.html'
        return texts

    def r_get_sub_elements(self, coll, objectIds='', reffs='', lang=None):
        """ A convenience function to return all sub-corpora in all collections

        :return: dictionary with all the collections as keys and a list of the corpora in the collection as values
        """
        texts = self.r_add_text_collection(coll, objectIds, reffs, lang=lang)
        texts["template"] = 'main::sub_element_snippet.html'
        return texts
