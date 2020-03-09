from flask import url_for, Markup, g, session, flash, request, Response, Blueprint
from flask_login import current_user, login_required
from flask_babel import _, refresh, get_locale
from flask_babel import lazy_gettext as _l
from babel.core import UnknownLocaleError
from werkzeug.utils import redirect
from flask_nemo import Nemo, filters
from rdflib.namespace import DCTERMS, DC, Namespace
from MyCapytain.common.constants import Mimetypes
from MyCapytain.resources.collections.capitains import XmlCapitainsReadableMetadata, XmlCapitainsCollectionMetadata
from MyCapytain.errors import UnknownCollection
from formulae.search.forms import SearchForm
from lxml import etree
from .errors.handlers import e_internal_error, e_not_found_error, e_unknown_collection_error
import re
from datetime import date
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
from typing import List, Tuple, Union, Match, Dict, Any, Sequence, Callable


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
        "r_index",
        # Controllers
        "get_inventory", "get_collection", "get_reffs", "get_passage", "get_siblings", "get_open_texts", "get_all_corpora",
        # Translator
        "semantic", "make_coins", "expose_ancestors_or_children", "make_members", "transform",
        # Business logic
        # "view_maker", "route", #"render",
    ]

    PROTECTED = [
        # "r_index", "r_collections", "r_collection", "r_references", "r_multipassage", "r_lexicon",
        # "r_add_text_collections", "r_add_text_collection", "r_corpus", "r_corpus_m", "r_add_text_corpus"
    ]

    OPEN_COLLECTIONS = ['urn:cts:formulae:andecavensis', 'urn:cts:formulae:buenden', 'urn:cts:formulae:elexicon',
                        'urn:cts:formulae:echternach', 'urn:cts:formulae:freising', 'urn:cts:formulae:fu2',
                        'urn:cts:formulae:fulda_dronke', 'urn:cts:formulae:fulda_stengel', 'urn:cts:formulae:hersfeld',
                        'urn:cts:formulae:lorsch', 'urn:cts:formulae:luzern', 'urn:cts:formulae:mittelrheinisch',
                        'urn:cts:formulae:mondsee', 'urn:cts:formulae:passau', 'urn:cts:formulae:regensburg',
                        'urn:cts:formulae:rheinisch', 'urn:cts:formulae:salzburg', 'urn:cts:formulae:schaeftlarn',
                        'urn:cts:formulae:stgallen', 'urn:cts:formulae:weissenburg', 'urn:cts:formulae:werden',
                        'urn:cts:formulae:zuerich']

    HALF_OPEN_COLLECTIONS = ['urn:cts:formulae:buenden', 'urn:cts:formulae:echternach', 'urn:cts:formulae:fulda_stengel',
                             'urn:cts:formulae:lorsch', 'urn:cts:formulae:mondsee', 'urn:cts:formulae:regensburg',
                             'urn:cts:formulae:rheinisch', 'urn:cts:formulae:salzburg', 'urn:cts:formulae:weissenburg',
                             'urn:cts:formulae:werden']

    LANGUAGE_MAPPING = {"lat": _l('Latein'), "deu": _l("Deutsch"), "fre": _l("Französisch"),
                        "eng": _l("Englisch"), "cat": _l("Katalanisch")}

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

    @staticmethod
    def register_font():
        """ Registers the LiberationSerif font to be used in producing PDFs"""
        pdfmetrics.registerFont(TTFont('Liberation', 'LiberationSerif-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('LiberationBd', 'LiberationSerif-Bold.ttf'))
        pdfmetrics.registerFont(TTFont('LiberationIt', 'LiberationSerif-Italic.ttf'))
        pdfmetrics.registerFont(TTFont('LiberationBI', 'LiberationSerif-BoldItalic.ttf'))
        pdfmetrics.registerFontFamily('Liberation', normal='Liberation', bold='LiberationBd', italic='LiberationIt',
                                      boldItalic='LiberationBI')

    def get_all_corpora(self) -> Dict[str, List[XmlCapitainsCollectionMetadata]]:
        """ A convenience function to return all sub-corpora in all collections

        :return: dictionary with all the collections as keys and a list of the corpora in the collection as values
        """
        colls = {}
        for member in self.make_members(self.resolver.getMetadata(), lang=None):
            members = self.make_members(self.resolver.getMetadata(member['id']))
            for m in members:
                m.update({'short_title':
                              str(self.resolver.getMetadata(m['id']).metadata.get_single(self.BIBO.AbbreviatedTitle))})
            colls[member['id']] = sorted(members, key=lambda x: self.sort_transcriptions(self.resolver.id_to_coll[x['id']]))
        return colls

    @staticmethod
    def sort_folia(matchobj: Match) -> str:
        """Sets up the folia ranges of manuscripts for better sorting"""
        groups = []
        sub_groups = re.search(r'(\d+)([rvab]+)', matchobj.group(1)).groups()
        groups.append('{:04}{}'.format(int(sub_groups[0]), sub_groups[1]))
        if matchobj.group(2):
            groups.append(matchobj.group(2))
        return '-'.join(groups)

    def ordered_corpora(self, m: XmlCapitainsReadableMetadata, collection: XmlCapitainsCollectionMetadata)\
            -> Tuple[Union[str, Tuple[str, Tuple[str, str]]],
                     Union[List[Sequence[str]], list],
                     XmlCapitainsReadableMetadata]:
        """ Sets up the readable descendants in each corpus to be correctly ordered

        :param m: the metadata for the descendant
        :param collection: the collection to which readable collection belongs
        :return: a tuple that will be put in the correct place in the ordered list when sorted
        """
        version = m.id.split('.')[-1]
        if "salzburg" in m.id:
            par = list(m.parent)[0].split('-')[1:]
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
            parent_0 = list(m.parent)[0]
            par = parent_0.split('.')[-1][0].capitalize()
            metadata = [m.id, parent_0.split('.')[-1], self.LANGUAGE_MAPPING[m.lang]]
        elif 'transcription' in m.subtype:
            if 'andecavensis' in m.id:
                if collection in m.id:
                    form_num = [x for x in self.resolver.id_to_coll[list(m.parent)[0]].parent if collection in x][0]
                    par = re.sub(r'.*?(\d+\D?)\Z', r'\1', form_num)
                    if par.lstrip('0') == '':
                        par = _('(Titel)')
                    elif 'computus' in par:
                        par = '057(Computus)'
                else:
                    par = re.sub(r'.*?(\d+[rvab]+)(\d+[rvab]+)?\Z', self.sort_folia, list(m.parent)[0])
                manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            else:
                if collection in m.id:
                    par = re.sub(r'.*?(\d+[rvab]+)(\d+[rvab]+)?\Z', self.sort_folia, list(m.parent)[0])
                    manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
                else:
                    form_num = [x for x in self.resolver.id_to_coll[list(m.parent)[0]].parent if collection in x][0]
                    par = re.sub(r'.*?(\d+\D?)\Z', r'\1', form_num)
                    if par.lstrip('0') == '':
                        par = _('(Prolog)')
                    manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        elif 'katalonien' in m.id:
            par = list(m.parent)[0].split('_')[-1]
            manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        else:
            par = re.sub(r'.*?(\d+\D?)\Z', r'\1', list(m.parent)[0])
            if par.lstrip('0') == '':
                if 'andecavensis' in m.id:
                    par = _('(Titel)')
                else:
                    par = _('(Prolog)')
            elif 'computus' in par:
                par = '057(Computus)'
            manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        return par, metadata, m

    def get_open_texts(self) -> Tuple[Dict[str, Tuple[Union[str, Tuple[str, Tuple[str, str]]],
                                                      Union[List[Sequence[str]], list],
                                                      XmlCapitainsReadableMetadata]],
                                      Dict[str, Tuple[Union[str, Tuple[str, Tuple[str, str]]],
                                                      Union[List[Sequence[str]], list],
                                                      XmlCapitainsReadableMetadata]],
                                      Dict[str, Tuple[Union[str, Tuple[str, Tuple[str, str]]],
                                                      Union[List[Sequence[str]], list],
                                                      XmlCapitainsReadableMetadata]]]:
        """ Creates the lists of open and half-open texts to be used later. I have moved this to a function to try to
            cache it.

        :return: dictionary of all texts {collection: [readableDescendants]}, list of open texts, and half-open texts
        """
        open_texts = []
        half_open_texts = []
        all_texts = {m['id']: sorted([self.ordered_corpora(r, m['id']) for r in self.resolver.getMetadata(m['id']).readableDescendants.values()])
                     for l in self.sub_colls.values() for m in l if m['id'] != 'urn:cts:formulae:katalonien'}
        all_texts.update({m: sorted([self.ordered_corpora(r, m) for r in self.resolver.getMetadata(m).readableDescendants.values()])
                          for m in self.resolver.children['urn:cts:formulae:katalonien']})
        for c in all_texts.keys():
            if c in self.OPEN_COLLECTIONS:
                open_texts += [x[1][0] for x in all_texts[c]]
            if c in self.HALF_OPEN_COLLECTIONS:
                half_open_texts += [x[1][0] for x in all_texts[c]]
        return all_texts, open_texts, half_open_texts

    @staticmethod
    def check_project_team() -> bool:
        """ A convenience function that checks if the current user is a part of the project team"""
        try:
            return current_user.project_team is True
        except AttributeError:
            return False

    def create_blueprint(self) -> Blueprint:
        """ Enhance original blueprint creation with error handling

        :rtype: flask.Blueprint
        """
        blueprint = super(NemoFormulae, self).create_blueprint()
        blueprint.register_error_handler(UnknownCollection, e_unknown_collection_error)
        return blueprint

    def get_locale(self) -> str:
        """ Retrieve the best matching locale using request headers

        .. note:: Probably one of the thing to enhance quickly.

        :rtype: str
        """
        try:
            best_match = str(get_locale())
        except UnknownLocaleError:
            best_match = 'de'
        lang = self.__default_lang__
        if best_match == "de":
            lang = "ger"
        elif best_match == "fr":
            lang = "fre"
        elif best_match == "en":
            lang = "eng"
        return lang

    @staticmethod
    def f_remove_from_list(l: list, i: Any) -> list:
        """ remove item "i" from list "l"

        :param l: the list
        :param i: the item
        :return: the list without the item
        """
        l.remove(i)
        return l

    @staticmethod
    def f_join_list_values(l: list, s: str) -> str:
        """ join the values of "l" user the separator "s"

        :param l: the list of values
        :param s: the separator
        :return: a string of the values joined by the separator
        """
        new_list = [str(x) for x in l]
        return s.join(new_list).strip(s)

    @staticmethod
    def f_replace_indexed_item(l: list, i: int, v: Any) -> list:
        """

        :param l: the list of values
        :param i: the index to be replace
        :param v: the value with which the indexed value will be replaced
        :return: new list
        """
        l[i] = v
        return l

    @staticmethod
    def f_insert_in_list(l: list, i: int, v: Any) -> list:
        """

        :param l: the list of values
        :param i: the index at which the item should be inserted
        :param v: the value that will be inserted
        :return: new list
        """
        l.insert(i, v)
        return l

    @staticmethod
    def r_set_language(code: str) -> Union[str, redirect]:
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

    @staticmethod
    def r_reading_format(direction: str) -> Union[str, redirect]:
        """ Sets the reading direction of the texts in the multipassage view

        :param direction: a string representing whether the texts are listed in 'rows' or 'columns'
        """
        session['reading_format'] = direction
        refresh()
        if request.headers.get('X-Requested-With') == "XMLHttpRequest":
            return 'OK'
        else:
            flash(_('Reading direction changed. You may need to refresh the page in your browser.'))
            return redirect(request.referrer)

    def before_request(self):
        g.search_form = SearchForm()
        g.sub_colls = self.sub_colls
        g.open_texts = self.open_texts
        g.open_collections = self.OPEN_COLLECTIONS
        if not re.search('texts|search|assets|favicon|reading_format', request.url):
            session.pop('previous_search', None)

    def after_request(self, response: Response) -> Response:
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

    def view_maker(self, name: str, instance=None) -> Callable:
        """ Create a view

        :param name: Name of the route function to use for the view.
        :param instance: The Flask instance for which to create the view function
        :return: Route function which makes use of Nemo context (such as menu informations)
        """
        # Avoid copy-pasta and breaking upon Nemo inside code changes by reusing the original view_maker function
        # Super will go to the parent class and you will use it's "view_maker" function
        route = super(NemoFormulae, self).view_maker(name, instance)
        if name in self.PROTECTED:
            route = login_required(route)
        return route

    def semantic(self, collection: Union[XmlCapitainsCollectionMetadata, XmlCapitainsReadableMetadata],
                 parent: XmlCapitainsCollectionMetadata=None) -> str:
        """ Generates a SEO friendly string for given collection

        :param collection: Collection object to generate string for
        :param parent: Current collection parent
        :return: SEO/URL Friendly string
         """
        # The order of the ancestors isn't kept in MyCap v3 (ancestors is a dictionary)
        #  So the reversing of the list of parent values probably doesn't make much sense here.
        if parent is not None:
            collections = list(parent.ancestors.values())[::-1] + [parent, collection]
        else:
            collections = list(collection.ancestors.values())[::-1] + [collection]

        return filters.slugify("--".join([item.get_label() for item in collections if item.get_label()]))

    def make_coins(self, collection: Union[XmlCapitainsCollectionMetadata, XmlCapitainsReadableMetadata],
                   text: XmlCapitainsReadableMetadata, subreference: str="", lang: str=None) -> str:
        """ Creates a CoINS Title string from information

        :param collection: Collection to create coins from
        :param text: Text/Passage object
        :param subreference: Subreference
        :param lang: Locale information
        :return: Coins HTML title value
        """
        if lang is None:
            lang = self.__default_lang__
        return "url_ver=Z39.88-2004" \
               "&ctx_ver=Z39.88-2004" \
               "&rft_val_fmt=info%3Aofi%2Ffmt%3Akev%3Amtx%3Abook" \
               "&rft_id={cid}" \
               "&rft.genre=bookitem" \
               "&rft.btitle={title}" \
               "&rft.edition={edition}"\
               "&rft.au={author}" \
               "&rft.atitle={pages}" \
               "&rft.language={language}" \
               "&rft.pages={pages}".format(
                    title=quote(str(text.get_title(lang))), author=quote(str(text.get_creator(lang))),
                    cid=url_for("InstanceNemo.r_collection", objectId=collection.id, _external=True),
                    language=collection.lang, pages=quote(subreference), edition=quote(str(text.get_description(lang)))
                 )

    @staticmethod
    def sort_parents(d: Dict[str, Union[str, int]]) -> int:
        """ Sort parents from closest to furthest"""
        if d['id'] in ['formulae_collection', 'other_collection', 'lexicon_entries']:
            return 3
        if len(d['id'].split('.')) == 1:
            return 2
        return 1

    def make_parents(self, collection: Union[XmlCapitainsCollectionMetadata, XmlCapitainsReadableMetadata],
                     lang: str=None) -> List[Dict[str, Union[str, int]]]:
        """ Build parents list for given collection

        :param collection: Collection to build dict view of for its members
        :param lang: Language to express data in
        :return: List of basic objects
        """
        parents = [
            {
                "id": member.id,
                "label": str(member.get_label(lang)),
                "model": str(member.model),
                "type": str(member.type),
                "size": member.size,
                "subtype": member.subtype
            }
            for member in collection.ancestors.values()
            if member.get_label()
        ]
        parents = sorted(parents, key=self.sort_parents)
        return parents

    def r_collection(self, objectId: str, lang: str=None) -> Dict[str, Any]:
        data = super(NemoFormulae, self).r_collection(objectId, lang=lang)
        if self.check_project_team() is False:
            data['collections']['members'] = [x for x in data['collections']['members'] if x['id'] in self.OPEN_COLLECTIONS]
        if 'katalonien' not in objectId and 'defaultTic' not in [x for x in self.resolver.getMetadata(objectId).parent]:
            return redirect(url_for('InstanceNemo.r_corpus', objectId=objectId, lang=lang))
        if len(data['collections']['members']) == 1:
            return redirect(url_for('InstanceNemo.r_corpus', objectId=data['collections']['members'][0]['id'], lang=lang))
        data['template'] = "main::sub_collections.html"
        return data

    def r_corpus(self, objectId: str, lang: str=None) -> Dict[str, Any]:
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
        template = "main::sub_collection.html"
        if 'elexicon' in objectId:
            template = "main::elex_collection.html"
        elif 'salzburg' in objectId:
            template = "main::salzburg_collection.html"
        elif objectId == "urn:cts:formulae:katalonien":
            return redirect(url_for('InstanceNemo.r_collection', objectId=objectId, lang=lang))
        for par, metadata, m in self.all_texts[collection.id]:
            if self.check_project_team() is True or m.id in self.open_texts:
                manuscript_data = [m.metadata.get_single(DC.source) or
                                   '{}<seg class="manuscript-number">{}</seg>'.format(metadata[2][0].title(),
                                                                                      metadata[2][1]),
                                   "manifest:" + m.id in self.app.picture_file]
                if 'cts:edition' in m.subtype:
                    key = 'editions'
                elif 'cts:translation' in m.subtype:
                    key = 'translations'
                else:
                    key = 'transcriptions'
                if par in r.keys():
                    r[par]["versions"][key].append(metadata + [manuscript_data])
                else:
                    work_name = par.lstrip('0') if type(par) is str else ''
                    if 'Computus' in work_name:
                        work_name = '(Computus)'
                    elif 'Titel' in work_name:
                        work_name = _('(Titel)')
                    elif 'Prolog' in work_name:
                        work_name = _('(Prolog)')
                    elif 'urn:cts:formulae:lorsch' in m.ancestors:
                        name_part = re.search(r'(Kap\.|Nr\.).*', str(m.metadata.get_single(DC.title)))
                        if name_part:
                            work_name = name_part.group(0)
                    r[par] = {"short_regest": str(m.metadata.get_single(DCTERMS.abstract)) if 'andecavensis' in m.id else '',
                              "regest": [str(m.metadata.get_single(DC.description))] if 'andecavensis' in m.id else str(m.metadata.get_single(DC.description)).split('***'),
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
            if 'manuscript_collection' in collection.ancestors:
                flash(_('Um das Digitalisat dieser Handschrift zu sehen, besuchen Sie bitte gegebenenfalls die Homepage der Bibliothek.'))
            else:
                flash(_('Diese Sammlung ist nicht öffentlich zugänglich.'))

        current_parents = self.make_parents(collection, lang=lang)

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
                "parents": current_parents,
                "parent_ids": [x['id'] for x in current_parents]
            }
        }
        return return_value

    def r_corpus_mv(self, objectId: str, lang: str=None) -> Dict[str, Any]:
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

        if 'marculf' in objectId or 'andecavensis' in objectId:
            for par, metadata, m in list_of_readable_descendants:
                if self.check_project_team() is True or m.id in self.open_texts:
                    edition = str(m.id).split(".")[-1]
                    if 'marculf' in objectId and 'marculf' not in m.id:
                        edition = str(m.id).split(':')[-1].split('.')[0]
                    ed_parent = sorted([(k, v) for k, v in m.ancestors.items() if objectId in k])[-1][-1]
                    title = str(ed_parent.metadata.get_single(DC.title, lang=lang))
                    form = ed_parent.id
                    edition_name = ed_trans_mapping.get(edition, edition).title()
                    full_edition_name = re.sub(r'{}|\(lat\)|\(deu\)'.format(title), '', str(m.metadata.get_single(DC.title))).strip()
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
            flash(_('Diese View ist nur für MARCULF und ANDECAVENSIS verfuegbar'))

        if r == {'editions': [], 'translations': [], 'transcriptions': []}:
            flash(_('Diese Sammlung ist nicht öffentlich zugänglich.'))

        current_parents = self.make_parents(collection, lang=lang)

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
                "parents": current_parents,
                "parent_ids": [x['id'] for x in current_parents]
            }
        }
        return return_value

    def r_add_text_collections(self, objectIds: str, reffs: str, lang: str=None) -> Dict[str, Any]:
        """ Retrieve the top collections of the inventory

        :param objectIds: the object ids from the previous view separated by '+'
        :param reffs: the citation references from the objects in the previous view seperated by '+'
        :param lang: Lang in which to express main data
        :return: Collections information and template
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

    def r_add_text_collection(self, objectId: str, objectIds: str, reffs: str, lang: str=None) -> Dict[str, Any]:
        """ Route to browse a top-level collection and add another text to the view

        :param objectId: the id of the collection from which the new text for the reading view should be added
        :param objectIds: the object ids from the previous view separated by '+'
        :param reffs: the citation references from the objects in the previous view seperated by '+'
        :param lang: Lang in which to express main data
        :return: Template and collections contained in given collection
        """
        collection = self.resolver.getMetadata(objectId)
        if 'defaultTic' not in collection.parent:
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

    def r_add_text_corpus(self, objectId: str, objectIds: str, reffs: str, lang: str=None) -> Dict[str, Any]:
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

    def get_first_passage(self, objectId: str) -> str:
        """ Provides a redirect to the first passage of given objectId

        :param objectId: Collection identifier
        :type objectId: str
        :return: Redirection to the first passage of given text
        """
        collection, reffs = self.get_reffs(objectId=objectId, export_collection=True)
        first, _ = reffs[0]
        return str(first)

    def get_prev_next_texts(self, objectId: str) -> Tuple[str, str]:
        """ Get the previous and next texts in a collection

        :param objectId: the ID of the current object
        :return: the IDs of the previous and next text in the same collection
        """
        id_parts = objectId.split('.')
        if re.search(r'lat\d\d\d', id_parts[-1]):
            sibling_texts = [x[1][0] for x in self.all_texts[id_parts[0]] if re.search(r'{}.*lat\d\d\d'.format(id_parts[0]), x[1][0])]
        elif re.search(r'deu\d\d\d', id_parts[-1]):
            sibling_texts = [x[1][0] for x in self.all_texts[id_parts[0]] if re.search(r'{}.*deu\d\d\d'.format(id_parts[0]), x[1][0])]
        else:
            sibling_texts = [x[1][0] for x in self.all_texts[id_parts[0]] if x[1][0].split('.')[-1] == id_parts[-1]]
        orig_index = sibling_texts.index(objectId)
        return sibling_texts[orig_index - 1] if orig_index > 0 else None, \
               sibling_texts[orig_index + 1] if orig_index + 1 < len(sibling_texts) else None

    def get_readable_siblings(self, obj: XmlCapitainsReadableMetadata) -> List[XmlCapitainsReadableMetadata]:
        """ Returns the readable children of every ancestor.
        This assumes that any direct readable descendants that an ancestor has will also be readable siblings to the
        collection.

        :param obj: the collection for which to find siblings
        :return: the list of siblings
        """
        siblings = []
        for ancestor in obj.ancestors.values():
            siblings += [x for x in ancestor.children.values() if x.readable]
        return siblings

    def sort_transcriptions(self, obj: Union[XmlCapitainsReadableMetadata,
                                             XmlCapitainsCollectionMetadata]) -> Tuple[str, int]:
        """ Return sortable tuple for the transcriptions of an object """
        identifier = obj.id
        manuscript_id = identifier.split(':')[-1].split('.')[0]
        parts = re.search(r'(\D+)?(\d+)?', manuscript_id).groups('0')
        return parts[0], int(parts[1])

    def get_transcriptions(self, obj: XmlCapitainsReadableMetadata) -> List[XmlCapitainsReadableMetadata]:
        """ Returns any manuscript transcriptions that are associated with this text

        :param obj: the readable collection for which to find transcriptions
        :return: the list of transcriptions
        """
        transcriptions = []
        for parent in obj.parent:
            parent_obj = self.resolver.id_to_coll[parent]
            transcriptions += [v for v in parent_obj.descendants.values() if 'transcription' in v.subtype]
        return sorted(transcriptions, key=self.sort_transcriptions)

    def r_passage(self, objectId: str, subreference: str, lang: str=None) -> Dict[str, Any]:
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
        metadata = self.get_collection(objectId)
        if isinstance(metadata, XmlCapitainsCollectionMetadata):
            editions = [t for t in metadata.children.values() if isinstance(t, XmlCapitainsReadableMetadata) and 'cts:edition' in t.subtype]
            if len(editions) == 0:
                raise UnknownCollection('{}.{}'.format(metadata.get_label(lang), subreference) + _l(' hat keine Edition.'),
                                        objectId)
            objectId = str(editions[0].id)
            metadata = self.get_collection(objectId)
        try:
            text = self.get_passage(objectId=objectId, subreference=subreference)
        except IndexError:
            new_subref = self.get_reffs(objectId)[0][0]
            text = self.get_passage(objectId=objectId, subreference=new_subref)
            flash('{}, {}'.format(metadata.get_label(lang), subreference) + _l(' wurde nicht gefunden. Der ganze Text wird angezeigt.'))
            subreference = new_subref
        passage = self.transform(text, text.export(Mimetypes.PYTHON.ETREE), objectId)
        # metadata1 = self.resolver.getMetadata(objectId=objectId)
        if 'notes' in self._transform:
            notes = self.extract_notes(passage)
        else:
            notes = ''
        prev, next = self.get_siblings(objectId, subreference, text)
        inRefs = []
        for inRef in sorted(metadata.metadata.get(DCTERMS.isReferencedBy)):
            ref = str(inRef).split('%')[1:]
            cits = ref[1:]
            for i, cit in enumerate(cits):
                cits[i] = Markup(Markup(cit))
            if ref[0] not in request.url:
                try:
                    inRefs.append([self.resolver.getMetadata(ref[0]), cits])
                except UnknownCollection:
                    inRefs.append(ref[0])
        translations = [(m, m.metadata.get_single(DC.title)) for m in self.get_readable_siblings(metadata)] + \
                       [(self.resolver.getMetadata(str(x)), self.resolver.getMetadata(str(x)).metadata.get_single(DC.title))
                        for x in metadata.metadata.get(DCTERMS.hasVersion)]
        transcriptions = [(m, m.metadata.get_single(DC.title)) for m in self.get_transcriptions(metadata)]
        current_parents = self.make_parents(metadata, lang=lang)
        return {
            "template": "main::text.html",
            "objectId": objectId,
            "subreference": subreference,
            "collections": {
                "current": {
                    "label": str(metadata.metadata.get_single(DC.title, lang=None)) or metadata.get_label(lang),
                    "id": metadata.id,
                    "model": str(metadata.model),
                    "type": str(metadata.type),
                    "author": str(metadata.metadata.get_single(DC.creator, lang=None)) or text.get_creator(lang),
                    "title": text.get_title(lang),
                    "description": str(metadata.metadata.get_single(DC.description)) or '',
                    "coins": self.make_coins(metadata, text, subreference, lang=lang),
                    "pubdate": str(metadata.metadata.get_single(DCTERMS.created, lang=lang)),
                    "publang": str(metadata.metadata.get_single(DC.language, lang=lang)),
                    "publisher": str(metadata.metadata.get_single(DC.publisher, lang=lang)),
                    'lang': metadata.lang,
                    'citation': str(metadata.metadata.get_single(DCTERMS.bibliographicCitation, lang=lang)),
                    "short_regest": str(metadata.metadata.get_single(DCTERMS.abstract)) if 'andecavensis' in metadata.id else '',
                    "dating": str(metadata.metadata.get_single(DCTERMS.temporal) or ''),
                    "issued_at": str(metadata.metadata.get_single(DCTERMS.spatial) or '')
                },
                "parents": current_parents,
                "parent_ids": [x['id'] for x in current_parents]
            },
            "text_passage": Markup(passage),
            "notes": Markup(notes),
            "prev": prev,
            "next": next,
            "open_regest": objectId not in self.half_open_texts,
            "urldate": "{:04}-{:02}-{:02}".format(date.today().year, date.today().month, date.today().day),
            "isReferencedBy": inRefs,
            "translations": translations + transcriptions,
            "transcriptions": [x[0] for x in transcriptions]
        }

    def r_multipassage(self, objectIds: str, subreferences: str, lang: str=None) -> Dict[str, Any]:
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
        passage_data = {'template': 'main::multipassage.html', 'objects': [], "translation": {}}
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
                d['prev_version'], d['next_version'] = self.get_prev_next_texts(d['objectId'])
                del d['template']
                translations[id] = [x for x in d.pop('translations', None) if x[0].id not in ids]
                if v:
                    # This is when there are multiple manuscripts and the edition cannot be tied to any single one of them
                    if 'manifest:' + d['collections']['current']['id'] in self.app.picture_file:
                        formulae = self.app.picture_file['manifest:' + d['collections']['current']['id']]
                    else:
                        flash(_('Es gibt keine Manuskriptbilder für ') + d['collections']['current']['label'])
                        continue
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
                                                                    else '')
                else:
                    d["IIIFviewer"] = []
                    for transcription in d['transcriptions']:
                        if "manifest:" + transcription.id in self.app.picture_file:
                            manifests = self.app.picture_file["manifest:" + transcription.id]
                            d["IIIFviewer"].append(("manifest:" + transcription.id, manifests['title']))

                    if 'previous_search' in session:
                        result_sents = [x for x in session['previous_search'] if x['id'] == id]
                        if result_sents:
                            d['text_passage'] = self.highlight_found_sents(d['text_passage'], result_sents[0])
                passage_data['objects'].append(d)
        if len(ids) > len(passage_data['objects']):
            flash(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
        passage_data['translation'] = translations
        return passage_data

    @staticmethod
    def highlight_found_sents(html: str, results: Dict[str, Union[List[str], str]]) -> str:
        """ Adds "searched" to the classList of words in "sents" from elasticsearch results

        :param html: the marked-up text to be searched
        :param results: the previous search session information from the session
        :return: transformed html
        """
        root = etree.fromstring(html)
        spans = root.xpath('//span[contains(@class, "w")]')
        for sent_index, sent in enumerate(results['sents']):
            for span_index, i in enumerate(results['sentence_spans'][sent_index]):
                if span_index == 0 and 'searched-start' not in spans[i].get('class'):
                    spans[i].set('class', spans[i].get('class') + ' searched-start')
                elif spans[i - 1].getparent() != spans[i].getparent() and 'searched-start' not in spans[i].get('class'):
                    spans[i].set('class', spans[i].get('class') + ' searched-start')
                if len(spans) > i + 1 and spans[i + 1].getparent() != spans[i].getparent():
                    if 'searched-end' not in spans[i].get('class'):
                        spans[i].set('class', spans[i].get('class') + ' searched-end')
            if 'searched-end' not in spans[i].get('class'):
                spans[i].set('class', spans[i].get('class') + ' searched-end')
        xml_string = etree.tostring(root, encoding=str, method='html', xml_declaration=None, pretty_print=False,
                                    with_tail=True, standalone=None)
        span_pattern = re.compile(r'(<span class="w [\w\-]*\s?searched-start.*?searched-end".*?</span>)', re.DOTALL)
        xml_string = re.sub(span_pattern, r'<span class="searched">\1</span>', xml_string)
        return Markup(xml_string)

    def r_lexicon(self, objectId: str, lang: str=None) -> Dict[str, Any]:
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

    @staticmethod
    def r_impressum() -> Dict[str, str]:
        """ Impressum route function

        :return: Template to use for Impressum page
        :rtype: {str: str}
        """
        return {"template": "main::impressum.html"}

    @staticmethod
    def r_bibliography() -> Dict[str, str]:
        """ Bibliography route function

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::bibliography.html"}

    @staticmethod
    def r_contact() -> Dict[str, str]:
        """ Contact route function

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::contact.html"}

    @staticmethod
    def r_man_desc(manuscript: str) -> Dict[str, str]:
        """ Route for manuscript descriptions

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::{}_desc.html".format(manuscript)}

    def extract_notes(self, text: str) -> str:
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

    def r_pdf(self, objectId: str) -> Response:
        """Produces a PDF from the objectId for download and then delivers it

        :param objectId: the URN of the text to transform
        :return:
        """
        if self.check_project_team() is False and objectId not in self.open_texts:
            flash(_('Das PDF für diesen Text ist nicht zugänglich.'))
            return redirect(url_for('InstanceNemo.r_index'))
        is_formula = re.search(r'marculf|andecavensis|elexicon', objectId) is not None

        def add_citation_info(canvas, doc):
            cit_string = '<font color="grey">' + re.sub(r',?\s+\[URL:[^\]]+\]', '', str(metadata.metadata.get_single(DCTERMS.bibliographicCitation))) + '</font>' + '<br/>'
            cit_string += '<font color="grey">URL: https://werkstatt.formulae.uni-hamburg.de' + url_for("InstanceNemo.r_multipassage", objectIds=objectId, subreferences='1') + '</font>' + '<br/>'
            cit_string += '<font color="grey">' + _('Heruntergeladen: ') + date.today().isoformat() + '</font>'
            cit_string = re.sub(r'<span class="manuscript-number">(\d+)</span>', r'<sub>\1</sub>', cit_string)
            cit_string = re.sub(r'<span class="surname">([^<]+)</span>', r'<b>\1</b>', cit_string)
            cit_flowables = [Paragraph(cit_string, cit_style)]
            f = Frame(doc.leftMargin - .9 * inch, 0.01 * inch, doc.pagesize[0] - .2 * inch, 0.7 * inch, showBoundary=0)
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
        with open(self._transform['pdf']) as xml_file:
            xslt = etree.XSLT(etree.parse(xml_file))
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
        my_doc = SimpleDocTemplate(pdf_buffer, title=description)
        sample_style_sheet = getSampleStyleSheet()
        custom_style = copy(sample_style_sheet['Normal'])
        custom_style.name = 'Notes'
        custom_style.fontSize = 10
        custom_style.fontName = 'Liberation'
        cit_style = copy(sample_style_sheet['Normal'])
        cit_style.name = 'DocCitation'
        cit_style.fontSize = 8
        cit_style.alignment = 1
        cit_style.leading = 9.6
        sample_style_sheet['BodyText'].fontName = 'Liberation'
        sample_style_sheet['BodyText'].fontSize = 12
        sample_style_sheet['BodyText'].leading = 14.4
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
