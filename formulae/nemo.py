import os.path

from flask import url_for, Markup, g, session, flash, request, Response, Blueprint, send_from_directory, abort
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
from formulae.search.Search import lem_highlight_to_text, POST_TAGS, PRE_TAGS
from formulae.auth.forms import AddSavedPageForm
from lxml import etree
from .errors.handlers import e_internal_error, e_not_found_error, e_unknown_collection_error
import re
from datetime import date
from urllib.parse import quote
from json import load as json_load, loads as json_loads, JSONDecodeError
from io import BytesIO
from reportlab.platypus import Paragraph, HRFlowable, Spacer, SimpleDocTemplate, Frame
from reportlab.lib.pdfencrypt import EncryptionFlowable
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from copy import copy
from typing import List, Tuple, Union, Match, Dict, Any, Sequence, Callable
from collections import defaultdict, OrderedDict
from random import randint
import roman


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
        ("/feedback", "r_feedback", ["GET"]),
        ("/pdf/<objectId>", "r_pdf", ["GET"]),
        ("/reading_format/<direction>", "r_reading_format", ["GET"]),
        ("/manuscript_desc/<manuscript>", "r_man_desc", ["GET"]),
        ("/manuscript_desc/siglen", "r_man_siglen", ["GET"]),
        ("/accessibility_statement", "r_accessibility_statement", ["GET"])
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
        "f_make_members",
        "f_random_int"
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

    OPEN_COLLECTIONS = ['anjou',
                        'chartae_latinae',
                        'fulda',
                        'rheinland',
                        'touraine',
                        'urn:cts:formulae:andecavensis',
                        'urn:cts:formulae:anjou_archives',
                        'urn:cts:formulae:anjou_comtes_chroniques',
                        'urn:cts:formulae:auvergne',
                        'urn:cts:formulae:bonneval_marmoutier',
                        'urn:cts:formulae:buenden',
                        'urn:cts:formulae:cartier_1841',
                        'urn:cts:formulae:chartae_latinae_xi',
                        'urn:cts:formulae:chartae_latinae_xii',
                        'urn:cts:formulae:chartae_latinae_xlvi',
                        'urn:cts:formulae:elexicon',
                        'urn:cts:formulae:echternach',
                        'urn:cts:formulae:eudes',
                        'urn:cts:formulae:freising',
                        'urn:cts:formulae:fu2',
                        'urn:cts:formulae:fulda_dronke',
                        'urn:cts:formulae:fulda_stengel',
                        'urn:cts:formulae:gorze',
                        'urn:cts:formulae:hersfeld',
                        'urn:cts:formulae:ka1',
                        'urn:cts:formulae:ko2',
                        # 'urn:cts:formulae:langobardisch', # needs correction
                        'urn:cts:formulae:le1',
                        'urn:cts:formulae:le3',
                        'urn:cts:formulae:lorsch',
                        'urn:cts:formulae:ludwig_2',
                        'urn:cts:formulae:luzern',
                        'urn:cts:formulae:m4',
                        'urn:cts:formulae:marculf',
                        'urn:cts:formulae:marmoutier_blésois',
                        'urn:cts:formulae:marmoutier_dunois',
                        'urn:cts:formulae:marmoutier_laurain',
                        'urn:cts:formulae:marmoutier_leveque',
                        'urn:cts:formulae:marmoutier_manceau',
                        'urn:cts:formulae:marmoutier_pour_le_perche',
                        'urn:cts:formulae:marmoutier_serfs',
                        'urn:cts:formulae:marmoutier_vendomois',
                        'urn:cts:formulae:marmoutier_vendomois_appendix',
                        'urn:cts:formulae:mittelrheinisch',
                        'urn:cts:formulae:mondsee',
                        'urn:cts:formulae:p3',
                        'urn:cts:formulae:p8',
                        'urn:cts:formulae:p10',
                        'urn:cts:formulae:p12',
                        'urn:cts:formulae:p14',
                        'urn:cts:formulae:p16a',
                        'urn:cts:formulae:p16b',
                        'urn:cts:formulae:pancarte_noir_internal',
                        'urn:cts:formulae:papsturkunden_frankreich',
                        'urn:cts:formulae:passau',
                        'urn:cts:formulae:pippin_3',
                        'urn:cts:formulae:redon',
                        'urn:cts:formulae:regensburg',
                        'urn:cts:formulae:rheinisch',
                        'urn:cts:formulae:s2',
                        'urn:cts:formulae:saint_bénigne',
                        'urn:cts:formulae:salzburg',
                        'urn:cts:formulae:schaeftlarn',
                        'urn:cts:formulae:sg2',
                        'urn:cts:formulae:stgallen',
                        'urn:cts:formulae:syd',
                        'urn:cts:formulae:tours',
                        'urn:cts:formulae:tours_gasnault',
                        'tours_st_julien_denis',
                        'urn:cts:formulae:tours_st_julien_fragments',
                        'urn:cts:formulae:v6',
                        'urn:cts:formulae:v8',
                        'urn:cts:formulae:v9',
                        'urn:cts:formulae:wa1',
                        'urn:cts:formulae:weissenburg',
                        'urn:cts:formulae:werden',
                        'urn:cts:formulae:zuerich']

    # Half-open collections are those that are newer than death-of-editor plus 70 years.
    # We do not show the regesten for these collections since those are still protected under copyright.
    HALF_OPEN_COLLECTIONS = ['urn:cts:formulae:buenden',
                             'urn:cts:formulae:chartae_latinae_xi',
                             'urn:cts:formulae:chartae_latinae_xii',
                             'urn:cts:formulae:chartae_latinae_xlvi',
                             'urn:cts:formulae:echternach',
                             'urn:cts:formulae:fulda_stengel',
                             # 'urn:cts:formulae:langobardisch', # needs correction
                             'urn:cts:formulae:lorsch',
                             'urn:cts:formulae:ludwig_2',
                             'urn:cts:formulae:mondsee',
                             'urn:cts:formulae:papsturkunden_frankreich',
                             'urn:cts:formulae:regensburg',
                             'urn:cts:formulae:rheinisch',
                             'urn:cts:formulae:saint_bénigne',
                             'urn:cts:formulae:salzburg',
                             'urn:cts:formulae:tours_gasnault',
                             'urn:cts:formulae:weissenburg',
                             'urn:cts:formulae:werden']

    FOUR_LEVEL_COLLECTIONS = ["urn:cts:formulae:katalonien",
                              "urn:cts:formulae:marmoutier_manceau",
                              "urn:cts:formulae:marmoutier_vendomois_appendix",
                              "urn:cts:formulae:marmoutier_dunois",
                              "urn:cts:formulae:anjou_archives",
                              "display_flavigny_formulae"]

    LANGUAGE_MAPPING = {"lat": _l('Latein'), "deu": _l("Deutsch"), "fre": _l("Französisch"),
                        "eng": _l("Englisch"), "cat": _l("Katalanisch"), "ita": _l("Italienisch")}

    BIBO = Namespace('http://bibliotek-o.org/1.0/ontology/')

    SALZBURG_MAPPING = {'a': 'Codex Odalberti', 'b': 'Codex Fridarici', 'c': 'Codex Hartuuici', 'd': 'Codex Tietmari II',
                        'e': 'Codex Balduuini', 'bn': 'Breves Notitiae', 'na': 'Notitia Arnonis',
                        'bna': 'Breves Notitiae Anhang'}

    ROMAN_NUMERAL_SORTING = {'I': 'a01',
                             'II': 'a02',
                             'III': 'a03',
                             'IV': 'a04',
                             'V': 'a05',
                             'VI': 'a06',
                             'VII': 'a07',
                             'VIII': 'a08',
                             'IX': 'a09',
                             'X': 'a10'}

    def __init__(self, *args, **kwargs):
        if "pdf_folder" in kwargs:
            self.pdf_folder = kwargs["pdf_folder"]
            del kwargs["pdf_folder"]
        super(NemoFormulae, self).__init__(*args, **kwargs)
        self.collected_colls = self.make_collected_colls()
        self.sub_colls = self.get_all_corpora()
        self.all_texts, self.open_texts, self.half_open_texts = self.get_open_texts()
        self.app.jinja_env.filters["remove_from_list"] = self.f_remove_from_list
        self.app.jinja_env.filters["join_list_values"] = self.f_join_list_values
        self.app.jinja_env.filters["replace_indexed_item"] = self.f_replace_indexed_item
        self.app.jinja_env.filters["insert_in_list"] = self.f_insert_in_list
        self.app.jinja_env.filters["random_int"] = self.f_random_int
        self.app.jinja_env.globals['get_locale'] = get_locale
        self.app.register_error_handler(404, e_not_found_error)
        self.app.register_error_handler(500, e_internal_error)
        self.app.before_request(self.before_request)
        self.app.after_request(self.after_request)
        self.register_font()
        self.inflected_to_lemma_mapping = self.make_inflected_to_lem_mapping()
        self.lem_to_lem_mapping = self.make_lem_to_lem_mapping()
        self.dead_urls = self.make_dead_url_mapping()
        self.comp_places = self.make_comp_places_list()
        self.manuscript_notes = self.make_manuscript_notes()
        self.ms_lib_links = self.make_ms_lib_links()
        self.closed_texts = self.make_closed_texts()
        # self.term_vectors = self.make_termvectors()
        self.restricted_four_level_collections = [x for x in self.FOUR_LEVEL_COLLECTIONS if x not in self.OPEN_COLLECTIONS]

    def make_closed_texts(self) -> dict:
        """ Ingests an existing JSON file that contains notes about specific manuscript transcriptions"""
        closed_texts = dict()
        for corpus_folder in self.app.config['CORPUS_FOLDERS']:
            if os.path.isfile(corpus_folder + '/' + 'closed_texts.json'):
                with open(corpus_folder + '/' + 'closed_texts.json') as f:
                    try:
                        closed = json_load(f)
                    except JSONDecodeError:
                        self.app.logger.warning(corpus_folder + '/' + 'closed_texts.json' + ' is not a valid JSON file. Unable to load valid closed texts from it.')
                        continue
                for k, v in closed.items():
                    closed_texts[k] = v
        return dict(closed_texts)

    def make_collected_colls(self) -> dict:
        """ Ingests an existing JSON file that contains notes about specific manuscript transcriptions"""
        collected_colls = defaultdict(list)
        for j in self.app.config['COLLECTED_COLLS']:
            with open(j) as f:
                try:
                    collected_coll = json_load(f)
                except JSONDecodeError:
                    self.app.logger.warning(j + ' is not a valid JSON file. Unable to load valid collected collections from it.')
                    continue
            for k, v in collected_coll.items():
                for parent_number, coll_urns in v.items():
                    for coll_urn in coll_urns:
                        for r_desc in self.resolver.getMetadata(coll_urn).readableDescendants.values():
                            manuscript_parts = re.search(r'(\D+)(\d+)', r_desc.id.split('.')[-1])
                            metadata = [r_desc.id, self.LANGUAGE_MAPPING[r_desc.lang], manuscript_parts.groups()]
                            collected_colls[k].append((parent_number, metadata, r_desc))
        return dict(collected_colls)

    def make_manuscript_notes(self) -> dict:
        """ Ingests an existing JSON file that contains notes about specific manuscript transcriptions"""
        manuscript_notes = dict()
        for corpus_folder in self.app.config['CORPUS_FOLDERS']:
            if os.path.isfile(corpus_folder + '/' + 'manuscript_notes.json'):
                with open(corpus_folder + '/' + 'manuscript_notes.json') as f:
                    try:
                        man_notes = json_load(f)
                    except JSONDecodeError:
                        self.app.logger.warning(corpus_folder + '/' + 'manuscript_notes.json' + ' is not a valid JSON file. Unable to load valid manuscript notes from it.')
                        continue
                for k, v in man_notes.items():
                    manuscript_notes[k] = v
        return dict(manuscript_notes)

    def make_ms_lib_links(self) -> dict:
        """ Ingests an existing JSON file that contains notes about specific manuscript transcriptions"""
        lib_links = dict()
        for corpus_folder in self.app.config['CORPUS_FOLDERS']:
            if os.path.isfile(corpus_folder + '/iiif/' + 'no_images.json'):
                with open(corpus_folder + '/iiif/' + 'no_images.json') as f:
                    try:
                        links = json_load(f)
                    except JSONDecodeError:
                        self.app.logger.warning(corpus_folder + '/iiif/' + 'no_images.json' + ' is not a valid JSON file. Unable to load valid library links from it.')
                        continue
                for k, v in links.items():
                    lib_links[k] = v
        return dict(lib_links)

    def make_inflected_to_lem_mapping(self) -> dict:
        """ Ingests an existing JSON file that maps inflected forms onto their lemmata"""
        lem_mapping = defaultdict(set)
        for j in self.app.config['INFLECTED_LEM_JSONS']:
            with open(j) as f:
                try:
                    inf_to_lem = json_load(f)
                except JSONDecodeError:
                    self.app.logger.warning(j + ' is not a valid JSON file. Unable to load valid inflected to lemma mapping from it.')
                    continue
            for k, v in inf_to_lem.items():
                lem_mapping[k].update(v)
        return dict(lem_mapping)

    def make_lem_to_lem_mapping(self) -> dict:
        """ Ingests an existing JSON file that maps theoretical lemmas onto the used lemmas, e.g., gero -> gerere"""
        lem_mapping = defaultdict(set)
        for j in self.app.config['LEM_TO_LEM_JSONS']:
            with open(j) as f:
                try:
                    lem_to_lem = json_load(f)
                except JSONDecodeError:
                    self.app.logger.warning(j + ' is not a valid JSON file. Unable to load valid lemma to lemma mapping from it.')
                    continue
            for k, v in lem_to_lem.items():
                lem_mapping[k].update(v)
        return dict(lem_mapping)

    def make_dead_url_mapping(self) -> dict:
        """ Ingests an existing JSON file that maps dead urls to active ones, e.g., urn:cts:formulae:lorsch.gloeckner4233 ->urn:cts:formulae:lorsch.gloeckner1134"""
        dead_url_mapping = dict()
        for j in self.app.config['DEAD_URLS']:
            with open(j) as f:
                try:
                    dead_urls = json_load(f)
                except JSONDecodeError:
                    self.app.logger.warning(j + ' is not a valid JSON file. Unable to load valid dead url mapping from it.')
                    continue
            for k, v in dead_urls.items():
                dead_url_mapping[k] = v
        return dict(dead_url_mapping)

    def make_comp_places_list(self) -> list:
        """ Ingests an existing JSON file that maps dead urls to active ones, e.g., urn:cts:formulae:lorsch.gloeckner4233 ->urn:cts:formulae:lorsch.gloeckner1134"""
        comp_places = list()
        for j in self.app.config['COMP_PLACES']:
            with open(j) as f:
                try:
                    comp_places += json_load(f)
                except JSONDecodeError:
                    self.app.logger.warning(j + ' is not a valid JSON file. Unable to load valid composition place list from it.')
                    continue
        return sorted(list(comp_places))

    # def make_termvectors(self) -> dict:
    #     """ Load the ES term vectors from a saved JSON file"""
    #     with open(self.app.config['TERM_VECTORS']) as f:
    #         try:
    #             return json_load(f)
    #         except JSONDecodeError:
    #             self.app.logger.warning(self.app.config['TERM_VECTORS'] + ' is not a valid JSON file. Unable to load valid term vector dictionary from it.')

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
                m.update({'coverage':
                              str(self.resolver.getMetadata(m['id']).metadata.get_single(DC.coverage))})
                m.update({'lemmatized':
                              str(self.resolver.getMetadata(m['id']).metadata.get_single(self.BIBO.Annotations)) == 'Lemmas'})
            if member['id'] not in ['other_collection', 'display_collection']:
                colls[member['id']] = sorted(members, key=lambda x: self.sort_transcriptions(self.resolver.id_to_coll[x['id']]))
            else:
                colls[member['id']] = sorted(members, key=lambda x: (x['coverage'].lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss'),
                                                                     x['label']))
        return colls

    @staticmethod
    def sort_folia(matchobj: Match) -> str:
        """Sets up the folia ranges of manuscripts for better sorting"""
        groups = []
        sub_groups = re.search(r'(\d+)([rvab]+)', matchobj.group(1)).groups()
        groups.append('{:04}<span class="verso-recto">{}</span>'.format(int(sub_groups[0]), sub_groups[1]))
        if matchobj.group(2):
            new_sub_groups = re.search(r'(\d+)([rvab]+)', matchobj.group(2)).groups()
            groups.append('{}<span class="verso-recto">{}</span>'.format(int(new_sub_groups[0]), new_sub_groups[1]))
        return_value = '-'.join(groups)
        if matchobj.group(3):
            return_value += '(' + matchobj.group(3) + ')'
        return return_value

    def ordered_corpora(self, m: XmlCapitainsReadableMetadata, collection: str)\
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
            par = parent_0.split('.')[-1].title()
            metadata = [m.id, parent_0.split('.')[-1], self.LANGUAGE_MAPPING[m.lang]]
        elif "marmoutier_serfs" in m.id:
            par = re.sub(r'.*?(\d+)(app)?\Z', r'\2\1', list(m.parent)[0])
            manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
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
                    par = re.sub(r'.*?(\d+[rvab]+)(\d+[rvab]+)?(\d)?\Z', self.sort_folia, list(m.parent)[0])
                manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            else:
                if collection in m.id:
                    par = re.sub(r'.*?(\d+[rvab]+)(\d+[rvab]+)?(\d)?\Z', self.sort_folia, list(m.parent)[0])
                    if "sg2" in m.id:
                        par_parts = re.search(r'.*\[p\.\s*(\d+)\-?(\d+)?.*', str(m.metadata.get_single(DC.title)))
                        par = '{:04}'.format(int(par_parts.group(1)))
                        if len(par_parts.groups()) > 1:
                            par += '-' + par_parts.group(2)
                    manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
                else:
                    form_num = [x for x in self.resolver.id_to_coll[list(m.parent)[0]].parent if collection in x][0]
                    par = re.sub(r'.*?(\d+\w*)\Z', r'\1', form_num)
                    if 'marculf' in form_num:
                        if 'capitula' in form_num:
                            par = par.replace('capitula', '000a')
                        if 'incipit' in form_num:
                            par = par.replace('incipit', '000b')
                    if 'urn:cts:formulae:tours' in form_num:
                        if 'capitula' in form_num:
                            par = '000_a'
                    if par.endswith('000'):
                        par = par.replace('000', _('(Prolog)'))
                    par = par.replace('capitula', '0')
                    manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        elif re.search(r'anjou_archives|katalonien|marmoutier_manceau', m.id):
            par = list(m.parent)[0].split('_')[-1]
            manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        else:
            par = re.sub(r'.*?(\d+\w*)\Z', r'\1', list(m.parent)[0])
            if 'marculf' in m.id:
                if 'capitula' in m.id:
                    par = par.replace('capitula', '000a')
                if 'incipit' in m.id:
                    par = par.replace('incipit', '000b')
            if 'urn:cts:formulae:tours' in m.id:
                if 'capitula' in m.id:
                    par = '000_a'
            if par.endswith('000'):
                if 'andecavensis' in m.id:
                    par = _('(Titel)')
                else:
                    par = par.replace('000', _('(Prolog)'))
            elif 'computus' in par:
                par = '057(Computus)'
            par = par.replace('capitula', '0')
            manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        return par, metadata, m

    def get_open_texts(self) -> Tuple[Dict[str, Tuple[Union[str, Tuple[str, Tuple[str, str]]],
                                                      Union[List[Sequence[str]], list],
                                                      XmlCapitainsReadableMetadata]],
                                      List[str],
                                      List[str]]:
        """ Creates the lists of open and half-open texts to be used later.

        :return: dictionary of all texts {collection: [readableDescendants]}, list of open texts, list of half-open texts
        """
        open_texts = []
        half_open_texts = []
        all_texts = {m['id']: sorted([self.ordered_corpora(r, m['id']) for r in self.resolver.getMetadata(m['id']).readableDescendants.values()])
                     for l in self.sub_colls.values() for m in l if m['id'] not in ['urn:cts:formulae:anjou_archives',
                                                                                    'urn:cts:formulae:katalonien',
                                                                                    'urn:cts:formulae:marmoutier_manceau',
                                                                                    'urn:cts:formulae:marmoutier_vendomois_appendix',
                                                                                    'urn:cts:formulae:marmoutier_dunois']
                     and 'urn:cts:formulae:' in m['id']}
        all_texts.update({m: sorted([self.ordered_corpora(r, m)
                                     for r in self.resolver.getMetadata(m).readableDescendants.values()],
                                    key=self.sort_katalonien)
                          for m in self.resolver.children['urn:cts:formulae:katalonien']})
        all_texts.update({m: sorted([self.ordered_corpora(r, m)
                                     for r in self.resolver.getMetadata(m).readableDescendants.values()])
                          for m in self.resolver.children['urn:cts:formulae:marmoutier_manceau']})
        all_texts.update({m: sorted([self.ordered_corpora(r, m)
                                     for r in self.resolver.getMetadata(m).readableDescendants.values()])
                          for m in self.resolver.children['urn:cts:formulae:marmoutier_vendomois_appendix']})
        all_texts.update({m: sorted([self.ordered_corpora(r, m)
                                     for r in self.resolver.getMetadata(m).readableDescendants.values()])
                          for m in self.resolver.children['urn:cts:formulae:marmoutier_dunois']})
        all_texts.update({m: sorted([self.ordered_corpora(r, m)
                                     for r in self.resolver.getMetadata(m).readableDescendants.values()])
                          for m in self.resolver.children['urn:cts:formulae:anjou_archives']})
        all_texts.update({k: sorted(v) for k, v in self.collected_colls.items()})
        for c in all_texts.keys():
            parents = [p.id for p in self.resolver.getMetadata(c).ancestors.values() if 'urn:cts:formulae:' in p.id]
            if set(self.OPEN_COLLECTIONS).intersection(parents + [c]):
                open_texts += [x[1][0] for x in all_texts[c]]
            if set(self.HALF_OPEN_COLLECTIONS).intersection(parents + [c]):
                half_open_texts += [x[1][0] for x in all_texts[c]]
        return all_texts, open_texts, half_open_texts

    def sort_katalonien(self, t: tuple):
        """ Correctly sort the Katalonien documents with mixed number and Roman numerals"""
        return re.sub(r'[IVX]+\Z', lambda x: self.ROMAN_NUMERAL_SORTING[x.group(0)], t[0])

    @staticmethod
    def check_project_team() -> bool:
        """ A convenience function that checks if the current user is a part of the project team"""
        try:
            return current_user.project_team is True
        except AttributeError:
            return False

    def create_blueprint(self) -> Blueprint:
        """ Enhance original blueprint creation with error handling

        :return: flask.Blueprint
        """
        blueprint = super(NemoFormulae, self).create_blueprint()
        blueprint.register_error_handler(UnknownCollection, e_unknown_collection_error)
        return blueprint

    def get_locale(self) -> str:
        """ Retrieve the best matching locale using request headers

        .. note:: Probably one of the thing to enhance quickly.

        :return: the 3-letter language code
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
        """ A Jinja filter to remove item "i" from list "l"

        :param l: the list
        :param i: the item
        :return: the list without the item
        """
        l.remove(i)
        return l

    @staticmethod
    def f_join_list_values(l: list, s: str) -> str:
        """ A Jinja filter to join the values of a list "l" into a string using the separator "s"

        :param l: the list of values
        :param s: the separator
        :return: a string of the values joined by the separator
        """
        new_list = [str(x) for x in l]
        return s.join(new_list).strip(s)

    @staticmethod
    def f_replace_indexed_item(l: list, i: int, v: Any) -> list:
        """ A Jinja filter to replace an item at 'i' with the value of 'v'

        :param l: the list of values
        :param i: the index to be replace
        :param v: the value with which the indexed value will be replaced
        :return: new list
        """
        l[i] = v
        return l

    @staticmethod
    def f_insert_in_list(l: list, i: int, v: Any) -> list:
        """ A Jinja filter to insert a value 'v' into an existing list 'l' at a given index 'i'

        :param l: the list of values
        :param i: the index at which the item should be inserted
        :param v: the value that will be inserted
        :return: new list
        """
        l.insert(i, v)
        return l

    @staticmethod
    def f_random_int(start: int = 1, end: int = 10000) -> int:
        """ A Jinja filter to produce a random integer between 1 and 10,000"""
        return randint(start, end)

    @staticmethod
    def r_set_language(code: str) -> Union[str, redirect]:
        """ Sets the session's language code which will be used for all requests

        :param code: The 2-letter language code
        """
        session['locale'] = code
        refresh()
        if request.headers.get('X-Requested-With') == "XMLHttpRequest":
            return 'OK'
        else:
            flash('Language Changed. You may need to refresh the page in your browser.')
            if request.referrer:
                return redirect(request.referrer)
            return redirect(url_for('InstanceNemo.r_index'))

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
            flash(_('Die Leserichtung wurde geändert. Wenn die Änderung noch nicht gezeigt wird, dann laden Sie die Seite neu.'))
            if request.referrer:
                return redirect(request.referrer)
            return redirect(url_for('InstanceNemo.r_index'))

    def before_request(self):
        g.search_form = SearchForm()
        g.save_page_form = AddSavedPageForm()
        g.sub_colls = self.sub_colls
        g.open_texts = self.open_texts
        g.open_collections = self.OPEN_COLLECTIONS
        if not re.search('texts|search|assets|favicon|reading_format|save_page', request.url):
            session.pop('previous_search', None)

    def after_request(self, response: Response) -> Response:
        """ Currently used only for the Cache-Control header.

        """
        max_age = self.app.config['CACHE_MAX_AGE']
        if re.search('/(lang|auth|texts)/', request.url):
            response.cache_control.no_cache = True
        elif re.search('/assets/', request.url):
            max_age = 60 * 60 * 24
        else:
            response.vary = 'session'
        response.cache_control.max_age = max_age
        response.cache_control.public = True
        if getattr(g, 'previous_search', None) is not None:
            session['previous_search'] = g.previous_search
        if getattr(g, 'previous_search_args', None):
            session['previous_search_args'] = g.previous_search_args
        if getattr(g, 'previous_aggregations', None):
            session['previous_aggregations'] = g.previous_aggregations
        if getattr(g, 'highlighted_words', None):
            session['highlighted_words'] = g.highlighted_words
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
                 parent: XmlCapitainsCollectionMetadata = None) -> str:
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
                   text: XmlCapitainsReadableMetadata, subreference: str = "", lang: str = None) -> str:
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
        """ Sort parents from closest to furthest

        :param d: The dictionary to be sorted
        :return: integer representing how deep in the collection a collection stands from lowest (i.e., text) to highest
        """
        return 10 - len(d['ancestors'])

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
                "label": str(member.metadata.get_single(DC.title)),
                "model": str(member.model),
                "type": str(member.type),
                "size": member.size,
                "subtype": member.subtype,
                "ancestors": member.ancestors,
                "short_title": str(member.metadata.get_single(self.BIBO.AbbreviatedTitle))
            }
            for member in collection.ancestors.values()
            if member.get_label()
        ]
        parents = sorted(parents, key=self.sort_parents)
        return parents

    def r_assets(self, filetype, asset):
        """ Route for specific assets.

        :param filetype: Asset Type
        :param asset: Filename of an asset
        :return: Response
        """
        if filetype in self.assets and asset in self.assets[filetype] and self.assets[filetype][asset]:
            return send_from_directory(
                directory=self.assets[filetype][asset],
                path=asset
            )
        abort(404)

    def r_collection(self, objectId: str, lang: str = None) -> Dict[str, Any]:
        """ Route to show a collection of different corpora, e.g., all formulae collections

        :param objectId: The id of the collection to be shown
        :param lang: Language in which to show the collection's metadata
        :return: Template and collections contained in a given collection
        """
        data = super(NemoFormulae, self).r_collection(objectId, lang=lang)
        from_four_level_collection = re.search(r'katalonien|marmoutier_manceau|marmoutier_vendomois_appendix|marmoutier_dunois|anjou_archives|display_flavigny_formulae', objectId)
        direct_parents = [x for x in self.resolver.getMetadata(objectId).parent]
        if self.check_project_team() is False:
            if not from_four_level_collection:
                data['collections']['members'] = [x for x in data['collections']['members'] if x['id'] in self.OPEN_COLLECTIONS]
            elif set(self.restricted_four_level_collections).intersection([p['id'] for p in data['collections']['parents']] + [objectId]):
                data['collections']['members'] = []
                flash(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
        if not from_four_level_collection and 'defaultTic' not in direct_parents and direct_parents != ['display_collection']:
            return redirect(url_for('InstanceNemo.r_corpus', objectId=objectId, lang=lang))
        if len(data['collections']['members']) == 1:
            return redirect(url_for('InstanceNemo.r_corpus', objectId=data['collections']['members'][0]['id'], lang=lang))
        for m in data['collections']['members']:
            m['lemmatized'] = str(self.resolver.getMetadata(m['id']).metadata.get_single(self.BIBO.Annotations)) == 'Lemmas'
        data['template'] = "main::sub_collections.html"
        if 'chartae_latinae' in objectId:
            data['collections']['members'] = sorted(data['collections']['members'], key=lambda x: roman.fromRoman(str(self.resolver.getMetadata(x['id']).metadata.get_single(self.BIBO.AbbreviatedTitle)).split()[-1]))
        else:
            data['collections']['members'] = sorted(data['collections']['members'], key=lambda x: x['label'])
        return data

    def r_corpus(self, objectId: str, lang: str = None) -> Dict[str, Any]:
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :param lang: Lang in which to express main data
        :return: Template and collections contained in given collection
        """
        collection = self.resolver.getMetadata(objectId)
        r = OrderedDict()
        template = "main::sub_collection.html"
        current_parents = self.make_parents(collection, lang=lang)
        form = None
        if 'elexicon' in objectId:
            template = "main::elex_collection.html"
        elif 'salzburg' in objectId:
            template = "main::salzburg_collection.html"
        elif objectId in self.FOUR_LEVEL_COLLECTIONS:
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
                    r[par] = {"versions": {'editions': [], 'translations': [], 'transcriptions': []},
                              "short_regest": '',
                              "regest": [],
                              "dating": '',
                              "ausstellungsort": '',
                              'name': '',
                              'title': '',
                              'transcribed_edition': [],
                              'parent_id': str(m.id)}
                    r[par]["versions"][key].append(metadata + [manuscript_data])
                if key == 'editions' or 'manuscript_collection' in collection.ancestors:
                    work_name = Markup(par.lstrip('0') if isinstance(par, str) else '')
                    parents = self.make_parents(m)
                    parent_title = parents[0]['label']
                    if 'manuscript_collection' in collection.ancestors:
                        parent_title = [x['label'] for x in parents if 'manuscript_collection' in self.resolver.getMetadata(x['id']).ancestors][0]
                    elif 'formulae_collection' in collection.ancestors:
                        parent_title = [x['label'] for x in parents if 'manuscript_collection' not in self.resolver.getMetadata(x['id']).ancestors][0]
                    if 'non_display_collection' in collection.ancestors:
                        if r[par]['name']:
                            work_name = [r[par]['name'], Markup(re.sub(r' \(lat\)', '', str(m.metadata.get_single(DC.title))))]
                        else:
                            work_name = Markup(re.sub(r' \(lat\)', '', str(m.metadata.get_single(DC.title))))
                    elif 'urn:cts:formulae:marculf' in m.ancestors and key == 'editions':
                        work_name = Markup(str(parent_title).replace('Marculf ', ''))
                    elif 'Computus' in work_name:
                        work_name = '(Computus)'
                    elif 'Titel' in work_name:
                        work_name = _('(Titel)')
                    elif 'urn:cts:formulae:lorsch' in m.ancestors:
                        name_part = re.search(r'(Kap\.|Nr\.).*', str(m.metadata.get_single(DC.title)))
                        if name_part:
                            work_name = Markup(name_part.group(0))
                    regest = [Markup(m.metadata.get_single(DC.description))] if 'formulae_collection' in collection.ancestors else [Markup(x) for x in str(m.metadata.get_single(DC.description)).split('***')]
                    if self.check_project_team() is False and (m.id in self.closed_texts['half_closed'] or m.id in self.closed_texts['closed']):
                        if len(regest) == 2:
                            regest[1] = re.sub(r'^(\w+?:).*', r'\1 ' + _('Dieses Regest ist nicht öffentlich zugänglich'), regest[1])

                    r[par].update({"short_regest": str(m.metadata.get_single(DCTERMS.abstract)) or '',
                                   "regest": regest,
                                   "dating": str(m.metadata.get_single(DCTERMS.temporal)),
                                   "ausstellungsort": str(m.metadata.get_single(DCTERMS.spatial)),
                                   'name': work_name,
                                   'title': Markup(str(self.make_parents(m)[0]['label'])),
                                   'translated_title': str(m.metadata.get_single(DCTERMS.alternative) or ''),
                                   'transcribed_edition': sorted([str(x) if x else '' for x in m.metadata.get(DCTERMS.isVersionOf)])})
        for k in r.keys():
            r[k]['versions']['transcriptions'] = sorted(sorted(r[k]['versions']['transcriptions'],
                                                               key=lambda x: int(x[2][1])),
                                                        key=lambda x: x[2][0])

        if len(r) == 0:
            if 'manuscript_collection' in collection.ancestors:
                flash(_('Um das Digitalisat dieser Handschrift zu sehen, besuchen Sie bitte gegebenenfalls die Homepage der Bibliothek.'))
            else:
                flash(_('Diese Sammlung ist nicht öffentlich zugänglich.'))

        return_value = {
            "template": template,
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                    "open_regesten": collection.id not in self.HALF_OPEN_COLLECTIONS,
                    "short_title": collection.metadata.get_single(self.BIBO.AbbreviatedTitle) or ''
                },
                "readable": r,
                "parents": current_parents,
                "parent_ids": [x['id'] for x in current_parents],
                "first_letters": set([x[0] for x in r.keys()])
            },
            "form": form,
            'manuscript_notes': self.manuscript_notes
        }
        return return_value

    def r_corpus_mv(self, objectId: str, lang: str = None) -> Dict[str, Any]:
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :param lang: Lang in which to express main data
        :return: Template and collections contained in given collection
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
        parents = {}
        template = "main::sub_collection_mv.html"
        list_of_readable_descendants = self.all_texts[collection.id]

        if 'formulae_collection' in collection.ancestors:
            for par, metadata, m in list_of_readable_descendants:
                if self.check_project_team() is True or m.id in self.open_texts:
                    edition = str(m.id).split(".")[-1]
                    if objectId not in m.id:
                        edition = str(m.id).split(':')[-1].split('.')[0]
                    ed_parent = sorted([(k, v) for k, v in m.ancestors.items() if objectId in k])[-1][-1]
                    title = str(ed_parent.metadata.get_single(DC.title, lang=lang))
                    form = ed_parent.id
                    edition_name = ed_trans_mapping.get(edition, edition).title()
                    regest = str(m.metadata.get_single(DCTERMS.abstract))
                    if 'manuscript_collection' in m.ancestors:
                        full_edition = sorted([(k, v) for k, v in m.ancestors.items() if 'manuscript_collection' in v.ancestors])[0][-1]
                        edition_name = str(full_edition.metadata.get_single(self.BIBO.AbbreviatedTitle, lang=lang))
                        for k, v in ed_parent.readableDescendants.items():
                            if 'deu001' in k:
                                regest = str(v.metadata.get_single(DCTERMS.abstract))
                    else:
                        full_edition = sorted([(k, v) for k, v in m.ancestors.items() if 'formulae_collection' in v.ancestors])[0][-1]
                    full_edition_name = str(full_edition.metadata.get_single(DC.title, lang=lang))

                    if edition not in translations.keys():
                        titles[edition] = [title]
                        translations[edition] = [m.id]
                        forms[edition] = [form]
                        edition_names[edition] = edition_name
                        full_edition_names[edition] = full_edition_name
                        regesten[edition] = [regest]
                        if "sg2" in m.id:
                            par_parts = re.search(r'.*\[p\.\s*(\d+)\-?(\d+)?.*', str(m.metadata.get_single(DC.title)))
                            ms_par = '{:04}'.format(int(par_parts.group(1)))
                            if len(par_parts.groups()) > 1:
                                ms_par += '-' + par_parts.group(2)
                            parents[edition] = [ms_par]
                        else:
                            parents[edition] = [re.sub(r'.*?(\d+[rvab]+)(\d+[rvab]+)?(\d)?\Z', self.sort_folia, list(m.parent)[0])]
                    else:
                        titles[edition].append(title)
                        translations[edition].append(m.id)
                        forms[edition].append(form)
                        regesten[edition].append(regest)
                        if "sg2" in m.id:
                            par_parts = re.search(r'.*\[p\.\s*(\d+)\-?(\d+)?.*', str(m.metadata.get_single(DC.title)))
                            ms_par = '{:04}'.format(int(par_parts.group(1)))
                            if len(par_parts.groups()) > 1:
                                ms_par += '-' + par_parts.group(2)
                            parents[edition].append(ms_par)
                        else:
                            parents[edition].append(re.sub(r'.*?(\d+[rvab]+)(\d+[rvab]+)?(\d)?\Z', self.sort_folia, list(m.parent)[0]))
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
                    # Zip titles, forms and regesten together and then sort them with
                    # re.sub(r'.*?(\d+[rvab]+)(\d+[rvab]+)?(\d)?\Z', self.sort_folia, list(m.parent)[0])
                    # I might need to add the m.parent[0] information to the lists so that I can sort by the folia.
                    new_titles = list()
                    new_forms = list()
                    new_regesten = list()
                    new_v = list()
                    new_parents = list()
                    for t_parent, t_title, t_form, t_regest, t_v in sorted(zip(parents[k], titles[k], forms[k], regesten[k], v)):
                        new_titles.append(t_title)
                        new_forms.append(t_form)
                        new_regesten.append(t_regest)
                        new_v.append(t_v)
                        if "sg2" in t_v:
                            new_parents.append('[p.' + t_parent.lstrip('0') + ']')
                        else:
                            new_parents.append('[fol.' + t_parent.lstrip('0').replace('</span>-', '</span>-fol.') + ']')
                    r['transcriptions'].append({
                        "name": k,
                        "edition_name": edition_names[k],
                        "full_edition_name": full_edition_names[k],
                        "titles": new_titles,
                        "links": [new_forms, new_v],
                        "ms_images": [True if "manifest:" + x in self.app.picture_file else False for x in new_v],
                        "regesten": new_regesten,
                        "folia": new_parents
                    })

            r['transcriptions'] = sorted(sorted(r['transcriptions'], key=lambda x: int(re.search(r'\d+', x['name']).group(0)) if re.search(r'\d+', x['name']) else 0),
                                         key=lambda x: re.search(r'\D+', x['name']).group(0))

        else:

            r = {'editions': [], 'translations': [], 'transcriptions': []}
            flash(_('Diese View ist nur für Formelsammlungen verfuegbar'))

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
            },
            'manuscript_notes': self.manuscript_notes
        }
        return return_value

    def r_add_text_collections(self, objectIds: str, reffs: str, lang: str = None) -> Dict[str, Any]:
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

    def r_add_text_collection(self, objectId: str, objectIds: str, reffs: str, lang: str = None) -> Dict[str, Any]:
        """ Route to browse a top-level collection and add another text to the view

        :param objectId: the id of the collection from which the new text for the reading view should be added
        :param objectIds: the object ids from the previous view separated by '+'
        :param reffs: the citation references from the objects in the previous view seperated by '+'
        :param lang: Lang in which to express main data
        :return: Template and collections contained in given collection
        """
        collection = self.resolver.getMetadata(objectId)
        if 'defaultTic' not in collection.parent and objectId not in self.FOUR_LEVEL_COLLECTIONS:
            return redirect(url_for('InstanceNemo.r_add_text_corpus', objectId=objectId,
                                    objectIds=objectIds, reffs=reffs, lang=lang))
        members = self.make_members(collection, lang=lang)
        for m in members:
            m['lemmatized'] = str(self.resolver.getMetadata(m['id']).metadata.get_single(self.BIBO.Annotations)) == 'Lemmas'
        from_four_level_collection = re.search(r'katalonien|marmoutier_manceau|marmoutier_vendomois_appendix|marmoutier_dunois|anjou_archives', objectId)
        if self.check_project_team() is False:
            if not from_four_level_collection:
                members = [x for x in members if x['id'] in self.OPEN_COLLECTIONS]
            elif set(self.restricted_four_level_collections).intersection([p['id'] for p in members] + [objectId]):
                members = []
                flash(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
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

    def r_add_text_corpus(self, objectId: str, objectIds: str, reffs: str, lang: str = None) -> Dict[str, Any]:
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :param objectIds: the ids of the documents in the previous view separated by '+'
        :param reffs: the references for the documents in the previous view separated by '+'
        :param lang: Lang in which to express main data
        :return: Template and collections contained in given collection
        """
        if objectId in self.FOUR_LEVEL_COLLECTIONS:
            return redirect(url_for('InstanceNemo.r_add_text_collection', objectId=objectId, objectIds=objectIds,
                                    reffs=reffs, lang=lang))
        initial = self.r_corpus(objectId, lang=lang)
        initial.update({'prev_texts': objectIds, 'prev_reffs': reffs})
        return initial

    def get_first_passage(self, objectId: str) -> str:
        """ Provides a redirect to the first passage of given objectId

        :param objectId: Collection identifier
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
        text = self.resolver.getMetadata(objectId)
        grandparents = set()
        for x in text.parent:
            grandparents.update(self.resolver.getMetadata(x).parent)
        if text.subtype & {'cts:translation', 'cts:edition'}:
            language = re.search(r'(\w\w\w)\d\d\d\Z', objectId).group(1)
            sibling_texts = [x[1][0] for gp in grandparents
                             for x in self.all_texts[gp]
                             if x[2].subtype & text.subtype and re.search(r'{}\d\d\d\Z'.format(language), x[1][0])]
        else:
            sibling_texts = []
            for gp in grandparents:
                if gp in self.all_texts:
                    sibling_texts += [x[1][0] for x in self.all_texts[gp] if x[1][0].split('.')[-1] == id_parts[-1]]
        orig_index = sibling_texts.index(objectId)
        return sibling_texts[orig_index - 1] if orig_index > 0 else None, \
               sibling_texts[orig_index + 1] if orig_index + 1 < len(sibling_texts) else None

    @staticmethod
    def get_readable_siblings(obj: XmlCapitainsReadableMetadata) -> List[XmlCapitainsReadableMetadata]:
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

    @staticmethod
    def sort_transcriptions(obj: Union[XmlCapitainsReadableMetadata,
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

    def r_passage(self, objectId: str, subreference: str, lang: str = None) -> Dict[str, Any]:
        """ Retrieve the text of the passage

        :param objectId: Collection identifier
        :param lang: Lang in which to express main data
        :param subreference: Reference identifier
        :return: Template, collections metadata and Markup object representing the text
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
        if objectId in self.closed_texts['closed'] and self.check_project_team() is False:
            passage = '<div class="text lang_lat edition" data-lang="lat" lang="la"><div class="charta"><p>{}</p></div></div>'.format(_('Dieser Text ist nicht öffentlich zugänglich.'))
        secondary_language = 'de'
        all_langs = [str(x) for x in metadata.metadata.get(DC.language, lang=None)]
        if len(all_langs) > 0:
            for l in all_langs:
                if l != 'lat':
                    secondary_language = l[:2]
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
        translations = [(m, m.metadata.get_single(DC.title), m.metadata.get_single(DCTERMS.isPartOf) or '')
                        for m in self.get_readable_siblings(metadata)] + \
                       [(self.resolver.getMetadata(str(x)),
                         self.resolver.getMetadata(str(x)).metadata.get_single(DC.title),
                         self.resolver.getMetadata(str(x)).metadata.get_single(DCTERMS.isPartOf) or '')
                        for x in metadata.metadata.get(DCTERMS.hasVersion)]
        transcriptions = []
        for m in self.get_transcriptions(metadata):
            siglum = [x['short_title'] for x in self.make_parents(m) if 'manuscript_collection' in x['ancestors']]
            transcriptions.append((m, m.metadata.get_single(DC.title), m.metadata.get_single(DCTERMS.isPartOf) or '', siglum[-1]))
        current_parents = self.make_parents(metadata, lang=lang)
        linked_resources = []
        for resource in metadata.metadata.get(DCTERMS.relation):
            linked_md = self.resolver.getMetadata(str(resource))
            linked_resources.append((linked_md.id, str(linked_md.metadata.get_single(DC.title, lang=None)) or metadata.get_label(lang)))
        regest = [Markup(metadata.metadata.get_single(DC.description))] if 'formulae_collection' in metadata.ancestors else [Markup(x) for x in str(metadata.metadata.get_single(DC.description)).split('***')]
        if self.check_project_team() is False and (metadata.id in self.closed_texts['half_closed'] or metadata.id in self.closed_texts['closed']):
            if len(regest) == 2:
                regest[1] = re.sub(r'^(\w+?:).*', r'\1 ' + _('Dieses Regest ist nicht öffentlich zugänglich'), regest[1])
        return {
            "template": "",
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
                    "description": regest,
                    "coins": self.make_coins(metadata, text, subreference, lang=lang),
                    "pubdate": str(metadata.metadata.get_single(DCTERMS.created, lang=lang)),
                    "publang": str(metadata.metadata.get_single(DC.language, lang=lang)),
                    "publisher": str(metadata.metadata.get_single(DC.publisher, lang=lang)),
                    'lang': metadata.lang,
                    'secondary_lang': secondary_language,
                    'citation': str(metadata.metadata.get_single(DCTERMS.bibliographicCitation, lang=lang)),
                    "short_regest": str(metadata.metadata.get_single(DCTERMS.abstract)) if 'formulae_collection' in [x['id'] for x in current_parents] else '',
                    "dating": str(metadata.metadata.get_single(DCTERMS.temporal) or ''),
                    "issued_at": str(metadata.metadata.get_single(DCTERMS.spatial) or ''),
                    "sigla": str(metadata.metadata.get_single(DCTERMS.isPartOf) or ''),
                    "ms_source": str(metadata.metadata.get_single(DCTERMS.source) or ''),
                    "linked_resources": linked_resources,
                    "transcribed_edition": sorted([str(x) if x else '' for x in metadata.metadata.get(DCTERMS.isVersionOf)] if metadata.metadata.get(DCTERMS.isVersionOf) else []),
                    "mss_eds": str(metadata.metadata.get_single(DCTERMS.references)).split('**') if metadata.metadata.get_single(DCTERMS.references) else []
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
            "transcriptions": transcriptions
        }

    def r_multipassage(self, objectIds: str, subreferences: str, lang: str = None) -> Dict[str, Any]:
        """ Retrieve the text of the passage

        :param objectIds: Collection identifiers separated by '+'
        :param lang: Lang in which to express main data
        :param subreferences: Reference identifiers separated by '+'
        :return: Template, collections metadata and Markup object representing the text
        """
        if 'reading_format' not in session:
            session['reading_format'] = 'columns'
        ids = objectIds.split('+')
        translations = {}
        view = 1
        passage_data = {'template': 'main::multipassage.html', 'objects': [], "translation": {}}
        subrefers = subreferences.split('+')
        if len(subrefers) != len(ids):
            abort(404)
        for i, id in enumerate(ids):
            v = False
            if id in self.dead_urls:
                id = self.dead_urls[id]
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
                translations[id] = []
                for x in d.pop('translations', None):
                    if x[0].id not in ids and x not in translations[id]:
                        translations[id].append(x)
                if v:
                    # This is when there are multiple manuscripts and the edition cannot be tied to any single one of them
                    formulae = dict()
                    if 'manifest:' + d['collections']['current']['id'] in self.app.picture_file:
                        formulae = self.app.picture_file['manifest:' + d['collections']['current']['id']]
                    d['alt_image'] = ''
                    if os.path.isfile(self.app.config['IIIF_MAPPING'] + '/' + 'alternatives.json'):
                        with open(self.app.config['IIIF_MAPPING'] + '/' + 'alternatives.json') as f:
                            alt_images = json_load(f)
                        d['alt_image'] = alt_images.get(id)
                    d["objectId"] = "manifest:" + id
                    d["div_v"] = "manifest" + str(view)
                    view = view + 1
                    del d['text_passage']
                    del d['notes']
                    if formulae == {}:
                        d['manifest'] = None
                        d["label"] = [d['collections']['current']['label'], '']
                        d['lib_link'] = self.ms_lib_links.get(id.split(':')[-1].split('.')[0], '')
                        passage_data['objects'].append(d)
                        continue
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
                    elif 'digitalcollections.universiteitleiden.nl' in this_manifest['@id']:
                        # This works for resources from the Leiden University Library
                        # This links to the manuscript as a whole.
                        # I am not sure how to link to specific pages in their IIIF viewer.
                        d['lib_link'] = 'https://iiifviewer.universiteitleiden.nl/?manifest=' + this_manifest['@id']
                    elif 'digi.vatlib.it' in this_manifest['@id']:
                        # This works for resources from the Vatican Libraries
                        d['lib_link'] = this_manifest['sequences'][0]['canvases'][0]['@id'].replace('iiif', 'view').replace('canvas/p', '')
                    folios = re.sub(r'(\d+)([rvab]{1,2})', r'\1<span class="verso-recto">\2</span>',
                                    this_manifest['sequences'][0]['canvases'][0]['label'])
                    if len(this_manifest['sequences'][0]['canvases']) > 1:
                        folios += ' - ' + re.sub(r'(\d+)([rvab]{1,2})', r'\1<span class="verso-recto">\2</span>',
                                                 this_manifest['sequences'][0]['canvases'][-1]['label'])
                    d["label"] = [formulae["title"], ' [fol.' + folios + ']']

                else:
                    d["IIIFviewer"] = []
                    for transcription, t_title, t_partOf, t_siglum in d['transcriptions']:
                        t_id = 'no_image'
                        if "manifest:" + transcription.id in self.app.picture_file:
                            t_id = "manifest:" + transcription.id
                        elif 'wa1' in transcription.id:
                            t_id = self.ms_lib_links['wa1']
                        d["IIIFviewer"].append((t_id,
                                                t_title + ' (' + t_siglum + ')',
                                                t_partOf))

                    if 'previous_search' in session:
                        result_ids = [x for x in session['previous_search'] if x['id'] == id]
                        if result_ids and any([x.get('highlight') for x in result_ids]):
                            d['text_passage'] = self.highlight_found_sents(d['text_passage'], result_ids)
                    if d['collections']['current']['sigla'] != '':
                        d['collections']['current']['label'] = d['collections']['current']['label'].split(' [')
                        d['collections']['current']['label'][-1] = ' [' + d['collections']['current']['label'][-1]
                filtered_transcriptions = []
                for x in d['transcriptions']:
                    if x[0].id not in ids and x not in filtered_transcriptions:
                        filtered_transcriptions.append(x)
                d['transcriptions'] = filtered_transcriptions
                passage_data['objects'].append(d)
        if len(ids) > len(passage_data['objects']):
            flash(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
        passage_data['translation'] = translations
        return passage_data

    @staticmethod
    def highlight_found_sents(html: str, results: List[Dict[str, Union[List[str], str]]]) -> str:
        """ Adds "searched" to the classList of words in "sents" from elasticsearch results

        :param html: the marked-up text to be searched
        :param results: the previous search session information from the session
        :return: transformed html
        """
        root = etree.fromstring(html)
        spans = root.xpath('//span[contains(@class, "w")]')
        ids = results
        if not any(ids) or spans == []:
            return html
        for sent, span in zip(ids[0]['sents'], ids[0]['sentence_spans']):
            if isinstance(span, str):
                for s in root.xpath('//span[@function="{}"]'.format(span)):
                    s.set('class', 'searched')
                for m in re.finditer(r'{}(\w+){}'.format(PRE_TAGS, POST_TAGS), sent):
                    for w_tag in root.xpath('//span[@function="{}"]//span[@class="w"]'.format(span)):
                        if w_tag.text == m.group(1):
                            w_tag.set('class', w_tag.get('class') + ' font-weight-bold')
            elif isinstance(span, range):
                for span_index, i in enumerate(span):
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
        span_pattern = re.compile(r'(<span id="\w+" class="w [\w\-]*\s?searched-start.*?searched-end".*?</span>)', re.DOTALL)
        xml_string = re.sub(span_pattern, r'<span class="searched">\1</span>', xml_string)
        return Markup(xml_string)

    def r_lexicon(self, objectId: str, lang: str = None) -> Dict[str, Any]:
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
    def r_feedback() -> Dict[str, str]:
        """ Feedback route function

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::feedback.html"}

    @staticmethod
    def r_man_desc(manuscript: str) -> Dict[str, str]:
        """ Route for manuscript descriptions

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::{}_desc.html".format(manuscript)}

    @staticmethod
    def r_man_siglen() -> Dict[str, str]:
        """ Route for manuscript descriptions

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return {"template": "main::manuscript_siglen.html"}

    @staticmethod
    def r_accessibility_statement() -> Dict[str, str]:
        """ Route for accessibility statement

        :return: Template to use for accessibility statement page
        :rtype: {str: str}
        """
        return {"template": "main::accessibility_statement.html"}

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

        notes_html = xslt(etree.fromstring(text))
        # Insert internal links
        try:
            for form_link in notes_html.xpath('//a[contains(@class, "formula-link")]'):
                form_link.set('href', url_for("InstanceNemo.r_multipassage", objectIds=form_link.get('href'), subreferences='1'))
        except:
            pass

        return str(notes_html)

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
            cit_string = re.sub(r'\s+', ' ', cit_string)
            cit_string += '<font color="grey">URL: https://werkstatt.formulae.uni-hamburg.de' + url_for("InstanceNemo.r_multipassage", objectIds=objectId, subreferences='1') + '</font>' + '<br/>'
            cit_string += '<font color="grey">' + _('Heruntergeladen: ') + date.today().isoformat() + '</font>'
            cit_string = re.sub(r'<span class="manuscript-number">(\d+)</span>', r'<sub>\1</sub>', cit_string)
            cit_string = re.sub(r'<span class="verso-recto">([^<]+)</span>', r'<super>\1</super>', cit_string)
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
        doc_title = re.sub(r'<span class="manuscript-number">(\w+)</span>',
                           r'<sub>\1</sub>',
                           re.sub(r'<span class="verso-recto">([^<]+)</span>', r'<super>\1</super>',
                                  str(metadata.metadata.get_single(DC.title, lang=None))))
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
