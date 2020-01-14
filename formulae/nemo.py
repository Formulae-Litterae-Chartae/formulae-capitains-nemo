from flask import url_for, Markup, g, session, flash, request, Response
from flask_login import current_user, login_required
from flask_babel import _, refresh, get_locale
from flask_babel import lazy_gettext as _l
from werkzeug.utils import redirect
from flask_nemo import Nemo
from rdflib.namespace import DCTERMS, DC, Namespace
from MyCapytain.common.constants import Mimetypes
from MyCapytain.resources.prototypes.cts.inventory import CtsWorkMetadata, CtsEditionMetadata, CtsTextInventoryMetadata
from MyCapytain.resources.collections.cts import XmlCtsTextgroupMetadata
from MyCapytain.errors import UnknownCollection
from formulae.search.forms import SearchForm
from lxml import etree
from .errors.handlers import e_internal_error, e_not_found_error, e_unknown_collection_error
import re
from datetime import date
from string import punctuation
from urllib.parse import quote
from json import load as json_load, loads as json_loads
from io import BytesIO
from reportlab.platypus import Paragraph, HRFlowable, Spacer, SimpleDocTemplate, Frame
from reportlab.lib.pdfencrypt import EncryptionFlowable
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from copy import copy


class NemoFormulae(Nemo):

    ROUTES = [
        ("/", "r_index", ["GET"]),
        ("/collections", "r_collections", ["GET"]),
        ("/collections/<objectId>", "r_collection", ["GET"]),
        ("/corpus_m/<objectId>", "r_corpus_mv", ["GET"]),
        ("/corpus/<objectId>", "r_corpus", ["GET"]),
        ("/text/<objectId>/references", "r_references", ["GET"]),
        ("/texts/<objectIds>/passage/<subreferences>", "r_multipassage", ["GET"]),
        ("/add_collections/<objectIds>/<reffs>", "r_add_text_collections", ["GET"]),
        ("/add_collection/<objectId>/<objectIds>/<reffs>", "r_add_text_collection", ["GET"]),
        ("/add_text/<objectId>/<objectIds>/<reffs>", "r_add_text_corpus", ["GET"]),
        ("/lexicon/<objectId>", "r_lexicon", ["GET"]),
        ("/lang/<code>", "r_set_language", ["GET", "POST"]),
        ("/imprint", "r_impressum", ["GET"]),
        ("/bibliography", "r_bibliography", ["GET"]),
        ("/contact", "r_contact", ["GET"]),
        ("/pdf/<objectId>", "r_pdf", ["GET"]),
        ("/reading_format/<direction>", "r_reading_format", ["GET"]),
        ("/manuscript_desc/<manuscript>", "r_man_desc", ["GET"])
    ]
    SEMANTIC_ROUTES = [
        "r_collection", "r_collection_mv", "r_references", "r_multipassage"
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
        # "r_add_text_collections", "r_add_text_collection", "r_corpus", "r_corpus_m", "r_add_text_corpus"
    ]

    OPEN_COLLECTIONS = ['urn:cts:formulae:andecavensis', 'urn:cts:formulae:buenden', 'urn:cts:formulae:elexicon',
                        'urn:cts:formulae:echternach', 'urn:cts:formulae:freising', 'urn:cts:formulae:fulda_dronke',
                        'urn:cts:formulae:fulda_stengel', 'urn:cts:formulae:hersfeld', 'urn:cts:formulae:luzern',
                        'urn:cts:formulae:mittelrheinisch', 'urn:cts:formulae:mondsee', 'urn:cts:formulae:passau',
                        'urn:cts:formulae:regensburg', 'urn:cts:formulae:rheinisch', 'urn:cts:formulae:salzburg',
                        'urn:cts:formulae:schaeftlarn', 'urn:cts:formulae:stgallen', 'urn:cts:formulae:weissenburg',
                        'urn:cts:formulae:werden', 'urn:cts:formulae:zuerich']

    HALF_OPEN_COLLECTIONS = ['urn:cts:formulae:buenden', 'urn:cts:formulae:echternach', 'urn:cts:formulae:fulda_stengel',
                             'urn:cts:formulae:mondsee', 'urn:cts:formulae:regensburg', 'urn:cts:formulae:rheinisch',
                             'urn:cts:formulae:salzburg', 'urn:cts:formulae:weissenburg', 'urn:cts:formulae:werden']

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
        self.sub_colls = self.get_all_corpora()
        self.all_texts, self.open_texts, self.half_open_texts = self.get_open_texts()
        self.app.jinja_env.filters["remove_from_list"] = self.f_remove_from_list
        self.app.jinja_env.filters["join_list_values"] = self.f_join_list_values
        self.app.jinja_env.filters["replace_indexed_item"] = self.f_replace_indexed_item
        self.app.jinja_env.filters["insert_in_list"] = self.f_insert_in_list
        self.app.register_error_handler(404, e_not_found_error)
        self.app.register_error_handler(500, e_internal_error)
        self.app.before_request(self.before_request)
        self.app.after_request(self.after_request)
        self.register_font()

    def register_font(self):
        """ Registers the LiberationSerif font to be used in producing PDFs"""
        pdfmetrics.registerFont(TTFont('Liberation', 'LiberationSerif-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('LiberationBd', 'LiberationSerif-Bold.ttf'))
        pdfmetrics.registerFont(TTFont('LiberationIt', 'LiberationSerif-Italic.ttf'))
        pdfmetrics.registerFont(TTFont('LiberationBI', 'LiberationSerif-BoldItalic.ttf'))
        pdfmetrics.registerFontFamily('Liberation', normal='Liberation', bold='LiberationBd', italic='LiberationIt',
                                      boldItalic='LiberationBI')

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

    def ordered_corpora(self, m):
        """ Sets up the readable descendants in each corpus to be correctly ordered

        :param m: the metadata for the descendant
        :return: a tuple that will be put in the correct place in the ordered list when sorted
        """
        version = m.id.split('.')[-1]
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
            if par == 'na':
                par = '1' + par
            elif 'n' in par:
                par = '2' + par
            par = (par, full_par)
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], version]
        elif "elexicon" in m.id:
            par = m.parent.id.split('.')[-1][0].capitalize()
            metadata = [m.id, m.parent.id.split('.')[-1], self.LANGUAGE_MAPPING[m.lang]]
        else:
            par = re.sub(r'.*?(\d+\D?)\Z', r'\1', m.parent.id)
            if par.lstrip('0') == '':
                par = _('(Titel)')
            elif 'computus' in par:
                par = '057(Computus)'
            manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        return par, metadata, m

    def get_open_texts(self):
        """ Creates the lists of open and half-open texts to be used later. I have moved this to a function to try to
            cache it.

        :return: dictionary of all texts {collection: [readableDescendants]}, list of open texts, and half-open texts
        """
        open_texts = []
        half_open_texts = []
        all_texts = {m['id']: sorted([self.ordered_corpora(r) for r in self.resolver.getMetadata(m['id']).readableDescendants])
                     for l in self.sub_colls.values() for m in l}
        for c in all_texts.keys(): # [-1]: Add this once andecavensis is added back into OPEN_COLLECTIONS
            if c in self.OPEN_COLLECTIONS:
                open_texts += [x[1][0] for x in all_texts[c]]
            if c in self.HALF_OPEN_COLLECTIONS:
                half_open_texts += [x[1][0] for x in all_texts[c]]
        return all_texts, open_texts, half_open_texts

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

    def f_insert_in_list(self, l, i, v):
        """

        :param l: the list of values
        :param i: the index at which the item should be inserted
        :param v: the value that will be inserted
        :return: new list
        """
        l.insert(i, v)
        return l

    def r_set_language(self, code):
        """ Sets the session's language code which will be used for all requests

        :param code: The 2-letter language code
        :type code: str
        """
        session['locale'] = code
        refresh()
        if request.headers.get('X-Requested-With') == "XMLHttpRequest":
            return 'OK'
        else:
            flash('Language Changed. You may need to refresh the page in your browser.')
            return redirect(request.referrer)

    def r_reading_format(self, direction):
        """ Sets the session's language code which will be used for all requests

        :param code: The 2-letter language code
        :type code: str
        """
        session['reading_format'] = direction
        refresh()
        if request.headers.get('X-Requested-With') == "XMLHttpRequest":
            return 'OK'
        else:
            flash('Language Changed. You may need to refresh the page in your browser.')
            return redirect(request.referrer)

    def before_request(self):
        g.search_form = SearchForm()
        g.sub_colls = self.sub_colls
        g.open_texts = self.open_texts
        g.open_collections = self.OPEN_COLLECTIONS
        if not re.search('texts|search|assets|favicon|reading_format', request.url):
            session.pop('previous_search', None)

    def after_request(self, response):
        """ Currently used only for the Cache-Control header.

        """
        max_age = self.app.config['CACHE_MAX_AGE']
        if re.search('/(lang|auth)/', request.url):
            max_age = 0
        elif re.search('/assets/', request.url):
            max_age = 60 * 60 * 24
        response.cache_control.max_age = max_age
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

    def make_coins(self, collection, text, subreference="", lang=None):
        """ Creates a CoINS Title string from information

        :param collection: Collection to create coins from
        :param text: Text/Passage object
        :param subreference: Subreference
        :param lang: Locale information
        :return: Coins HTML title value
        """
        if lang is None:
            lang = self.__default_lang__
        return "url_ver=Z39.88-2004"\
                 "&ctx_ver=Z39.88-2004"\
                 "&rft_val_fmt=info%3Aofi%2Ffmt%3Akev%3Amtx%3Abook"\
                 "&rft_id={cid}"\
                 "&rft.genre=bookitem"\
                 "&rft.btitle={title}"\
                 "&rft.edition={edition}"\
                 "&rft.au={author}"\
                 "&rft.atitle={pages}"\
                 "&rft.language={language}"\
                 "&rft.pages={pages}".format(
                    title=quote(str(text.get_title(lang))), author=quote(str(text.get_creator(lang))),
                    cid=url_for("InstanceNemo.r_collection", objectId=collection.id, _external=True),
                    language=collection.lang, pages=quote(subreference), edition=quote(str(text.get_description(lang)))
                 )

    def r_collection(self, objectId, lang=None):
        data = super(NemoFormulae, self).r_collection(objectId, lang=lang)
        if self.check_project_team() is False:
            data['collections']['members'] = [x for x in data['collections']['members'] if x['id'] in self.OPEN_COLLECTIONS]
        if type(self.resolver.getMetadata(objectId)) == XmlCtsTextgroupMetadata:
            return redirect(url_for('InstanceNemo.r_corpus', objectId=objectId, lang=lang))
        if len(data['collections']['members']) == 1:
            return redirect(url_for('InstanceNemo.r_corpus', objectId=data['collections']['members'][0]['id'], lang=lang))
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
        for par, metadata, m in self.all_texts[collection.id]:
            if self.check_project_team() is True or m.id in self.open_texts:
                manuscript_data = [m.metadata.get_single(DC.source) or
                                   '{}<seg class="manuscript-number">{}</seg>'.format(metadata[2][0].title(),
                                                                                      metadata[2][1]),
                                   "manifest:" + m.id in self.app.picture_file]
                version = m.id.split('.')[-1]
                if 'lat' in version:
                    key = 'editions'
                elif 'deu' in version:
                    key = 'translations'
                else:
                    key = 'transcriptions'
                if par in r.keys():
                    r[par]["versions"][key].append(metadata + [manuscript_data])
                else:
                    work_name = par.lstrip('0') if type(par) is str else ''
                    if 'Computus' in work_name:
                        work_name = '(Computus)'
                    r[par] = {"short_regest": str(m.metadata.get_single(DCTERMS.abstract)) if 'andecavensis' in m.id else '',
                              # short_regest will change to str(m.get_cts_property('short-regest')) and
                              # regest will change to str(m.get_description()) once I have reconverted the texts
                              "regest": [str(m.get_description())] if 'andecavensis' in m.id else str(m.get_description()).split('***'),
                              "dating": str(m.metadata.get_single(DCTERMS.temporal)),
                              "ausstellungsort": str(m.metadata.get_single(DCTERMS.spatial)),
                              "versions": {'editions': [], 'translations': [], 'transcriptions': []},
                              'name': work_name}
                    r[par]["versions"][key].append(metadata + [manuscript_data])
        for k in r.keys():
            r[k]['versions']['transcriptions'] = sorted(sorted(r[k]['versions']['transcriptions'],
                                                               key=lambda x: int(x[2][1])),
                                                        key=lambda x: x[2][0])
        if len(r) == 0:
            flash(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))

        return_value = {
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
        return return_value

    def r_corpus_mv(self, objectId, lang=None):
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template and collections contained in given collection
        :rtype: {str: Any}
        """

        collection = self.resolver.getMetadata(objectId)
        ed_trans_mapping = {'lat001': _('Edition'), 'deu001': _('Übersetzung')}
        r = {'editions': [], 'translations': [], 'transcriptions': []}
        translations = {}
        forms = {}
        titles = {}
        edition_names = {}
        full_edition_names = {}
        regesten = {}
        template = "main::sub_collection_mv.html"
        list_of_readable_descendants = self.all_texts[collection.id]

        if 'markulf' in objectId or 'andecavensis' in objectId:
            for par, metadata, m in list_of_readable_descendants:
                if self.check_project_team() is True or m.id in self.open_texts:
                    edition = str(m.id).split(".")[-1]
                    title = str(list(m.parent.get_cts_property('title').values())[0])  # " ".join([m.metadata.get_single(DC.title).__str__().split(" ")[0], m.metadata.get_single(DC.title).__str__().split(" ")[1]])
                    form = str(m.id).split(".")[-2]
                    edition_name = ed_trans_mapping.get(edition, edition).title()
                    full_edition_name = " ".join(m.metadata.get_single(DC.title).__str__().split(" ")[2:])
                    regest = str(m.metadata.get_single(DCTERMS.abstract))

                    if edition not in translations.keys():
                        titles[edition] = [title]
                        translations[edition] = [m.id]
                        forms[edition] = [form]
                        edition_names[edition] = edition_name
                        full_edition_names[edition] = full_edition_name
                        regesten[edition] = [regest]
                    else:
                        titles[edition].append(title)
                        translations[edition].append(m.id)
                        forms[edition].append(form)
                        regesten[edition].append(regest)
            for k, v in translations.items():
                if k == 'lat001':
                    r['editions'].append({
                        "name": k,
                        "edition_name": edition_names[k],
                        "full_edition_name": full_edition_names[k],
                        "titles": titles[k],
                        "links": [forms[k], v],
                        "regesten": regesten[k]
                    })
                elif k == 'deu001':
                    r['translations'].append({
                        "name": k,
                        "edition_name": edition_names[k],
                        "full_edition_name": full_edition_names[k],
                        "titles": titles[k],
                        "links": [forms[k], v],
                        "regesten": regesten[k]
                    })
                else:
                    r['transcriptions'].append({
                        "name": k,
                        "edition_name": edition_names[k],
                        "full_edition_name": full_edition_names[k],
                        "titles": titles[k],
                        "links": [forms[k], v],
                        "regesten": regesten[k]
                    })

            r['transcriptions'] = sorted(sorted(r['transcriptions'], key=lambda x: int(re.search(r'\d+', x['name']).group(0))),
                                         key=lambda x: re.search(r'\D+', x['name']).group(0))


        else:

            r = {'editions': [], 'translations': [], 'transcriptions': []}
            flash(_('Diese View ist nur für MARKULF und ANDECAVENSIS verfuegbar'))

        return_value = {
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
        return return_value

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
        if type(collection) == XmlCtsTextgroupMetadata:
            return redirect(url_for('InstanceNemo.r_add_text_corpus', objectId=objectId,
                                    objectIds=objectIds, reffs=reffs, lang=lang))
        members = self.make_members(collection, lang=lang)
        if self.check_project_team() is False:
            members = [x for x in members if x['id'] in self.OPEN_COLLECTIONS]
        if len(members) == 1:
            return redirect(url_for('InstanceNemo.r_add_text_corpus', objectId=members[0]['id'], objectIds=objectIds,
                                    reffs=reffs, lang=lang))
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
        initial = self.r_corpus(objectId, lang=lang)
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

    def get_prev_next_texts(self, objId, collection):
        """ Get the previous and next texts in a collection

        :param objId: the ID of the current object
        :param collection: the grandparent of the current object (should be the collection, e.g., Freising or Markulf)
        :return: the IDs of the previous and next text in the same collection
        """
        if re.search(r'lat\d\d\d', objId.split('.')[-1]):
            sibling_texts = [x[1][0] for x in self.all_texts[collection['id']] if re.search(r'lat\d\d\d', x[1][0].split('.')[-1])]
        elif re.search(r'deu\d\d\d', objId.split('.')[-1]):
            sibling_texts = [x[1][0] for x in self.all_texts[collection['id']] if re.search(r'deu\d\d\d', x[1][0].split('.')[-1])]
        else:
            sibling_texts = [x[1][0] for x in self.all_texts[collection['id']] if x[1][0].split('.')[-1] == objId.split('.')[-1]]
        orig_index = sibling_texts.index(objId)
        return sibling_texts[orig_index - 1] if orig_index > 0 else None, \
               sibling_texts[orig_index + 1] if orig_index + 1 < len(sibling_texts) else None

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
        collection = self.get_collection(objectId)
        if isinstance(collection, CtsWorkMetadata):
            editions = [t for t in collection.children.values() if isinstance(t, CtsEditionMetadata)]
            if len(editions) == 0:
                raise UnknownCollection('{}.{}'.format(collection.get_label(lang), subreference) + _l(' hat keine Edition.'),
                                        objectId)
            objectId = str(editions[0].id)
            collection = self.get_collection(objectId)
        try:
            text = self.get_passage(objectId=objectId, subreference=subreference)
        except IndexError:
            new_subref = self.get_reffs(objectId)[0][0]
            text = self.get_passage(objectId=objectId, subreference=new_subref)
            flash('{}.{}'.format(collection.get_label(lang), subreference) + _l(' wurde nicht gefunden. Der ganze Text wird angezeigt.'))
            subreference = new_subref
        passage = self.transform(text, text.export(Mimetypes.PYTHON.ETREE), objectId)
        metadata = self.resolver.getMetadata(objectId=objectId)
        if 'notes' in self._transform:
            notes = self.extract_notes(passage)
        else:
            notes = ''
        prev, next = self.get_siblings(objectId, subreference, text)
        inRefs = []
        for inRef in sorted(metadata.metadata.get(DCTERMS.isReferencedBy)):
            ref = str(inRef).split('%')
            cits = ref[1:]
            for i, cit in enumerate(cits):
                cits[i] = Markup(Markup(cit))
            if ref[0] not in request.url:
                try:
                    inRefs.append([self.resolver.getMetadata(ref[0]), cits])
                except UnknownCollection:
                    inRefs.append(ref[0])
        return {
            "template": "main::text.html",
            "objectId": objectId,
            "subreference": subreference,
            "collections": {
                "current": {
                    "label": str(metadata.metadata.get_single(DC.title, lang=None)) or collection.get_label(lang),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                    "author": str(metadata.metadata.get_single(DC.creator, lang=None)) or text.get_creator(lang),
                    "title": text.get_title(lang),
                    "description": str(text.get_description(lang)) or '',
                    "coins": self.make_coins(collection, text, subreference, lang=lang),
                    "pubdate": str(metadata.metadata.get_single(DCTERMS.created, lang=lang)),
                    "publang": str(metadata.metadata.get_single(DC.language, lang=lang)),
                    "publisher": str(metadata.metadata.get_single(DC.publisher, lang=lang)),
                    'lang': collection.lang,
                    'citation': str(metadata.metadata.get_single(DCTERMS.bibliographicCitation, lang=lang)),
                    "short_regest": str(metadata.metadata.get_single(DCTERMS.abstract)) if 'andecavensis' in collection.id else '',
                    "dating": str(metadata.metadata.get_single(DCTERMS.temporal) or ''),
                    "issued_at": str(metadata.metadata.get_single(DCTERMS.spatial) or '')
                },
                "parents": self.make_parents(collection, lang=lang)
            },
            "text_passage": Markup(passage),
            "notes": Markup(notes),
            "prev": prev,
            "next": next,
            "open_regest": objectId not in self.half_open_texts,
            "urldate": "{:04}-{:02}-{:02}".format(date.today().year, date.today().month, date.today().day),
            "isReferencedBy": inRefs
        }

    def r_multipassage(self, objectIds, subreferences, lang=None):
        """ Retrieve the text of the passage

        :param objectIds: Collection identifiers separated by '+'
        :type objectIds: str
        :param lang: Lang in which to express main data
        :type lang: str
        :param subreferences: Reference identifiers separated by '+'
        :type subreferences: str
        :param result_sents: The list of sentences from elasticsearch results
        :type result_sents: str
        :param reading_format: The format to display multiple texts on the reading page: 'columns' or 'rows'
        :type reading_format: str
        :return: Template, collections metadata and Markup object representing the text
        :rtype: {str: Any}
        """
        if 'reading_format' not in session:
            session['reading_format'] = 'columns'
        ids = objectIds.split('+')
        translations = {}
        view = 1
        for i in ids:
            if "manifest" in i:
                i = re.sub(r'^manifest:', '', i)
            p = self.resolver.getMetadata(self.resolver.getMetadata(i).parent.id)
            translations[i] = [(m, m.metadata.get_single(DC.title)) for m in p.readableDescendants if m.id not in ids] + \
                              [(self.resolver.getMetadata(str(x)), self.resolver.getMetadata(str(x)).metadata.get_single(DC.title))
                               for x in self.resolver.getMetadata(objectId=i).metadata.get(DCTERMS.hasVersion)
                               if str(x) not in ids]
        passage_data = {'template': 'main::multipassage.html', 'objects': [], "translation": translations}
        subrefers = subreferences.split('+')
        for i, id in enumerate(ids):
            v = False
            if "manifest:" in id:
                id = re.sub(r'^manifest:', '', id)
                v = True
            if self.check_project_team() is True or id in self.open_texts:
                if subrefers[i] in ["all", 'first']:
                    subref = self.get_reffs(id)[0][0]
                else:
                    subref = subrefers[i]
                d = self.r_passage(id, subref, lang=lang)
                d['prev_version'], d['next_version'] = self.get_prev_next_texts(d['objectId'], d['collections']['parents'][1])
                del d['template']
                if v:
                    # This is when there are multiple manuscripts and the edition cannot be tied to any single one of them
                    if 'manifest:' + d['collections']['current']['id'] in self.app.picture_file:
                        formulae = self.app.picture_file['manifest:' + d['collections']['current']['id']]
                    else:
                        flash(_('Es gibt keine Manuskriptbilder für ') + d['collections']['current']['label'])
                        continue
                    if type(formulae) == list:
                        formulae = self.app.picture_file[formulae[0]]
                        flash(_('Diese Edition hat mehrere möglichen Manusckriptbilder. Nur ein Bild wird hier gezeigt.'))
                    # This should no longer be necessary since all manifests should be linked to a specific version id
                    # This is when there is a single manuscript for the transcription, edition, and translation
                    # elif 'manifest:' + d['collections']['parents'][0]['id'] in self.app.picture_file:
                    #    formulae = self.app.picture_file['manifest:' + d['collections']['parents'][0]['id']]
                    d["objectId"] = "manifest:" + id
                    d["div_v"] = "manifest" + str(view)
                    view = view + 1
                    del d['text_passage']
                    del d['notes']
                    # this viewer work when the library or archive give an IIIF API for the external usage of theirs books
                    d["manifest"] = url_for('viewer.static', filename=formulae["manifest"])
                    with open(self.app.config['IIIF_MAPPING'] + '/' + formulae['manifest']) as f:
                        this_manifest = json_load(f)
                    if 'fuldig.hs-fulda.de' in this_manifest['@id']:
                        # This works for resources from https://fuldig.hs-fulda.de/
                        d['lib_link'] = this_manifest['sequences'][0]['canvases'][0]['rendering']['@id']
                    elif 'gallica.bnf.fr' in this_manifest['@id']:
                        # This link needs to be constructed from the thumbnail link for images from https://gallica.bnf.fr/
                        d['lib_link'] = this_manifest['sequences'][0]['canvases'][0]['thumbnail']['@id'].replace('.thumbnail', '')
                    elif 'api.digitale-sammlungen.de' in this_manifest['@id']:
                        # This works for resources from the Bayerische Staatsbibliothek
                        # (and perhaps other German digital libraries?)
                        d['lib_link'] = this_manifest['sequences'][0]['canvases'][0]['@id'] + '/view'
                    d["title"] = formulae["title"] + ' {}{}'.format(this_manifest['sequences'][0]['canvases'][0]['label'],
                                                                    ' - ' +
                                                                    this_manifest['sequences'][0]['canvases'][-1]['label']
                                                                    if
                                                                    len(this_manifest['sequences'][0]['canvases']) > 1
                                                                    else '') + ' (' + d['collections']['current']['title'] + ')'
                else:
                    d["IIIFviewer"] = []
                    if "manifest:" + d['collections']['current']['id'] in self.app.picture_file:
                        manifests = self.app.picture_file["manifest:" + d['collections']['current']['id']]
                        if type(manifests) == dict:
                            d["IIIFviewer"] = [("manifest:" + d['collections']['current']['id'], manifests['title'])]
                        elif type(manifests) == list:
                            d["IIIFviewer"] = [(link, self.app.picture_file[link]['title']) for link in manifests]

                    if 'previous_search' in session:
                        result_sents = [x['sents'] for x in session['previous_search'] if x['id'] == id]
                        if result_sents:
                            d['text_passage'] = self.highlight_found_sents(d['text_passage'],
                                                                           self.convert_result_sents(result_sents))
                passage_data['objects'].append(d)
        if len(ids) > len(passage_data['objects']):
            flash(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
        return passage_data

    def convert_result_sents(self, result_sents):
        """ Remove extraneous markup and punctuation from the result_sents returned from the search page

        :param sents: the original 'result_sents' request argument
        :return: list of the individual sents with extraneous markup and punctuation removed
        """
        intermediate = []
        sents = result_sents[0]
        for sent in sents:
            sent = sent.replace('+', ' ').replace('%2C', '').replace('%2F', '').replace('%24', '$')
            sent = re.sub('strong|small', '', sent)
            sent = re.sub('\s+', ' ', sent)
            intermediate.append(sent)
        return [re.sub('[{}„“…]'.format(punctuation), '', x) for x in intermediate]

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
        m = re.search('/texts/([^/]+)/passage/([^/]+)', request.referrer) if "texts" in request.referrer else re.search('/viewer/([^/]+)', request.referrer)
        subreference = "1"
        d = self.r_passage(objectId, subreference, lang=lang)
        d['template'] = 'main::lexicon_modal.html'
        d['prev_texts'] = m.group(1).replace('%2B', '+')
        d['prev_reffs'] = m.group(2).replace('%2B', '+') if "texts" in request.referrer else "all"
        return d

    def r_impressum(self):
        """ Impressum route function

        :return: Template to use for Impressum page
        :rtype: {str: str}
        """
        return {"template": "main::impressum.html"}

    def r_bibliography(self):
        """ Bibliography route function

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::bibliography.html"}

    def r_contact(self):
        """ Contact route function

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::contact.html"}

    def r_man_desc(self, manuscript):
        """ Route for manuscript descriptions

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::{}_desc.html".format(manuscript)}

    def extract_notes(self, text):
        """ Constructs a dictionary that contains all notes with their ids. This will allow the notes to be
        rendered anywhere on the page and not only where they occur in the text.

        :param text: the string to be transformed
        :return: dict('note_id': 'note_content')
        """
        if '/lexicon/' in str(request.path):
            with open(self._transform['elex_notes']) as f:
                xslt = etree.XSLT(etree.parse(f))
        else:
            with open(self._transform['notes']) as f:
                xslt = etree.XSLT(etree.parse(f))

        return str(xslt(etree.fromstring(text)))

    def r_pdf(self, objectId):
        """Produces a PDF from the objectId for download and then delivers it

        :param objectId: the URN of the text to transform
        :return:
        """
        if self.check_project_team() is False and objectId not in self.open_texts:
            flash(_('Das PDF für diesen Text ist nicht zugänglich.'))
            return redirect(url_for('InstanceNemo.r_index'))
        is_formula = re.search(r'markulf|andecavensis|elexicon', objectId) is not None

        def add_citation_info(canvas, doc):
            cit_string = re.sub(r', \[UR[LI].*\]', '. ', str(metadata.metadata.get_single(DCTERMS.bibliographicCitation)))
            cit_string = re.sub(r'<span class="manuscript-number">(\d+)</span>', r'<sub>\1</sub>', cit_string)
            cit_string = re.sub(r'<span class="surname">', r'<span>', cit_string)
            cit_string += _('Heruntergeladen: ') + date.today().isoformat() + '.'
            cit_flowables = [Paragraph('[' + cit_string + ']', cit_style)]
            f = Frame(doc.leftMargin, doc.pagesize[1] - 0.5 * inch, doc.pagesize[0] - doc.leftMargin - doc.rightMargin, 0.5 * inch)
            canvas.saveState()
            if is_formula is True:
                canvas.drawImage(self.static_folder + 'images/logo_white.png',
                                 inch, inch, width=doc.pagesize[0] - doc.rightMargin,
                                 height=doc.pagesize[1] - 1.5 * inch)
            canvas.drawImage(self.static_folder + 'images/uhh-logo-web.gif',
                             doc.leftMargin, doc.pagesize[1] - 0.9 * inch, width=1.111 * inch, height=0.5 * inch,
                             mask=[255, 256, 255, 256, 255, 256])
            canvas.drawImage(self.static_folder + 'images/logo_226x113_white_bg.png',
                             (doc.pagesize[0] / 2) - 0.5 * inch, doc.pagesize[1] - 0.9 * inch, width=inch,
                             height=0.5 * inch, mask=[255, 256, 255, 256, 255, 256])
            canvas.drawImage(self.static_folder + 'images/adwhh200x113.jpg',
                             doc.pagesize[0] - doc.rightMargin - 0.88 * inch, doc.pagesize[1] - 0.9 * inch, width=.882 * inch,
                             height=0.5 * inch)
            f.addFromList(cit_flowables, canvas)
            canvas.setFont('Times-Roman', 8)
            canvas.drawCentredString(doc.pagesize[0] / 2, 0.75 * inch, '{}'.format(doc.page))
            canvas.restoreState()
        new_subref = self.get_reffs(objectId)[0][0]
        text = self.get_passage(objectId=objectId, subreference=new_subref)
        metadata = self.resolver.getMetadata(objectId=objectId)
        with open(self._transform['pdf']) as f:
            xslt = etree.XSLT(etree.parse(f))
        d = json_loads(re.sub(r'\s+', ' ', str(xslt(text.export(Mimetypes.PYTHON.ETREE)))))
        pdf_buffer = BytesIO()
        doc_title = re.sub(r'<span class="manuscript-number">(\w+)</span>', r'<sub>\1</sub>', str(metadata.metadata.get_single(DC.title, lang=None)))
        description = '{} ({})'.format(doc_title, date.today().isoformat())
        trans_table = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ẞ': 'Ss'}
        filename = ''
        for char in description:
            new_char = char
            if char in trans_table:
                new_char = trans_table[char]
            filename += new_char
        if objectId == "urn:cts:formulae:salzburg.hauthaler-a0001.lat001":
            txt_value = '\n\n'.join([re.sub(r'<.*?>', '', str(metadata.metadata.get_single(DCTERMS.bibliographicCitation))),
                                     doc_title,
                                     '\n\t'.join(d['paragraphs']),
                                     '\n'.join(d['app']),
                                     '\n'.join(d['hist_notes'])])
            return Response(txt_value, mimetype='text/plain',
                            headers={'Content-Disposition': 'attachment;filename={}.txt'.format(re.sub(r'\W+', '_', filename))})
        my_doc = SimpleDocTemplate(pdf_buffer, title=description)
        sample_style_sheet = getSampleStyleSheet()
        custom_style = copy(sample_style_sheet['Normal'])
        custom_style.name = 'Notes'
        custom_style.fontSize = 8
        custom_style.fontName = 'Liberation'
        cit_style = copy(sample_style_sheet['Normal'])
        cit_style.name = 'DocCitation'
        cit_style.fontSize = 8
        cit_style.alignment = 1
        sample_style_sheet['BodyText'].fontName = 'Liberation'
        encryption = EncryptionFlowable(userPassword='',
                                        ownerPassword=self.app.config['PDF_ENCRYPTION_PW'],
                                        canPrint=1,
                                        canAnnotate=0,
                                        canCopy=0,
                                        canModify=0)
        flowables = list()
        flowables.append(Paragraph(doc_title, sample_style_sheet['Heading1']))
        for p in d['paragraphs']:
            flowables.append(Paragraph(p, sample_style_sheet['BodyText']))
        if d['app']:
            flowables.append(Spacer(1, 5))
            flowables.append(HRFlowable())
            flowables.append(Spacer(1, 5))
            for n in d['app']:
                flowables.append(Paragraph(n, custom_style))
        if d['hist_notes']:
            flowables.append(Spacer(1, 5))
            flowables.append(HRFlowable())
            flowables.append(Spacer(1, 5))
            for n in d['hist_notes']:
                flowables.append(Paragraph(n, custom_style))
        if self.check_project_team() is False and is_formula is True:
            flowables.append(encryption)
        my_doc.build(flowables, onFirstPage=add_citation_info, onLaterPages=add_citation_info)
        pdf_value = pdf_buffer.getvalue()
        pdf_buffer.close()
        return Response(pdf_value, mimetype='application/pdf',
                        headers={'Content-Disposition': 'attachment;filename={}.pdf'.format(re.sub(r'\W+', '_', filename))})
