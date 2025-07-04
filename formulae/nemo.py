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
from .errors.handlers import e_internal_error, e_not_found_error, e_unknown_collection_error, e_not_authorized_error
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
from copy import copy, deepcopy
from typing import List, Tuple, Union, Match, Dict, Any, Sequence, Callable
from collections import defaultdict, OrderedDict
from random import randint
import roman
import requests
from itertools import zip_longest
from operator import itemgetter


class NemoFormulae(Nemo):

    ROUTES = [
        ("/", "r_index", ["GET"]),
        ("/collections", "r_collections", ["GET"]),
        ("/collections/<objectId>", "r_collection", ["GET"]),
        ("/corpus_m/<objectId>", "r_corpus_mv", ["GET"]),
        ("/corpus/<objectId>", "r_corpus", ["GET"]),
        ("/text/<objectId>/references", "r_references", ["GET"]),
        ("/texts/<objectIds>/passage/<subreferences>", "r_multipassage", ["GET"]),
        ("/texts_v2/<objectIds>/passage/<subreferences>", "r_multipassage_authentication_check", ["GET"]),
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
        ("/accessibility_statement", "r_accessibility_statement", ["GET"]),
        ("/videos", "r_videos", ["GET"]),
        ("/charter_parts", "r_parts", ["GET"]),
        ("/charter_groups", "r_groups", ["GET"]),
        ("/similar_parts", "r_part_groups", ["GET"]),
        ("/charter_formulaic", "r_charter_formulaic", ["GET"]),
        ("/formulae_formulae", "r_formulae_formulae", ["GET"]),
        ("/formulae_charter", "r_formulae_charter", ["GET"]),
        ("/collocations/<targetWord>/<word1Lemma>/<targetWord2>/<word1Type>", "r_call_word_graph_api", ["GET"]),
        ("/robots.txt", "r_robots", ["GET"])
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
        # Inherited from https://github.com/Capitains/flask-capitains-nemo/blob/982df8e89bf447235f8106e2b5c18d9e35be539a/flask_nemo/__init__.py#L405
        "get_inventory", "get_collection", "get_reffs", "get_passage", "get_siblings", "get_open_texts", "get_all_corpora",
        # Translator
        "semantic", "make_coins", "expose_ancestors_or_children", "make_members", "transform",
        # Business logic
        # "view_maker", "route", #"render",
    ]
    # For more information, please see view_maker method
    PROTECTED = [
        # "r_index", "r_collections", "r_collection", "r_references", "r_multipassage", "r_lexicon",
        # "r_add_text_collections", "r_add_text_collection", "r_corpus", "r_corpus_m", "r_add_text_corpus"
    ]

    OPEN_COLLECTIONS = ['anjou',
                        'chartae_latinae',
                        'fulda',
                        'herrscher_urkunden',
                        'langobarden',
                        'other_formulae',
                        'rheinland',
                        'touraine',
                        'urn:cts:formulae:andecavensis',
                        'urn:cts:formulae:anjou_archives',
                        'urn:cts:formulae:anjou_comtes_chroniques',
                        'urn:cts:formulae:auvergne',
                        'urn:cts:formulae:be4',
                        'urn:cts:formulae:bonneval_marmoutier',
                        'urn:cts:formulae:bourges',
                        'urn:cts:formulae:buenden',
                        'urn:cts:formulae:cartier_1841',
                        'urn:cts:formulae:chartae_latinae_xi',
                        'urn:cts:formulae:chartae_latinae_xii',
                        'urn:cts:formulae:chartae_latinae_xlvi',
                        'urn:cts:formulae:elexicon',
                        'urn:cts:formulae:echternach',
                        'urn:cts:formulae:eudes',
                        'urn:cts:formulae:flavigny',
                        'urn:cts:formulae:formulae_marculfinae',
                        'urn:cts:formulae:freising',
                        'urn:cts:formulae:fu2',
                        'urn:cts:formulae:fulda_dronke',
                        'urn:cts:formulae:fulda_stengel',
                        'urn:cts:formulae:gorze',
                        'urn:cts:formulae:hersfeld',
                        'urn:cts:formulae:ka1',
                        'urn:cts:formulae:karl_der_grosse',
                        'urn:cts:formulae:karlmann_mgh',
                        'urn:cts:formulae:ko1',
                        'urn:cts:formulae:ko2',
                        'urn:cts:formulae:konrad_mgh',
                        # 'urn:cts:formulae:langobardisch', # needs correction
                        'urn:cts:formulae:langobardisch_1',
                        'urn:cts:formulae:le1',
                        'urn:cts:formulae:le3',
                        'urn:cts:formulae:lorsch',
                        'urn:cts:formulae:lothar_2',
                        'urn:cts:formulae:ludwig_2',
                        'urn:cts:formulae:ludwig_der_juengere',
                        'urn:cts:formulae:luzern',
                        'urn:cts:formulae:m1',
                        'urn:cts:formulae:m4',
                        'urn:cts:formulae:m15',
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
                        'urn:cts:formulae:p6',
                        'urn:cts:formulae:p8',
                        'urn:cts:formulae:p10',
                        'urn:cts:formulae:p12',
                        'urn:cts:formulae:p13',
                        'urn:cts:formulae:p14',
                        'urn:cts:formulae:p16a',
                        'urn:cts:formulae:p16b',
                        'urn:cts:formulae:p16c',
                        'urn:cts:formulae:pancarte_noire',
                        'urn:cts:formulae:papsturkunden_frankreich',
                        'urn:cts:formulae:passau',
                        'urn:cts:formulae:pippin_3',
                        'urn:cts:formulae:redon',
                        'urn:cts:formulae:regensburg',
                        'urn:cts:formulae:rheinisch',
                        'urn:cts:formulae:rudolf_1_mgh',
                        'urn:cts:formulae:rudolf_2_mgh',
                        'urn:cts:formulae:rudolf_3',
                        'urn:cts:formulae:s2',
                        'urn:cts:formulae:saint_bénigne',
                        'urn:cts:formulae:salzburg',
                        'urn:cts:formulae:schaeftlarn',
                        'urn:cts:formulae:scholars',
                        'urn:cts:formulae:sens',
                        'urn:cts:formulae:sg2',
                        'urn:cts:formulae:stavelot_malmedy',
                        'urn:cts:formulae:stgallen',
                        'urn:cts:formulae:syd',
                        'urn:cts:formulae:tours',
                        'urn:cts:formulae:tours_gasnault',
                        'tours_st_julien_denis',
                        'urn:cts:formulae:tours_st_julien_fragments',
                        'urn:cts:formulae:tours_ueberarbeitung',
                        'urn:cts:formulae:v6',
                        'urn:cts:formulae:v8',
                        'urn:cts:formulae:v9',
                        'urn:cts:formulae:wa1',
                        'urn:cts:formulae:weissenburg',
                        'urn:cts:formulae:werden',
                        'urn:cts:formulae:z2',
                        'urn:cts:formulae:zuerich']

    # Half-open collections are those that are newer than death-of-editor plus 70 years.
    # We do not show the regesten for these collections since those are still protected under copyright.
    HALF_OPEN_COLLECTIONS = ['urn:cts:formulae:buenden',
                             'urn:cts:formulae:chartae_latinae_xi',
                             'urn:cts:formulae:chartae_latinae_xii',
                             'urn:cts:formulae:chartae_latinae_xlvi',
                             'urn:cts:formulae:echternach',
                             'urn:cts:formulae:fulda_stengel',
                             'urn:cts:formulae:konrad_mgh',
                             # 'urn:cts:formulae:langobardisch', # needs correction
                             'urn:cts:formulae:lorsch',
                             'urn:cts:formulae:lothar_2',
                             'urn:cts:formulae:ludwig_2',
                             'urn:cts:formulae:mondsee',
                             'urn:cts:formulae:papsturkunden_frankreich',
                             'urn:cts:formulae:regensburg',
                             'urn:cts:formulae:rheinisch',
                             'urn:cts:formulae:rudolf_1_mgh',
                             'urn:cts:formulae:rudolf_2_mgh',
                             'urn:cts:formulae:rudolf_3',
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
                              "other_formulae",
                              "langobarden"]

    LANGUAGE_MAPPING = {"lat": _l('Latein'), "deu": _l("Deutsch"), "fre": _l("Französisch"),
                        "eng": _l("Englisch"), "cat": _l("Katalanisch"), "ita": _l("Italienisch")}

    BIBO = Namespace('http://bibliotek-o.org/1.0/ontology/')
    BF = Namespace('http://id.loc.gov/ontologies/bibframe/')

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

    VIDEOS = {(1, _l('Zur einfachen und erweiterten Suche')):
                  {(1, _l('Die einfache Suche (allgemein)')):
                       {'video': 'videos/einfache_suche_'},
                   (2, _l('Aktuelle Suchergebnisse herunterladen')):
                       {'video': 'videos/suchergebnisse_herunterladen_'},
                   (3, _l('Suchergebnisse im Benutzerkonto speichern')):
                       {'video': 'videos/suchergebnisse_speichern_'},
                   (4, _l('Nach Lemmata suchen')):
                       {'video': 'videos/lemma_search_'},
                   (5, _l('Die Regestensuche')):
                       {'video': 'videos/regest_search_'},
                   (6, _l('Suchen mit Platzhalter')):
                       {'video': 'videos/wildcard_search_'},
                   },
              (2, _l('Zur Leseansicht')):
                  {(1, _l('Über die Leseansicht')):
                       {'video': 'videos/reading_page_'},
                   (2, _l('Übersetzung, Transkription oder Manuskriptbild anzeigen')):
                       {'video': 'videos/add_another_version_'},
                   (3, _l('Einen anderen Text von der selben Sammlung anzeigen')):
                       {'video': 'videos/add_from_same_collection_'},
                   (4, _l('Einen Text von einer anderen Sammlung anzeigen')):
                       {'video': 'videos/add_from_other_collection_'},
                   (5, _l('Einen dritten Text anzeigen')):
                       {'video': 'videos/add_third_text_'},
                   (6, _l('Die Leseansicht ändern')):
                       {'video': 'videos/adjust_reading_view_'},
                   (7, _l('Texte zitieren und herunterladen')):
                       {'video': 'videos/cite_download_'},
                   },
              (3, _l('Benutzerkonto erstellen und verwalten')):
                  {(1, _l('Benutzerkonto erstellen')):
                       {'video': 'videos/user_account_setup_'},
                   (2, _l('Benutzerkonto verwalten')):
                       {'video': 'videos/user_account_edit_profile_'},
                   (3, _l('Werkstattseiten im Benutzerkonto speichern')):
                       {'video': 'videos/suchergebnisse_speichern_'}
                   }
              }

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
        self.app.register_error_handler(401, e_not_authorized_error)
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

        # Load transcripts from .txt files
        for v in self.VIDEOS.values():
            for v1 in v.values():
                v1['transcripts'] = {'en': '', 'de': ''}
                for language in ('en', 'de'):
                    transcript_filename = os.path.join(self.static_folder, v1['video'] + language + '.txt')
                    if os.path.isfile(transcript_filename):
                        with open(transcript_filename) as f:
                            v1['transcripts'][language] = f.read()

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
        #folio_extraction_pattern = r'(\d+)((?:bis)?[rvab])'
        folio_extraction_pattern = r'(\d+(?:bis)?)([rv][ab]?)'

        groups = []
        # Examples:
        # '28r' → ['28', 'r']
        # '28bisr' → ['28', 'bisr']
        # '100b' → ['100', 'b']
        # '101bisv' → ['101', 'bisv']
        sub_groups = list(re.search(folio_extraction_pattern, matchobj.group(1)).groups())
        start_letter = ''
        start_letter_dict = {'m4': {range(0, 24): 'a',
                                    range(32, 40): 'b',
                                    range(24, 32): 'c',
                                    range(56, 72): 'd',
                                    range(40, 56): 'e',
                                    range(80, 86): 'f',
                                    range(72, 80): 'g'},
                             'p3': {range(0, 143): 'a',
                                    range(147, 151): 'b',
                                    range(143, 147): 'c'}
                             }
    
        if 'm4' in matchobj.group(0):
            start_fol = int(sub_groups[0])
            for k, v in start_letter_dict['m4'].items():
                if start_fol in k:
                    start_letter = v
        elif 'p3' in matchobj.group(0):
            start_fol = int(sub_groups[0])
            start_letter = 'd'
            for k, v in start_letter_dict['p3'].items():
                if start_fol in k:
                    start_letter = v
        if 'bis' in sub_groups[0]:
            groups.append('{}{} bis<span class="verso-recto">{}</span>'.format(start_letter, int(sub_groups[0].replace('bis','')), sub_groups[1]))
        else:
            groups.append('{}{:04}<span class="verso-recto">{}</span>'.format(start_letter, int(sub_groups[0]), sub_groups[1]))
            
        if matchobj.group(2):
            new_sub_groups = re.search(folio_extraction_pattern, matchobj.group(2)).groups() 
            if 'bis' in new_sub_groups[0]:
                groups.append('{} bis<span class="verso-recto">{}</span>'.format(int(new_sub_groups[0].replace('bis','')), new_sub_groups[1]))
            else:
                groups.append('{}<span class="verso-recto">{}</span>'.format(int(new_sub_groups[0]), new_sub_groups[1]))
                
        return_value = '-'.join(groups)
        if matchobj.group(3):
            return_value += '(' + matchobj.group(3) + ')'
        return return_value

    def ordered_corpora(self, m: XmlCapitainsReadableMetadata, collection: str)\
            -> Tuple[Union[str, Tuple[str, Tuple[str, str]]],
                     Union[List[Sequence[str]], list],
                     XmlCapitainsReadableMetadata]:
        """ Sets up the readable descendants in each corpus to be correctly ordered.
        These strings are later used in displaying the buttons on templates/main/sub_collection.html

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
                    elif "bis" in m.id:
                        par = re.sub(r'.*?(\d+(?:bis)?[rvab]+)(\d+(?:bis)?[rvab]+)?(\d)?\Z', self.sort_folia, list(m.parent)[0])
                    manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
                else:
                    if collection == "urn:cts:formulae:formulae_marculfinae":
                        form_num = [x for x in self.resolver.id_to_coll[list(m.parent)[0]].parent if re.search(r'marculfinae|marculf|salzburg', x)][0]
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
                    elif 'urn:cts:formulae:flavigny' in form_num:
                        if 'capitula' in form_num:
                            par = '0' + par
                    elif 'formulae:bourges.' in form_num:
                        par = re.sub(r'.*form_(\w_.*)', r'\1', form_num)
                    elif 'formulae:sens.' in form_num:
                        par = re.sub(r'.*form_(\w_.*)', r'\1', form_num)
                    if par.endswith('000') and not 'formulae:sens.' in form_num:
                        par = par.replace('000', _('(Prolog)'))
                    par = par.replace('capitula', '0')
                    manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        elif re.search(r'anjou_archives|katalonien|marmoutier_manceau', m.id):
            par = list(m.parent)[0].split('_')[-1]
            manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        elif 'formulae:bourges.' in m.id:
            par = re.sub(r'.*form_(\w_.*)', r'\1', list(m.parent)[0])
            manuscript_parts = re.search(r'(\D+)(\d+)', m.id.split('.')[-1])
            metadata = [m.id, self.LANGUAGE_MAPPING[m.lang], manuscript_parts.groups()]
        
        elif 'formulae:sens.' in m.id:
            # -> "a_001"
            self.app.logger.debug("m.i={}".format(m.id))
            par = re.sub(r'.*form_(a|b)', r'\1', list(m.parent)[0])
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
            elif 'urn:cts:formulae:flavigny' in m.id:
                if 'capitula' in m.id:
                    par = '0' + par
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
        g.half_open_texts = self.half_open_texts
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

    @staticmethod
    def sort_sigla(x: str) -> list:
        sorting_groups = list(re.search(r'(\D+)(\d+)?(\D+)?', x).groups(default=0))
        sorting_groups[1] = int(sorting_groups[1])
        return sorting_groups

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
        collection = self.resolver.getMetadata(objectId)
        data = super(NemoFormulae, self).r_collection(objectId, lang=lang)
        from_four_level_collection = re.search(r'katalonien|marmoutier_manceau|marmoutier_vendomois_appendix|marmoutier_dunois|anjou_archives|other_formulae|langobarden', objectId)
        direct_parents = [x for x in self.resolver.getMetadata(objectId).parent]
        self.app.logger.debug(str(objectId)+"'s data: "+str(data))
        if self.check_project_team() is False:
            if from_four_level_collection:
                data['collections']['members'] = [x for x in data['collections']['members']]
            else:
                data['collections']['members'] = [x for x in data['collections']['members'] if
                                                  x['id'] in self.OPEN_COLLECTIONS]
            if set(self.restricted_four_level_collections).intersection([p['id'] for p in data['collections']['parents']] + [objectId]):
                data['collections']['members'] = []
                flash(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
        if not from_four_level_collection and 'defaultTic' not in direct_parents and direct_parents != ['display_collection']:
            return redirect(url_for('InstanceNemo.r_corpus', objectId=objectId, lang=lang))
        if 0 == len(data['collections']['members']):
            self.app.logger.warn(str(objectId)+' is an empty collection')
        if len(data['collections']['members']) == 1 and objectId != 'other_formulae':
            # "redirection collection" is a collection with only one member
            # member is the collection, to which the redirect points 
            self.app.logger.debug(str(objectId)+' is a redirection collection. redirect to '+str(data['collections']['members'][0]['id']))
            return redirect(url_for('InstanceNemo.r_corpus', objectId=data['collections']['members'][0]['id'], lang=lang))
        for m in data['collections']['members']:
            m['lemmatized'] = str(self.resolver.getMetadata(m['id']).metadata.get_single(self.BIBO.Annotations)) == 'Lemmas'
            m['short_title'] = str(self.resolver.getMetadata(m['id']).metadata.get_single(self.BIBO.AbbreviatedTitle))
        data['template'] = "main::sub_collections.html"
        if 'chartae_latinae' in objectId:
            data['collections']['members'] = sorted(data['collections']['members'], key=lambda x: roman.fromRoman(str(self.resolver.getMetadata(x['id']).metadata.get_single(self.BIBO.AbbreviatedTitle)).split()[-1]))
        else:
            data['collections']['members'] = sorted(data['collections']['members'], key=lambda x: x['label'])
        all_parent_colls = list()
        parent_colls = defaultdict(list)
        # Since r_collection is only used for the top-level collections, the following lines are not needed
        # parent_textgroups = [x for x in current_parents if 'cts:textgroup' in x['subtype']]
        # parent_ids = {x['id'] for x in parent_textgroups}
        # for parent_coll in parent_textgroups:
        #     parent_colls[len(parent_ids.intersection({x for x in parent_coll['ancestors'].keys()}))].append(parent_coll)
        all_parent_colls.append([(x['id'], str(x['short_title'])) for k, v in sorted(parent_colls.items()) for x in v] + [(collection.id, str(collection.metadata.get_single(self.BIBO.AbbreviatedTitle) or ''))])
        data['breadcrumb_colls'] = [all_parent_colls]
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
        containing_colls = list()
        mss_editions = list()
        for cont_coll in sorted(collection.metadata.get(DCTERMS.isPartOf), key=lambda x: self.sort_sigla(x.split(':')[-1])):
            cont_coll_md = self.resolver.getMetadata(str(cont_coll)).metadata
            containing_colls.append((Markup(cont_coll_md.get_single(self.BIBO.AbbreviatedTitle)), cont_coll_md.get_single(DC.title), str(cont_coll)))

        form = None
        if 'elexicon' in objectId:
            template = "main::elex_collection.html"
        # elif 'salzburg' in objectId:
        #     template = "main::salzburg_collection.html"
        elif objectId in self.FOUR_LEVEL_COLLECTIONS:
            return redirect(url_for('InstanceNemo.r_collection', objectId=objectId, lang=lang))
        if collection.id not in self.all_texts:
            if collection.readable == True:
                return redirect(url_for('InstanceNemo.r_multipassage', objectIds=objectId, subreferences='all'))
            new_id = [x['id'] for x in self.make_parents(collection) if x['id'] in self.all_texts]
            raise UnknownCollection('{}'.format(collection.get_label(lang)) + _l(' ist kein bekannter Korpus.'),
                                    new_id[0] if new_id else '')
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

                def extract_short_key(par: str|tuple) -> str:
                    """
                    From 'urn:cts:formulae:formulae_marculfinae.form008' or 'form008' extract '008'.
                    """
                    if isinstance(par, tuple):
                        print('paristuple:', par)
                        par = par[0]  # get the actual key like 'form008'
                    if isinstance(par, str):
                        if par.startswith('urn:'):
                            par = par.split('.')[-1]
                        return par.replace('form', '')


                short_key = extract_short_key(par)
                if short_key in r:
                    r[short_key]["versions"][key].append(metadata + [manuscript_data])
                else:
                    r[short_key] = {
                        "versions": {'editions': [], 'translations': [], 'transcriptions': []},
                        "short_regest": '',
                        "regest": [],
                        "dating": '',
                        "ausstellungsort": '',
                        'name': '',
                        'title': '',
                        'transcribed_edition': [],
                        'parent_id': str(m.id)
                    }
                    r[short_key]["versions"][key].append(metadata + [manuscript_data])
                if key == 'editions' or 'manuscript_collection' in collection.ancestors:
                    if 'm4' in objectId or 'p3' in objectId:
                        work_name = Markup(par.lstrip('abcdefg0') if isinstance(par, str) else '')
                    else:
                        work_name = Markup(par.lstrip('0') if isinstance(par, str) else '')
                        # work_name = Markup(self.format_folia_range(par) if isinstance(par, str) else '')
                    #print('work_name',work_name,'par',par)
                    parents = self.make_parents(m)
                    parent_title = parents[0]['label']
                    if 'manuscript_collection' in collection.ancestors:
                        parent_title = [x['label'] for x in parents if 'manuscript_collection' in self.resolver.getMetadata(x['id']).ancestors][0]
                    elif 'formulae_collection' in collection.ancestors:
                        parent_title = [x['label'] for x in parents if 'manuscript_collection' not in self.resolver.getMetadata(x['id']).ancestors][0]
                    if 'urn:cts:formulae:marculf' in m.ancestors and key == 'editions':
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
                    short_regest = str(m.metadata.get_single(DCTERMS.abstract)) or ''
                    bg_color = 'bg-color-0'
                    for version_index, form_version in enumerate(sorted(m.metadata.get(DCTERMS.isVersionOf))):
                        if form_version:
                            if '_' in form_version.split('.')[-1]:
                                mss_edition = re.sub(r'(.*)\.(form)?(([2-9]_)*).*', r'\1\3', form_version)
                            else:
                                mss_edition = ''.join(form_version.split('.')[:-1])
                            if mss_edition not in mss_editions:
                                mss_editions.append(mss_edition)
                            bg_color = 'bg-color-' + str(mss_editions.index(mss_edition) + 1)
                            form_metadata = self.resolver.getMetadata(str(form_version))
                            form_parent = [str(x['id']) for x in self.make_parents(form_metadata) if 'formulae_collection' in x['ancestors'] and 'manuscript_collection' not in x['ancestors']][0]
                            for readable_form in form_metadata.readableDescendants.values():
                                form_par, form_md, form_m = self.ordered_corpora(readable_form, form_parent)
                                form_ms_data = [readable_form.metadata.get_single(DC.source), "manifest:" + readable_form.id in self.app.picture_file]
                                if readable_form.subtype == {'cts:translation'}:
                                    r[short_key]["versions"]['translations'].append(form_md + [form_ms_data])
                                elif readable_form.subtype == {'cts:edition'}:
                                    r[short_key]["versions"]['editions'].append(form_md + [form_ms_data])
                                    r[short_key]['transcribed_edition'].append(Markup(str(readable_form.metadata.get_single(DC.title)).replace(' (lat)', '')))
                                    if version_index == 0:
                                        regest = [Markup(readable_form.metadata.get_single(DC.description))]
                                        short_regest = Markup(str(readable_form.metadata.get_single(DCTERMS.abstract)))
                    # The following lines are to deal with the Pancarte Noire double regests
                    if self.check_project_team() is False and (m.id in self.closed_texts['half_closed'] or m.id in self.closed_texts['closed']):
                        if len(regest) == 2:
                           regest[1] = Markup('<b>REGEST EDITION</b>: ' + '<i>{}</i>'.format(_('Dieses Regest ist nicht öffentlich zugänglich.')))

                    r[short_key].update({"short_regest": short_regest,
                                   "regest": regest,
                                   "dating": str(m.metadata.get_single(DCTERMS.temporal)),
                                   "ausstellungsort": str(m.metadata.get_single(DCTERMS.spatial)),
                                   'name': work_name,
                                   'title': Markup(str(self.make_parents(m)[0]['label'])),
                                   'translated_title': str(m.metadata.get_single(DCTERMS.alternative) or ''),
                                   'deperditum': str(m.metadata.get_single(self.BF.status)) == 'deperditum',
                                   'problematic': str(m.metadata.get_single(self.BIBO.Activity)) if m.metadata.get_single(self.BIBO.Activity) else '',
                                   "source_edition": str(m.metadata.get_single(DCTERMS.source) or ''),
                                   'bg_color': bg_color})


        for key, v in collection.children.items():
            if not v.children:
                replacement_data = [str(v.metadata.get_single(DCTERMS.isPartOf) or ''),
                                    str(v.metadata.get_single(DCTERMS.isReplacedBy) or '')]
                if all(replacement_data):
                    #par = re.sub(r'.*?(\d+\w*)\Z', r'\1', k)
                    
                    #par = re.sub(r'^.*?\.(\d+\w*(?:\d+\w*)?)$', r'\1', key)
                    short_key = extract_short_key(key)

                    replacement_md = self.resolver.getMetadata(replacement_data[-1])
                    regest = [Markup(replacement_md.metadata.get_single(DC.description))] if 'formulae_collection' in collection.ancestors else [Markup(x) for x in str(replacement_md.metadata.get_single(DC.description)).split('***')]
                    short_regest = str(replacement_md.metadata.get_single(DCTERMS.abstract)) or ''
                    replacement_par = re.sub(r'.*?(\d+\w*)\Z', r'\1', list(replacement_md.parent)[0])
                    #r[short_key] = {"versions": {'editions': [], 'translations': [], 'transcriptions': []},
                    r[short_key] = {"versions": {'editions': [], 'translations': [], 'transcriptions': []},
                              "short_regest": short_regest,
                              "regest": regest,
                              "dating": '',
                              "ausstellungsort": '',
                              'name': v.metadata.get_single(DC.title),
                              'title': v.metadata.get_single(DC.title),
                              'transcribed_edition': [],
                              'parent_id': '',
                              'alt_link': url_for('InstanceNemo.r_corpus', objectId=replacement_data[0]) + '#N' + replacement_par,
                              'alt_title': Markup(replacement_md.metadata.get_single(DC.title) or '').replace(' (lat)', '')}



        from formulae.services.corpus_service import extract_folio_sort_key

        def normalize_sort_key(item_key):
            if isinstance(item_key, str):
                return extract_folio_sort_key(item_key)
            elif isinstance(item_key, tuple):
                return extract_folio_sort_key(item_key[0])
            return (9999, 99)

        # r = OrderedDict(sorted(r.items(), key=lambda item: normalize_sort_key(item[0])))
        r = OrderedDict(
            sorted(
                ((k, v) for k, v in r.items() if isinstance(k, (str, tuple))),  # skip ellipsis
                key=lambda item: normalize_sort_key(item[0])
            )
        )



        #r = OrderedDict(sorted(r.items()))
        for k in r.keys():
            valid_trans = [
                t for t in r[k]['versions']['transcriptions']
                if isinstance(t, (list, tuple)) and len(t) > 2 and isinstance(t[2], (list, tuple)) and len(t[2]) > 1
                    and isinstance(t[2][1], (str, int)) and str(t[2][1]).isdigit()
            ]
            r[k]['versions']['transcriptions'] = sorted(
                sorted(valid_trans, key=lambda x: int(x[2][1])),
                key=lambda x: x[2][0]
            )

 

        if len(r) == 0:
            if 'manuscript_collection' in collection.ancestors:
                flash(_('Um das Digitalisat dieser Handschrift zu sehen, besuchen Sie bitte gegebenenfalls die Homepage der Bibliothek.'))
            else:
                flash(_('Diese Sammlung ist nicht öffentlich zugänglich.'))

        all_parent_colls = list()
        parent_colls = defaultdict(list)
        parent_textgroups = [x for x in current_parents if 'cts:textgroup' in x['subtype']]
        parent_ids = {x['id'] for x in parent_textgroups}
        for parent_coll in parent_textgroups:
            parent_colls[len(parent_ids.intersection({x for x in parent_coll['ancestors'].keys()}))].append(parent_coll)
        for key, v in sorted(parent_colls.items()):
            if v:
                all_parent_colls.append([(x['id'], str(x['short_title'])) for x in v])
        all_parent_colls.append([(collection.id, str(collection.metadata.get_single(self.BIBO.AbbreviatedTitle) or ''))])

        return_value = {
            "template": template,
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                    "open_regesten": collection.id not in self.HALF_OPEN_COLLECTIONS,
                    "short_title": collection.metadata.get_single(self.BIBO.AbbreviatedTitle) or '',
                    "containing_collections": containing_colls
                },
                # later consumed in templates/main/sub_collection.html:
                # {% for number, values in collections.readable.items() %}
                "readable": r,
                "parents": current_parents,
                "parent_ids": [x['id'] for x in current_parents],
                "first_letters": set([x[0] for x in r.keys()])
            },
            "form": form,
            'manuscript_notes': self.manuscript_notes,
            'breadcrumb_colls': [all_parent_colls]
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
        list_of_readable_descendants = copy(self.all_texts[collection.id])

        if 'manuscript_collection' in collection.ancestors:
            related_mss = set()
            for ms_r_d in list_of_readable_descendants:
                form_parent = [self.resolver.getMetadata(v['id']) for v in self.make_parents(ms_r_d[-1]) if 'manuscript_collection' not in v['ancestors']][0]
                form_mss_r = [v_r for v_r in form_parent.readableDescendants.values() if 'manuscript_collection' in v_r.ancestors]
                for form_ms_r in form_mss_r:
                    related_mss.add([v['id'] for v in self.make_parents(form_ms_r) if 'manuscript_collection' in v['ancestors']][-1])
            list_of_readable_descendants = list()
            for related_ms in related_mss:
                list_of_readable_descendants += self.all_texts[related_ms]

        if {'formulae_collection', 'manuscript_collection'} & set(collection.ancestors):
            for par, metadata, m in list_of_readable_descendants:
                if self.check_project_team() is True or m.id in self.open_texts:
                    edition = str(m.id).split(".")[-1]
                    if 'manuscript_collection' in m.ancestors:
                        edition = str(m.id).split(':')[-1].split('.')[0]
                    if 'manuscript_collection' in collection.ancestors:
                        ed_titles = list()
                        for ed_parent_id in sorted(m.metadata.get(DCTERMS.isVersionOf)):
                            ed_parent = self.resolver.getMetadata(str(ed_parent_id))
                            ed_titles.append([v.metadata.get_single(DC.title) for v in ed_parent.readableDescendants.values() if 'cts:edition' in v.subtype][0].replace(' (lat)', ''))
                            form = ed_parent.id
                        title = '/'.join(sorted(ed_titles))
                    else:
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
                # transcriptions
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
                            new_parents.append('[fol.' + t_parent.lstrip('0abcdefg').replace('</span>-', '</span>-fol.') + ']')
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

            r['transcriptions'] = sorted(sorted(r['transcriptions'], key=lambda x: self.sort_sigla(x['name'])), key=lambda x: x['name'] not in collection.id)

        else:

            r = {'editions': [], 'translations': [], 'transcriptions': []}
            flash(_('Diese View ist nur für Formelsammlungen verfuegbar'))

        if r == {'editions': [], 'translations': [], 'transcriptions': []}:
            flash(_('Diese Sammlung ist nicht öffentlich zugänglich.'))

        current_parents = self.make_parents(collection, lang=lang)

        all_parent_colls = list()
        parent_colls = defaultdict(list)
        # Since corpus_mv is only used for the top-level formulae collections, the following lines are not needed
        # parent_textgroups = [x for x in current_parents if 'cts:textgroup' in x['subtype']]
        # parent_ids = {x['id'] for x in parent_textgroups}
        # for parent_coll in parent_textgroups:
        #     parent_colls[len(parent_ids.intersection({x for x in parent_coll['ancestors'].keys()}))].append(parent_coll)
        all_parent_colls.append([(x['id'], str(x['short_title'])) for k, v in sorted(parent_colls.items()) for x in v] + [(collection.id, str(collection.metadata.get_single(self.BIBO.AbbreviatedTitle) or ''))])

        return_value = {
            "template": template,
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                    "open_regesten": collection.id not in self.HALF_OPEN_COLLECTIONS,
                    "short_title": collection.metadata.get_single(self.BIBO.AbbreviatedTitle) or '',
                },
                "readable": r,
                "parents": current_parents,
                "parent_ids": [x['id'] for x in current_parents]
            },
            'manuscript_notes': self.manuscript_notes,
            'breadcrumb_colls': [all_parent_colls]
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
        from_four_level_collection = re.search(r'katalonien|marmoutier_manceau|marmoutier_vendomois_appendix|marmoutier_dunois|anjou_archives|other_formulae', objectId)
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

    def get_prev_next_texts(self, objectId: str) -> Dict[str, Union[str, list]]:
        """ Get the previous and next texts in a collection

        :param objectId: the ID of the current object
        :return: the IDs of the previous and next text in the same collection and lists of all previous and next texts
        """
        id_parts = objectId.split('.')
        text = self.resolver.getMetadata(objectId)
        grandparents = set()
        for x in text.parent:
            grandparents.update(self.resolver.getMetadata(x).parent)
        if text.subtype & {'cts:translation', 'cts:edition'}:
            language = re.search(r'(\w\w\w)\d\d\d\Z', objectId).group(1)
            sibling_texts = []
            for gp in grandparents:
                for x in self.all_texts[gp]:
                    if x[2].subtype & text.subtype and re.search(r'{}\d\d\d\Z'.format(language), x[1][0]):
                        text_label = Markup(self.make_parents(x[2])[0]['label'])
                        sibling_texts.append((x[1][0], text_label))
        else:
            sibling_texts = []
            for gp in grandparents:
                if gp in self.all_texts:
                    for x in self.all_texts[gp]:
                        if x[1][0].split('.')[-1] == id_parts[-1]:
                            text_label = Markup(self.make_parents(x[2])[0]['label'])
                            sibling_texts.append((x[1][0], text_label))
        orig_index = sibling_texts.index((objectId, str(self.make_parents(text)[0]['label'])))
        return {'prev_version': sibling_texts[orig_index - 1][0] if orig_index > 0 else None,
                'next_version': sibling_texts[orig_index + 1][0] if orig_index + 1 < len(sibling_texts) else None,
                'all_prev_versions': sibling_texts[:orig_index] if orig_index > 0 else None,
                'all_next_versions': sibling_texts[orig_index + 1:] if orig_index + 1 < len(sibling_texts) else None}

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
        if identifier == 'other_formulae':
            return 'zzz', 1000
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

    def get_mss_eds(self, metadata, split_token: str = "**") -> list[str]:
        """ 
        Extracts a list of manuscript edition references from the metadata.

        The method retrieves the value associated with the Dublin Core 'references' field,
        splits it into separate entries based on a given split token (defaulting to "\*\*"),
        and unescapes any escaped "**" sequences within each entry.

        :param metadata: the metadata object containing a 'DCTERMS.references' field
        :param split_token: the delimiter used to separate edition entries (default '**')
        :return: a list of manuscript edition references as strings
        """
        # Check if 'references' field is present in the metadata
        if metadata.metadata.get_single(DCTERMS.references):
            # Get the field value and split it using the split_token (default '**')
            mss_eds_list = str(metadata.metadata.get_single(DCTERMS.references)).split(split_token)

            # Unescape any escaped '**' (i.e., replace '\*\*' with '**')
            mss_eds_list = [mss_edition.replace('\*\*', '**') for mss_edition in mss_eds_list]

            return mss_eds_list
        else:
            # If no references exist, return an empty list
            return []


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
        # The following is to deal with the Pancarte Noire texts that are still under copyright
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
                    in_ref_coll = self.resolver.getMetadata(ref[0])
                    inRefs.append([(in_ref_coll.id, Markup(in_ref_coll.get_label())), cits])
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
        # The following lines are to deal with the Pancarte Noire double regests
        if self.check_project_team() is False and (metadata.id in self.closed_texts['half_closed'] or metadata.id in self.closed_texts['closed']):
            if len(regest) == 2:
                regest[1] = Markup('<b>REGEST EDITION</b>: ' + '<i>{}</i>'.format(_('Dieses Regest ist nicht öffentlich zugänglich.')))
        transcribed_edition = []

        for mss_ed in metadata.metadata.get(DCTERMS.isVersionOf):
            if str(mss_ed):
                ed_name = self.resolver.getMetadata(str(mss_ed))
                for child_id, child_col in ed_name.children.items():
                    if str(child_col.metadata.get_single(DC.type)) == 'cts:edition':
                        transcribed_edition.append(str(child_col.metadata.get_single(DC.title)).replace(' (lat)', ''))

        coll_label = str(metadata.metadata.get_single(DC.title, lang=None)) or metadata.get_label(lang)
        if 'manuscript_collection' in metadata.ancestors:
            coll_siglum = [x['short_title'] for x in self.make_parents(m) if 'manuscript_collection' in x['ancestors']][-1]
            coll_label = '{} ({})<br>[{}'.format(coll_label.split(' [')[0], coll_siglum, coll_label.split(' [')[-1])

        return {
            "template": "",
            "objectId": objectId,
            "subreference": subreference,
            "collections": {
                "current": {
                    "label": coll_label,
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
                    'citation': str(metadata.metadata.get_single(DCTERMS.bibliographicCitation, lang=lang)).replace('&lt;', '<').replace('&gt;', '>'),
                    "short_regest": str(metadata.metadata.get_single(DCTERMS.abstract)) if 'formulae_collection' in [x['id'] for x in current_parents] else '',
                    "dating": str(metadata.metadata.get_single(DCTERMS.temporal) or ''),
                    "issued_at": str(metadata.metadata.get_single(DCTERMS.spatial) or ''),
                    "sigla": str(metadata.metadata.get_single(DCTERMS.isPartOf) or ''),
                    "ms_source": str(metadata.metadata.get_single(DCTERMS.source)).split('***') if metadata.metadata.get_single(DCTERMS.source) else '',
                    "linked_resources": linked_resources,
                    "transcribed_edition": sorted([Markup(x) for x in transcribed_edition]),
                    "mss_eds": self.get_mss_eds(metadata),
                    'problematic': str(metadata.metadata.get_single(self.BIBO.Activity)) if metadata.metadata.get_single(
                        self.BIBO.Activity) else ''
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
    
    
    def r_multipassage_authentication_check(self, objectIds: str, subreferences: str, lang: str = None, collate: bool = False) -> Dict[str, Any]:
        """ Wrapper method for r_multipassage. Requires all users to be logged in, when using '+' in the query. It should eventually replace r_multipassage.

        :param objectIds: Collection identifiers separated by '+'
        :param lang: Lang in which to express main data
        :param subreferences: Reference identifiers separated by '+'
        :return: Template, collections metadata and Markup object representing the text
        """
        # Example call:
        # /texts/urn:cts:formulae:bourges.form_a_007.lat001+urn:cts:formulae:be4.86v.lat001+urn:cts:formulae:andecavensis.form000.lat001/passage/1+1+all
        if '+' in objectIds or '+' in subreferences:
            if not current_user.is_authenticated:
                if not 'dev' in self.app.config['SERVER_TYPE'].lower():
                    abort(401)
        return self.r_multipassage(objectIds, subreferences, lang, collate)
        

    def r_multipassage(self, objectIds: str, subreferences: str, lang: str = None, collate: bool = False) -> Dict[str, Any]:
        """ Retrieve the text of the passage

        :param objectIds: Collection identifiers separated by '+'
        :param lang: Lang in which to express main data
        :param subreferences: Reference identifiers separated by '+'
        :return: Template, collections metadata and Markup object representing the text
        """
        # authentication check:
        texts_threshold = self.app.config['MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER']
        if (texts_threshold <= objectIds.count('+')  or texts_threshold <= subreferences.count('+')) and \
            not current_user.is_authenticated and \
            not 'dev' in self.app.config['SERVER_TYPE'].lower():
                abort(401)

        if 'reading_format' not in session:
            session['reading_format'] = 'columns'
        ids = objectIds.split('+')
        translations = {}
        view = 1
        passage_data = {'template': 'main::multipassage.html', 'objects': [], "translation": {}}
        subrefers = subreferences.split('+')
        all_parent_colls = list()
        collate_html_dict = dict()
        if 'collate' in request.values:
            collate_html_dict = self.call_collate_api(obj_ids=ids, subrefers=subrefers)
        if len(subrefers) != len(ids):
            abort(404)
        for i, id in enumerate(ids):
            manifest_requested = False
            if id in self.dead_urls:
                id = self.dead_urls[id]
            if "manifest:" in id:
                id = re.sub(r'^manifest:', '', id)
                manifest_requested = True
            if self.check_project_team() is True or id in self.open_texts:
                if subrefers[i] in ["all", 'first']:
                    subref = self.get_reffs(id)[0][0]
                else:
                    subref = subrefers[i]
                d = self.r_passage(id, subref, lang=lang)
                d['text_passage'] = collate_html_dict.get(id, d['text_passage'])
                d.update(self.get_prev_next_texts(d['objectId']))
                del d['template']
                parent_colls = defaultdict(list)
                parent_colls[99] = [(id, str(d['collections']['current']['label'].replace('<br>', ' ')))]
                parent_textgroups = [x for x in d['collections']['parents'] if 'cts:textgroup' in x['subtype']]
                for parent_coll in parent_textgroups:
                    grandparent_depths = list()
                    for grandparent in parent_coll['ancestors'].values():
                        start_number = 0
                        if 'cts:textgroup' in grandparent.subtype:
                            start_number = 1
                        grandparent_depths.append(len([x for x in self.make_parents(grandparent) if 'cts:textgroup' in x['subtype']]) + start_number)
                    max_grandparent_depth = max(grandparent_depths)
                    parent_colls[max_grandparent_depth].append((parent_coll['id'], str(parent_coll['short_title'])))
                all_parent_colls.append([v for k, v in sorted(parent_colls.items())])
                translations[id] = []
                for x in d.pop('translations', None):
                    if x[0].id not in ids and x not in translations[id]:
                        translations[id].append(x)
                if manifest_requested:
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
                    self.app.logger.warn("this_manifest['@id'] {}".format(this_manifest['@id']))
                    if 'fuldig.hs-fulda.de' in this_manifest['@id']:
                        # This works for resources from https://fuldig.hs-fulda.de/
                        d['lib_link'] = this_manifest['sequences'][0]['canvases'][0]['rendering'][1]['@id']
                    elif 'gallica.bnf.fr' in this_manifest['@id']:
                        # This link needs to be constructed from the thumbnail link for images from https://gallica.bnf.fr/
                        d['lib_link'] = this_manifest['sequences'][0]['canvases'][0]['thumbnail']['@id'].replace('.thumbnail', '')
                        self.app.logger.warn("gallica.bnf.fr: lib_link created:{}".format(d['lib_link']))
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
                    elif 'digital.blb-karlsruhe.de' in this_manifest['@id']:
                        # This works for resources from the BLB Karlsrühe
                        # This links to the manuscript as a whole.
                        # I am not sure how to link to specific pages in their IIIF viewer.
                        d['lib_link'] = 'https://i3f.vls.io/?collection=i3fblbk&id=' + this_manifest['@id']
                    elif 'www.e-codices.unifr.ch' in this_manifest['@id']:
                        # This works for resources from the E-Codices
                        d['lib_link'] = this_manifest['related'].replace('/list/one', '') + '/' + this_manifest['sequences'][0]['canvases'][0]['label']
                    
                    self.app.logger.debug(msg="lib_link: {}".format(d['lib_link']))
                    
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

                    
                    self.app.logger.warn(msg='d["IIIFviewer"]: {}'.format(d["IIIFviewer"]))
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
        passage_data['breadcrumb_colls'] = all_parent_colls
        if len(ids) > len(passage_data['objects']):
            flash(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
        passage_data['translation'] = translations
        passage_data['videos'] = [v for k, v in self.VIDEOS.items() if 2 in k][0]
        passage_data['word_graph_url'] = self.app.config['WORD_GRAPH_API_URL']
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
        span_pattern = re.compile(r'(<span id="\w+" (inflected="\w+" )?class="w [\w\-]*\s?searched-start.*?searched-end".*?</span>)', re.DOTALL)
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

    def call_collate_api(self, obj_ids: list, subrefers: list) -> Dict[str, str]:
        """ Transforms texts, sends them to collate API and transforms the results

        :return:
        """
        json_input = {'texts': dict(), 'xpath': '//tei:w//text()'}
        obj_dict = dict()
        for i, obj_id in enumerate(obj_ids):
            text = self.get_passage(objectId=obj_id, subreference=subrefers[i])
            obj_dict[obj_id] = text
            xml = text.export(Mimetypes.PYTHON.ETREE)
            json_input['texts'][obj_id] = etree.tostring(xml, encoding='unicode')
        r = requests.post(os.path.join(self.app.config['COLLATE_API_URL'], 'collate_xml'), json=json_input)
        html_output_dict = dict()
        for k, v in r.json().items():
            return_xml = etree.fromstring(v)
            html_output_dict[k] = Markup(self.transform(obj_dict[k], return_xml, k))
        return html_output_dict

    def r_call_word_graph_api(self, targetWord: str, word1Lemma: str, targetWord2: str, word1Type: str):
        opposite_type = {'inflected': 'lemma', 'lemma': 'inflected'}
        target_word = targetWord
        extra_params = list()
        coll_dict = None
        if word1Type == 'lemma':
            target_word = word1Lemma
            extra_params.append('lemmas=true')
        target_corpus = request.args.get('corpus', '')
        if target_corpus:
            extra_params.append('includedcollections=' + target_corpus)
            coll_dict = session.get('word_graph_used_colls', None)
        extra_params = '?{}'.format('&'.join(extra_params))
        if targetWord2 == 'None':
            r = requests.get(os.path.join(self.app.config['WORD_GRAPH_API_URL'],
                                          'word',
                                          target_word,
                                          'neighbors',
                                          'maxneighborhops',
                                          '1{}'.format(extra_params)))
            return_data = dict()
            used_colls = set()
            for x in r.json():
                if x['word']:
                    used_colls.add(x['in_collection'])
                    return_data[x['word']] = int(x['in_text_quantity'])
            if not coll_dict:
                coll_dict = {'Formulae': [c for c in self.sub_colls['formulae_collection'] if c['id'] in used_colls],
                             'Urkunden': defaultdict(list)}
                for sub_coll in self.sub_colls['other_collection']:
                    if sub_coll['id'] in used_colls:
                        coll_dict['Urkunden'][sub_coll['coverage']].append(sub_coll)
                session['word_graph_used_colls'] = coll_dict
            return {'template': 'main::word_graph_modal.html',
                    'data': return_data,
                    'target_word': targetWord, 'target_lemma': word1Lemma, 'target_type': word1Type,
                    'opposite_type': opposite_type[word1Type], 'target_corpus': target_corpus, 'coll_dict': coll_dict}
        else:
            r = requests.get(os.path.join(self.app.config['WORD_GRAPH_API_URL'],
                                          'text',
                                          'mutual',
                                          target_word,
                                          targetWord2,
                                          'maxneighborhops',
                                          '1{}'.format(extra_params)))
            return '<ul>{}</ul>'.format(
                '\n'.join(['<li><a href="{}" target="_blank">{}</a></li>'.format(
                    url_for("InstanceNemo.r_multipassage", objectIds=x['title'], subreferences='1'),
                    x['headline']) for x in sorted(r.json(), key=itemgetter('title'))]))

    @staticmethod
    def r_robots():
        """ Route for the robots.txt

        :param filetype: Asset Type
        :param asset: Filename of an asset
        :return: Response
        """
        return send_from_directory("assets", "robots.txt")

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

    def r_videos(self) -> Dict[str, Union[str, List[Tuple[str]]]]:
        """ Route for videos

        :return: Video template with video and subtitle filenames
        :rtype: {str: str, str: list(tuple(str))}
        """
        return {"template": "main::videos.html", 'videos': self.VIDEOS}

    def r_parts(self) -> Dict[str, Union[str, List[Tuple[str]]]]:
        """ Route for page with data from Franziska Quaas showing all charters with certain formulaic parts

        :return: all_parts template
        :rtype: {str: str, str: list(tuple(str))}
        """
        return {"template": "main::all_parts.html"}

    def r_part_groups(self) -> Dict[str, Union[str, List[Tuple[str]]]]:
        """ Route for page with data from Franziska Quaas showing similar parts for Arengen and Überleitungsformel

        :return: all_parts template
        :rtype: {str: str, str: list(tuple(str))}
        """
        return {"template": "main::charter_parts.html"}

    def r_groups(self) -> Dict[str, Union[str, List[Tuple[str]]]]:
        """ Route for page with data from Franziska Quaas showing charter and charter part groups

        :return: all_parts template
        :rtype: {str: str, str: list(tuple(str))}
        """
        return {"template": "main::charter_groups.html"}

    def r_formulae_formulae(self) -> Dict[str, Union[str, List[Tuple[str]]]]:
        """ Route for page with data from Franziska Quaas showing formulae with formulae agreements

        :return: all_parts template
        :rtype: {str: str, str: list(tuple(str))}
        """
        return {"template": "main::formulae_formulae.html"}

    def r_formulae_charter(self) -> Dict[str, Union[str, List[Tuple[str]]]]:
        """ Route for page with data from Franziska Quaas showing formulae with charter agreements

        :return: all_parts template
        :rtype: {str: str, str: list(tuple(str))}
        """
        return {"template": "main::formulae_charter.html"}

    def r_charter_formulaic(self) -> Dict[str, Union[str, List[Tuple[str]]]]:
        """ Route for page with intro and links to data from Franziska Quaas

        :return: all_parts template
        :rtype: {str: str, str: list(tuple(str))}
        """
        return {"template": "main::charter_formulae.html"}

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
        """Produces a PDF from the objectId for download and then delivers it.

        If the objectId is not part of the open_texts a pdf only generated if project member tries to access it.

        :param objectId: the URN of the text to transform
        :return:
        """
        if self.check_project_team() is False and objectId not in self.open_texts:
            flash(_('Das PDF für diesen Text ist nicht zugänglich.'))
            return redirect(url_for('InstanceNemo.r_index'))
        from formulae.services.pdf_service import render_pdf_response
        return render_pdf_response(
            objectId=objectId,
            resolver=self.resolver,
            static_folder=self.static_folder,
            check_project_team=self.check_project_team,
            transform=self.transform,
            get_passage=self.get_passage,
            get_reffs=self.get_reffs,
            encryption_pw=self.app.config['PDF_ENCRYPTION_PW']
        )
