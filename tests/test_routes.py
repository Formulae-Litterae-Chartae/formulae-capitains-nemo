from config import Config
from MyCapytain.resolvers.capitains.local import XmlCapitainsLocalResolver
from formulae import create_app, db, mail
from formulae.nemo import NemoFormulae
from formulae.models import User
from formulae.search.Search import advanced_query_index, build_sort_list, \
    suggest_word_search, PRE_TAGS, POST_TAGS
from formulae.search import Search
from flask_nemo.filters import slugify
from formulae.search.forms import AdvancedSearchForm, SearchForm
from formulae.auth.forms import LoginForm, PasswordChangeForm, LanguageChangeForm, ResetPasswordForm, \
    ResetPasswordRequestForm, RegistrationForm, ValidationError, EmailChangeForm
from flask_login import current_user
from flask_babel import _
from elasticsearch import Elasticsearch
from unittest.mock import patch, mock_open
from unittest import TestCase
from tests.fake_es import FakeElasticsearch
from collections import OrderedDict
import os
from MyCapytain.common.constants import Mimetypes
from flask import Markup, session, g, url_for, abort, template_rendered, message_flashed
from json import dumps, load
import re
from datetime import date
from copy import copy
from lxml import etree
from itertools import cycle


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    CORPUS_FOLDERS = ["tests/test_data/formulae"]
    INFLECTED_LEM_JSONS = ["tests/test_data/formulae/inflected_to_lem.json"]
    LEM_TO_LEM_JSONS = ["tests/test_data/formulae/lem_to_lem.json"]
    DEAD_URLS = ["tests/test_data/formulae/dead_urls.json"]
    COMP_PLACES = ["tests/test_data/formulae/composition_places.json"]
    LEMMA_LISTS = ["tests/test_data/formulae/lem_list_1.json", "tests/test_data/formulae/lem_list_2.json"]
    # TERM_VECTORS = "tests/test_data/formulae/composition_places.json"
    WTF_CSRF_ENABLED = False
    SESSION_TYPE = 'filesystem'
    SAVE_REQUESTS = False
    IIIF_MAPPING = "tests/test_data/formulae/iiif"
    IIIF_SERVER = "http://127.0.0.1:5004"


class NoESConfig(TestConfig):
    ELASTICSEARCH_URL = None


class SSLESConfig(TestConfig):
    ELASTICSEARCH_URL = "https://some.secure.server/elasticsearch"
    ES_CLIENT_CERT = "SomeFile"
    ES_CLIENT_KEY = "SomeOtherFile"


class NormalESConfig(TestConfig):
    ELASTICSEARCH_URL = "Normal ES Server"


class InvalidIIIFMappingConfig(TestConfig):
    IIIF_MAPPING = "tests/test_data/formulae/data/mapping_error"


class NoIIIFMappingConfig(TestConfig):
    IIIF_MAPPING = ""


class NoIIIFServerConfig(TestConfig):
    IIIF_SERVER = None


def term_vector_default_value():
    return TestES.MOCK_VECTOR_RETURN_VALUE


class Formulae_Testing(TestCase):
    def create_app(self):

        app = create_app(TestConfig)
        resolver = XmlCapitainsLocalResolver(app.config['CORPUS_FOLDERS'])
        NemoFormulae.PROTECTED = ['r_contact']
        self.nemo = NemoFormulae(name="InstanceNemo", resolver=resolver,
                                 app=app, base_url="", transform={"default": "components/epidoc.xsl",
                                                                  "notes": "components/extract_notes.xsl",
                                                                  "elex_notes": "components/extract_elex_notes.xsl",
                                                                  "pdf": "components/xml_to_pdf.xsl"},
                                 templates={"main": "templates/main",
                                            "errors": "templates/errors",
                                            "auth": "templates/auth",
                                            "search": "templates/search",
                                            "viewer": "templates/viewer"},
                                 css=["assets/css/theme.css"], js=["assets/js/empty.js"], static_folder="./assets/",
                                 pdf_folder="pdf_folder/")

        self.templates = []
        self.flashed_messages = []
        app.config['nemo_app'] = self.nemo
        self.nemo.open_texts += ['urn:cts:formulae:buenden.meyer-marthaler0024.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0025.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0027.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0028.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0086.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0140.lat001',
                                 'urn:cts:formulae:freising.bitterauf0090.lat001',
                                 'urn:cts:formulae:papsturkunden_frankreich.ramackers0131.lat001']

        @app.route('/500', methods=['GET'])
        def r_500():
            abort(500)

        return app

    def setUp(self):
        self.app = self.create_app()
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.templates = []
        self.flashed_messages = []
        template_rendered.connect(self._add_template)
        message_flashed.connect(self._add_flash_message)
        db.create_all()
        u = User(username="project.member", email="project.member@uni-hamburg.de", project_team=True)
        u.set_password('some_password')
        db.session.add(u)
        u = User(username="not.project", email="not.project@uni-hamburg.de", project_team=False)
        u.set_password('some_other_password')
        db.session.add(u)
        db.session.commit()
        self.maxDiff = None
        with open('tests/test_data/advanced_search/all_term_vectors.json') as f:
            self.term_vectors = load(f)
        self.search_response = dict()
        self.search_aggs = dict()

    def tearDown(self):
        template_rendered.disconnect(self._add_template)
        message_flashed.disconnect(self._add_flash_message)
        db.session.remove()
        db.drop_all()

    def _add_flash_message(self, app, message, category):
        self.flashed_messages.append((message, category))

    def _add_template(self, app, template, context):
        if len(self.templates) > 0:
            self.templates = []
        self.templates.append((template, context))

    def get_context_variable(self, name):
        """
        Returns a variable from the context passed to the
        template. Only works if your version of Flask
        has signals support (0.6+) and blinker is installed.
        Raises a ContextVariableDoesNotExist exception if does
        not exist in context.
        :versionadded: 0.2
        :param name: name of variable
        """

        for template, context in self.templates:
            if name in context:
                return context[name]
        raise AttributeError('{} does not exist in this context')


class TestNemoSetup(Formulae_Testing):

    def test_setup_global_app(self):
        """ Make sure that the instance of Nemo on the server is created correctly"""
        if os.environ.get('CI'):
            # This should only be tested on a remote CI system since I don't want it to run locally
            from formulae.app import nemo
            self.assertEqual(nemo.open_texts + ['urn:cts:formulae:buenden.meyer-marthaler0024.lat001',
                                                'urn:cts:formulae:buenden.meyer-marthaler0025.lat001',
                                                'urn:cts:formulae:buenden.meyer-marthaler0027.lat001',
                                                'urn:cts:formulae:buenden.meyer-marthaler0028.lat001',
                                                'urn:cts:formulae:buenden.meyer-marthaler0086.lat001',
                                                'urn:cts:formulae:buenden.meyer-marthaler0140.lat001',
                                                'urn:cts:formulae:freising.bitterauf0090.lat001',
                                                'urn:cts:formulae:papsturkunden_frankreich.ramackers0131.lat001'],
                             self.nemo.open_texts)
            self.assertEqual(nemo.sub_colls, self.nemo.sub_colls)
            self.assertEqual(nemo.pdf_folder, self.nemo.pdf_folder)
            # self.assertEqual(self.nemo.term_vectors['urn:cts:formulae:katalonien.vinyals_albanyamonestirpere_0001.lat001'],
            #                  TestES.MOCK_VECTOR_RETURN_VALUE)
            # self.assertEqual(self.nemo.term_vectors['urn:cts:formulae:marmoutier_manceau.laurain_ballée_0001.lat001'],
            #                  TestES.MOCK_VECTOR_RETURN_VALUE)


class TestInit(TestCase):

    def test_non_secure_es_server(self):
        """ Make sure that an ES server with no SSL security is correctly initiated"""
        app = create_app(NormalESConfig)
        self.assertEqual(app.elasticsearch.transport.hosts[0]['host'], NormalESConfig.ELASTICSEARCH_URL.lower())

    def test_secure_es_server(self):
        """ Make sure that an ES server with no SSL security is correctly initiated"""
        app = create_app(SSLESConfig)
        self.assertEqual(app.elasticsearch.transport.hosts[0]['host'],
                         'some.secure.server',
                         'Host server name should be correct.')
        self.assertTrue(app.elasticsearch.transport.hosts[0]['use_ssl'], 'SSL should be enabled.')

    def test_no_es_server(self):
        """ Make sure that the app is initiated correctly when no ES server is given"""
        app = create_app(NoESConfig)
        self.assertIsNone(app.elasticsearch)

    def test_with_bad_iiif_mapping(self):
        """ Make sure that app initiates correctly when the IIIF mapping file is not valid"""
        with self.assertLogs() as cm:
            app = create_app(InvalidIIIFMappingConfig)
        self.assertIn(_('Der Viewer konnte nicht gestartet werden.'), [x.msg for x in cm.records])
        self.assertFalse(app.IIIFviewer, "No IIIF Viewer should be loaded with an invalid mapping file.")
        self.assertEqual(app.picture_file, "", "picture_file should be an empty string with invalid mapping file.")

    def test_with_no_iiif_mapping(self):
        """ Make sure that app initiates correctly when no IIIF mapping file is given"""
        with self.assertLogs() as cm:
            app = create_app(NoIIIFMappingConfig)
        self.assertIn(_('Der Viewer konnte nicht gestartet werden.'), [x.msg for x in cm.records])
        self.assertFalse(app.IIIFviewer, "No IIIF Viewer should be loaded with an invalid mapping file.")
        self.assertEqual(app.picture_file, "", "picture_file should be an empty string with invalid mapping file.")

    def test_with_no_iiif_server(self):
        """ Make sure that app initiates correctly when no IIIF server is given"""
        app = create_app(NoIIIFServerConfig)
        self.assertIsNone(app.IIIFserver, "IIIFserver value should be none if no IIIF Server is given.")


class TestIndividualRoutes(Formulae_Testing):
    def test_anonymous_user(self):
        """ Make sure that protected routes do not work with unauthorized users and that unprotected routes do

        """
        with self.client as c:
            c.get('/', follow_redirects=True)
            self.assertIn('main::index.html', [x[0].name for x in self.templates])
            c.get('/imprint', follow_redirects=True)
            self.assertIn('main::impressum.html', [x[0].name for x in self.templates])
            c.get('/bibliography', follow_redirects=True)
            self.assertIn('main::bibliography.html', [x[0].name for x in self.templates])
            c.get('/contact', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            c.get('/search/doc', follow_redirects=True)
            self.assertIn('search::documentation.html', [x[0].name for x in self.templates])
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertIn(_('Bitte loggen Sie sich ein, um Zugang zu erhalten.'), [x[0] for x in self.flashed_messages])
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            c.get('/auth/reset_password_request', follow_redirects=True)
            self.assertIn('auth::reset_password_request.html', [x[0].name for x in self.templates])
            c.get('/auth/register', follow_redirects=True)
            self.assertIn('auth::register.html', [x[0].name for x in self.templates])
            c.get('/collections', follow_redirects=True)
            self.assertIn('main::collection.html', [x[0].name for x in self.templates])
            c.get('/collections/formulae_collection', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            r = c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            self.assertIn('<p class=" no-copy">', r.get_data(as_text=True))
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertIn('main::salzburg_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/urn:cts:formulae:fu2', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/urn:cts:formulae:ko2', follow_redirects=True)
            self.assertIn(_('Um das Digitalisat dieser Handschrift zu sehen, besuchen Sie bitte gegebenenfalls die Homepage der Bibliothek.'),
                          [x[0] for x in self.flashed_messages])
            r = c.get('/collections/urn:cts:formulae:katalonien', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            data = self.get_context_variable('collections')
            self.assertEqual(data['members'], [])
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            rv = c.get('/collections/urn:cts:formulae:katalonien', follow_redirects=True)
            template, data = self.templates[0]
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            self.assertEqual(data['collections']['members'], [])
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:salzburg.hauthaler-a0001.lat001/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            # Check for backwards compatibility of URLs
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:salzburg.hauthaler-a0001.lat001/passage/1+first', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            c.get('/add_collections/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::collection.html', [x[0].name for x in self.templates])
            c.get('/add_collection/other_collection/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            c.get('/add_collection/urn:cts:formulae:katalonien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            data = self.get_context_variable('collections')
            self.assertEqual(data['members'], [])
            c.get('/add_collection/urn:cts:formulae:marmoutier_manceau/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            data = self.get_context_variable('collections')
            self.assertNotEqual(data['members'], [])
            c.get('/add_collection/formulae_collection/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/add_collection/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/add_collection/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/add_text/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertIn('main::lexicon_modal.html', [x[0].name for x in self.templates])
            c.get('/add_collection/lexicon_entries/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::elex_collection.html', [x[0].name for x in self.templates])
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::elex_collection.html', [x[0].name for x in self.templates])
            # An non-authenicated user who surfs to the login page should not be redirected
            c.get('/auth/login', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            # The following tests are to make sure that non-open texts are not available to non-project members
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('/corpus_m/urn:cts:formulae:marculf', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('/corpus_m/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertIn('main::sub_collection_mv.html', [x[0].name for x in self.templates])
            # Make sure the Salzburg collection is ordered correctly
            r = c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            p = re.compile('<h5>Notitia Arnonis: </h5>.+<h5>Codex Odalberti Vorrede: </h5>.+<h5>Codex Odalberti 1: </h5>',
                           re.DOTALL)
            self.assertRegex(r.get_data(as_text=True), p)
            r = c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn('text-section no-copy', r.get_data(as_text=True))
            r = c.get('/texts/urn:cts:formulae:andecavensis.form001.fu2/passage/all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn('text-section no-copy', r.get_data(as_text=True))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:marculf.form003.le1/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'), [x[0] for x in self.flashed_messages])
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertIn(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'), [x[0] for x in self.flashed_messages])
            c.get('/reading_format/rows', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.fu2/passage/1+all'})
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertEqual(session['reading_format'], 'rows')
            response = c.get('/reading_format/columns', follow_redirects=True, headers={"X-Requested-With": "XMLHttpRequest"})
            self.assertEqual(response.get_data(as_text=True), 'OK')
            self.assertEqual(session['reading_format'], 'columns')
            c.get('/lang/en', follow_redirects=True, headers={'Referer': url_for('InstanceNemo.r_bibliography')})
            self.assertIn('main::bibliography.html', [x[0].name for x in self.templates])
            self.assertEqual(session['locale'], 'en')
            response = c.get('/lang/en', follow_redirects=True, headers={"X-Requested-With": "XMLHttpRequest"})
            self.assertEqual(response.get_data(as_text=True), 'OK')
            # Navigating to the results page with no search args should redirect the user to the index
            c.get('/search/results', follow_redirects=True)
            self.assertIn('main::index.html', [x[0].name for x in self.templates])
            c.get('/viewer/manifest:urn:cts:formulae:andecavensis.form001.fu2?view=0&embedded=True', follow_redirects=True)
            self.assertIn('viewer::miradorviewer.html', [x[0].name for x in self.templates])
            r = c.get('/viewer/urn:cts:formulae:marculf.form003.lat001', follow_redirects=True)
            self.assertIn(_('Diese Formelsammlung ist noch nicht frei zugänglich.'), [x[0] for x in self.flashed_messages])
            self.assertIn('main::index.html', [x[0].name for x in self.templates])
            r = c.get('/pdf/urn:cts:formulae:andecavensis.form002.lat001', follow_redirects=True)
            self.assertRegex(r.get_data(), b'Encrypt \d+ 0 R', 'PDF should be encrypted.')
            c.get('/pdf/urn:cts:formulae:raetien.erhart0001.lat001', follow_redirects=True)
            self.assertIn(_('Das PDF für diesen Text ist nicht zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('manuscript_desc/fulda_d1', follow_redirects=True)
            self.assertIn('main::fulda_d1_desc.html', [x[0].name for x in self.templates])
            c.get('manuscript_desc/siglen', follow_redirects=True)
            self.assertIn('main::manuscript_siglen.html', [x[0].name for x in self.templates])
            c.get('accessibility_statement', follow_redirects=True)
            self.assertIn('main::accessibility_statement.html', [x[0].name for x in self.templates])
            c.get('/search/lemmata', follow_redirects=True)
            self.assertEqual(['goodbye', 'hello'], self.get_context_variable('lemmas'))
            self.assertEqual(['1', '8', '12', '45', 'iii', 'iv', 'v', 'xxviiii', 'xxx', 'xc', 'c', 'cd', 'd', 'cm', 'm'],
                             self.get_context_variable('numbers'))
            c.get('/search/advanced_search', follow_redirects=True)
            self.assertIn(('Angers', 'andecavensis', True),
                          self.get_context_variable('categories')['formulae_collection'])
            self.assertIn(('<b>Fulda</b>: Cod. dipl. Fuldensis', 'fulda_dronke', False),
                          self.get_context_variable('categories')['other_collection'])
            # Make sure session variables are correctly set from g
            attributes = ['previous_search',
                          'previous_search_args',
                          'previous_aggregations',
                          'highlighted_words']
            for a in attributes:
                setattr(g, a, 'some_value')
            c.get('/', follow_redirects=True)
            for a in attributes:
                self.assertEqual(session[a], 'some_value')

    def test_authorized_project_member(self):

        """ Make sure that all routes are open to project members"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            c.get('/', follow_redirects=True)
            self.assertIn('main::index.html', [x[0].name for x in self.templates])
            c.get('/imprint', follow_redirects=True)
            self.assertIn('main::impressum.html', [x[0].name for x in self.templates])
            c.get('/bibliography', follow_redirects=True)
            self.assertIn('main::bibliography.html', [x[0].name for x in self.templates])
            c.get('/contact', follow_redirects=True)
            self.assertIn('main::contact.html', [x[0].name for x in self.templates])
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            c.get('/collections', follow_redirects=True)
            self.assertIn('main::collection.html', [x[0].name for x in self.templates])
            c.get('/collections/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/formulae_collection', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            c.get('/collections/other_collection', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:katalonien', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:katalonien.vinyals_albanyamonestirpere', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertIn('main::salzburg_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:elexicon', follow_redirects=True)
            self.assertIn('main::elex_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:marculf', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus_m/urn:cts:formulae:marculf', follow_redirects=True)
            self.assertIn('main::sub_collection_mv.html', [x[0].name for x in self.templates])
            c.get('/corpus_m/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertIn('main::sub_collection_mv.html', [x[0].name for x in self.templates])
            c.get('/corpus_m/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertIn(_('Diese View ist nur für MARCULF und ANDECAVENSIS verfuegbar'), [x[0] for x in self.flashed_messages])
            c.get('/collections/urn:cts:formulae:fu2', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/urn:cts:formulae:ko2', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/urn:cts:formulae:katalonien', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            # Check for backwards compatibility of URLs
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+first', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            c.get('/add_collections/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::collection.html', [x[0].name for x in self.templates])
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertIn('main::lexicon_modal.html', [x[0].name for x in self.templates])
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::elex_collection.html', [x[0].name for x in self.templates])
            c.get('/add_text/urn:cts:formulae:katalonien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            # An authenicated user who surfs to the login page should be redirected to their user page
            c.get('/auth/login', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Sie sind schon eingeloggt.'), [x[0] for x in self.flashed_messages])
            # The following tests are to make sure that non-open texts are available to project members
            c.get('/add_collection/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/add_collection/urn:cts:formulae:katalonien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            data = self.get_context_variable('collections')
            self.assertNotEqual(data['members'], [])
            c.get('/add_collection/urn:cts:formulae:marmoutier_manceau/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            data = self.get_context_variable('collections')
            self.assertNotEqual(data['members'], [])
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            r = c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            re_sub_coll = re.compile(r'\[Edition\].+\[Deutsche Übersetzung\].+Transkription/Manuskriptbild', re.DOTALL)
            self.assertRegex(r.get_data(as_text=True), re_sub_coll)
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertNotIn('text-section no-copy', r.get_data(as_text=True))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.fu2/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertNotIn('text-section no-copy', r.get_data(as_text=True))
            c.get('/texts/urn:cts:formulae:andecavensis.computus.fu2+urn:cts:formulae:andecavensis.computus.lat001/passage/all+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            c.get('/texts/urn:cts:formulae:andecavensis.form000.lat001+urn:cts:formulae:andecavensis.form000.fu2/passage/all+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            r = c.get('/texts/urn:cts:formulae:marculf.form000.lat001+urn:cts:formulae:p3.105va106rb.lat001/passage/all+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn('Marculf Prolog', r.get_data(as_text=True))
            # make sure hasVersion metadata is correctly interpreted
            r = c.get('/texts/urn:cts:formulae:fulda_dronke.dronke0004a.lat001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn('Urkundenbuch des Klosters Fulda; Teil: Bd. 1., (Die Zeit der Äbte Sturmi und Baugulf) (Ed. Stengel) Nr. 15', r.get_data(as_text=True))
            r = c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn(r'<span class="choice"><span class="abbr">o.t.</span><span class="expan">other text</span></span>',
                          r.get_data(as_text=True), '<choice> elements should be correctly converted.')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/2+12', follow_redirects=True)
            self.assertIn('Angers 1 (lat), 12 wurde nicht gefunden. Der ganze Text wird angezeigt.', [x[0] for x in self.flashed_messages])
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            r = c.get('/texts/urn:cts:formulae:andecavensis.form001/passage/2', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn('Angers 1', r.get_data(as_text=True))
            # Make sure that a text that has no edition will throw an error
            r = c.get('/texts/urn:cts:formulae:andecavensis.form003/passage/1', follow_redirects=True)
            self.assertIn("errors::unknown_collection.html", [x[0].name for x in self.templates])
            self.assertIn('Angers 3.1' + _(' hat keine Edition.'), r.get_data(as_text=True))
            r = c.get('/viewer/urn:cts:formulae:andecavensis.form003', follow_redirects=True)
            self.assertIn("errors::unknown_collection.html", [x[0].name for x in self.templates])
            self.assertIn('Angers 3' + _(' hat keine Edition.'), r.get_data(as_text=True))
            # c.get('/viewer/urn:cts:formulae:andecavensis.form001.fu2', follow_redirects=True)
            # self.assertIn('viewer::miradorviewer.html', [x[0].name for x in self.templates])
            c.get('/texts/urn:cts:formulae:andecavensis.form002.lat001+manifest:urn:cts:formulae:andecavensis.form002.fu2/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            c.get('/texts/manifest:urn:cts:formulae:andecavensis.form003.deu001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            r = c.get('/texts/urn:cts:formulae:lorsch.gloeckner4233.lat001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            c_v = self.get_context_variable('objects')
            self.assertEqual(c_v[0]['objectId'], 'urn:cts:formulae:lorsch.gloeckner0002.lat001',
                             'A dead url should redirect to a live document.')
            c.get('/texts/urn:cts:formulae:andecavensis.form002.lat001+manifest:urn:cts:formulae:p12.65r65v.lat001/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            c.get('/texts/manifest:urn:cts:formulae:m4.60v61v.lat001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            c.get('/viewer/manifest:urn:cts:formulae:andecavensis.form001.fu2?view=0&embedded=True', follow_redirects=True)
            self.assertIn('viewer::miradorviewer.html', [x[0].name for x in self.templates])
            c.get('/viewer/urn:cts:formulae:andecavensis.form001?view=0&embedded=True', follow_redirects=True)
            self.assertIn('viewer::miradorviewer.html', [x[0].name for x in self.templates])
            r = c.get('/pdf/urn:cts:formulae:andecavensis.form002.lat001', follow_redirects=True)
            self.assertNotIn(b'Encrypt', r.get_data())
            self.assertIn('Angers 2 \\(lat\\) \\({}\\)'.format(date.today().isoformat()).encode(), r.get_data())
            r = c.get('/pdf/urn:cts:formulae:raetien.erhart0001.lat001', follow_redirects=True)
            self.assertIn('Urkundenlandschaft R\\344tien \\(Ed. Erhart/Kleindinst\\) Nr. 1 \\({}\\)'.format(date.today().isoformat()).encode(), r.get_data())
            self.assertNotIn(b'Encrypt', r.get_data())
            c.get('manuscript_desc/fulda_d1', follow_redirects=True)
            self.assertIn('main::fulda_d1_desc.html', [x[0].name for x in self.templates])
            # Ensure that the PDF search results progress checker returns the correct value
            r = c.get('/search/pdf_progress/1000')
            self.assertEqual(r.get_data(as_text=True), '0%',
                             'If the key does not exist in Redis, it should return "0%"')
            self.app.redis.setex('pdf_download_1000', 10, '10%')
            r = c.get('/search/pdf_progress/1000')
            self.assertEqual(r.get_data(as_text=True), '10%')
            self.app.redis.delete('pdf_download_1000')
            c.get('manuscript_desc/siglen', follow_redirects=True)
            self.assertIn('main::manuscript_siglen.html', [x[0].name for x in self.templates])
            c.get('accessibility_statement', follow_redirects=True)
            self.assertIn('main::accessibility_statement.html', [x[0].name for x in self.templates])
            c.get('/search/advanced_search', follow_redirects=True)
            d = self.get_context_variable('composition_places')
            self.assertEqual(d[1], 'Aachen', 'The correct places should be sent to the advanced search pages.')

    def test_authorized_normal_user(self):
        """ Make sure that all routes are open to normal users but that some texts are not available"""
        with self.client as c:
            c.post('/auth/login?next=/imprint', data=dict(username='not.project', password="some_other_password"),
                   follow_redirects=True)
            self.assertIn('main::impressum.html', [x[0].name for x in self.templates])
            c.get('/', follow_redirects=True)
            self.assertIn('main::index.html', [x[0].name for x in self.templates])
            c.get('/imprint', follow_redirects=True)
            self.assertIn('main::impressum.html', [x[0].name for x in self.templates])
            c.get('/bibliography', follow_redirects=True)
            self.assertIn('main::bibliography.html', [x[0].name for x in self.templates])
            c.get('/contact', follow_redirects=True)
            self.assertIn('main::contact.html', [x[0].name for x in self.templates])
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            c.get('/auth/reset_password_request', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Sie sind schon eingeloggt. Sie können Ihr Password hier ändern.'), [x[0] for x in self.flashed_messages])
            c.get('/auth/login', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Sie sind schon eingeloggt.'), [x[0] for x in self.flashed_messages])
            c.get('/auth/register', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Sie sind schon eingeloggt.'), [x[0] for x in self.flashed_messages])
            c.get('/collections', follow_redirects=True)
            self.assertIn('main::collection.html', [x[0].name for x in self.templates])
            c.get('/collections/formulae_collection', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/lexicon_entries', follow_redirects=True)
            self.assertIn('main::elex_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertIn('main::salzburg_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus/urn:cts:formulae:elexicon', follow_redirects=True)
            self.assertIn('main::elex_collection.html', [x[0].name for x in self.templates])
            c.get('/corpus_m/urn:cts:formulae:marculf', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('/collections/urn:cts:formulae:ko2', follow_redirects=True)
            self.assertIn(_('Um das Digitalisat dieser Handschrift zu sehen, besuchen Sie bitte gegebenenfalls die Homepage der Bibliothek.'), [x[0] for x in self.flashed_messages])
            c.get('/collections/urn:cts:formulae:katalonien', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('/add_collection/urn:cts:formulae:katalonien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            data = self.get_context_variable('collections')
            self.assertEqual(data['members'], [])
            c.get('/add_collection/urn:cts:formulae:marmoutier_manceau/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collections.html', [x[0].name for x in self.templates])
            data = self.get_context_variable('collections')
            self.assertNotEqual(data['members'], [])
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            # Check for backwards compatibility of URLs
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:salzburg.hauthaler-a0001.lat001/passage/1+first', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            c.get('/add_collections/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::collection.html', [x[0].name for x in self.templates])
            c.get('/add_text/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::sub_collection.html', [x[0].name for x in self.templates])
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertIn('main::lexicon_modal.html', [x[0].name for x in self.templates])
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn('main::elex_collection.html', [x[0].name for x in self.templates])
            # An authenicated user who surfs to the login page should be redirected to index
            c.get('/auth/login', follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Sie sind schon eingeloggt.'), [x[0] for x in self.flashed_messages])
            # The following tests are to make sure that non-open texts are not available to non-project members
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertIn(_('Diese Sammlung ist nicht öffentlich zugänglich.'), [x[0] for x in self.flashed_messages])
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertIn('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.', [x[0] for x in self.flashed_messages])
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.fu2/passage/1+all', follow_redirects=True)
            self.assertIn(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'), [x[0] for x in self.flashed_messages])
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertIn('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.', [x[0] for x in self.flashed_messages])
            c.get('/viewer/manifest:urn:cts:formulae:andecavensis.form001.fu2?view=0&embedded=True', follow_redirects=True)
            self.assertIn('viewer::miradorviewer.html', [x[0].name for x in self.templates])
            c.get('/viewer/urn:cts:formulae:marculf.form003.lat001', follow_redirects=True)
            self.assertIn(_('Diese Formelsammlung ist noch nicht frei zugänglich.'), [x[0] for x in self.flashed_messages])
            self.assertIn('main::index.html', [x[0].name for x in self.templates])
            r = c.get('/pdf/urn:cts:formulae:andecavensis.form002.lat001', follow_redirects=True)
            self.assertRegex(r.get_data(), b'Encrypt \d+ 0 R', 'PDF should be encrypted.')
            r = c.get('/pdf/urn:cts:formulae:fulda_stengel.stengel0015.lat001', follow_redirects=True)
            self.assertIn('\\(Ed. Stengel\\) Nr. 15 \\({}\\)'.format(date.today().isoformat()).encode(), r.get_data())
            self.assertNotIn(b'Encrypt', r.get_data())
            c.get('manuscript_desc/fulda_d1', follow_redirects=True)
            self.assertIn('main::fulda_d1_desc.html', [x[0].name for x in self.templates])
            c.get('manuscript_desc/siglen', follow_redirects=True)
            self.assertIn('main::manuscript_siglen.html', [x[0].name for x in self.templates])
            c.get('accessibility_statement', follow_redirects=True)
            self.assertIn('main::accessibility_statement.html', [x[0].name for x in self.templates])


    @patch("formulae.search.routes.advanced_query_index")
    def test_advanced_search_results(self, mock_search):
        """ Make sure that the correct search results are passed to the search results form"""
        params = dict(corpus='formulae%2Bchartae', year=600, month=1, day=31, year_start=600, month_start=12,
                      day_start=12, year_end=700, month_end=1, day_end=12)
        aggs = {"corpus": {"buckets":
                               {k: {'doc_count': 0} if k != '<b>Angers</b>: Angers' else
                               {k: {'doc_count': 2}} for k in TestES.AGGS_ALL_DOCS['corpus']['buckets']
                                }
                           }
                }
        mock_search.return_value = [[], 0, aggs, []]
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            response = c.get('/search/advanced_search?corpus=formulae&corpus=chartae&q=&year=600&month=1&day=31&'
                             'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                             'date_plus_minus=0&submit=Search')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))
            c.get('/search/advanced_search?corpus=formulae&corpus=chartae&q=&year=600&month=1&day=31&'
                  'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                  'date_plus_minus=0&submit=Search', follow_redirects=True)
            # Check g.corpora
            self.assertIn(('<b>St. Gallen</b>: St. Gallen', 'stgallen'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')
            c.get('/search/results?source=advanced&corpus=formulae&q=&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&search_id=1234&submit=Search')
            mock_search.assert_called_with(corpus=['formulae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, lemma_search='False', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10000, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=None, regest_q='', old_search=False, source='advanced',
                                           regest_field='regest', formulaic_parts='', proper_name='',
                                           forgeries='include', search_id="1234")
            self.assertEqual(self.get_context_variable('searched_lems'), [], 'When "q" is empty, there should be no searched lemmas.')
            c.get('/search/results?source=advanced&corpus=formulae&q=&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&special_days=Easter%20Tuesday'
                  '&search_id=1234&submit=Search')
            mock_search.assert_called_with(corpus=['formulae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, lemma_search='False', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10000, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=['Easter', 'Tuesday'], regest_q='', old_search=False,
                                           source='advanced', regest_field='regest', formulaic_parts='', proper_name='',
                                           forgeries='include', search_id="1234")
            c.get('/search/advanced_search?corpus=formulae&q=&fuzziness=0&slop=0&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&regest_q=&special_days=Easter%20Tuesday&search_id=1234'
                  '&submit=True', follow_redirects=True)
            mock_search.assert_called_with(corpus=['formulae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, lemma_search='False', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10000, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=['Easter', 'Tuesday'], regest_q='', old_search=False,
                                           source='advanced', regest_field='regest', formulaic_parts='', proper_name='',
                                           forgeries='include', search_id="1234")
            c.get('/search/advanced_search?corpus=formulae&q=&fuzziness=0&slop=0&lemma_search=y&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&regest_q=&special_days=Easter%20Tuesday&search_id=1234'
                  '&submit=True', follow_redirects=True)
            mock_search.assert_called_with(corpus=['formulae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, lemma_search='True', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10000, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=['Easter', 'Tuesday'], regest_q='', old_search=False,
                                           source='advanced', regest_field='regest', formulaic_parts='', proper_name='',
                                           forgeries='include', search_id="1234")
            c.get('/search/advanced_search?corpus=formulae&q=&fuzziness=0&slop=0&lemma_search=y&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&regest_q=&special_days=Easter%20Tuesday&search_id=1234&'
                  'formulaic_parts=Poenformel%20Stipulationsformel&submit=True', follow_redirects=True)
            mock_search.assert_called_with(corpus=['formulae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, lemma_search='True', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10000, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=['Easter', 'Tuesday'], regest_q='', old_search=False,
                                           source='advanced', regest_field='regest', proper_name='',
                                           search_id="1234",
                                           forgeries='include', formulaic_parts="Poenformel+Stipulationsformel")
            c.get('/search/results?source=advanced&corpus=formulae&q=&fuzziness=0&slop=0&lemma_search=y&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&regest_q=&special_days=Easter%20Tuesday&search_id=1234&'
                  'formulaic_parts=Poenformel%2BStipulationsformel&page=2&submit=True&per_page=10000', follow_redirects=True)
            mock_search.assert_called_with(corpus=['formulae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, lemma_search='y', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10000, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=['Easter', 'Tuesday'], regest_q='', old_search=False,
                                           source='advanced', regest_field='regest', proper_name='', search_id="1234",
                                           forgeries='include',
                                           formulaic_parts="Poenformel+Stipulationsformel")
            self.assertIn('search::search.html', [x[0].name for x in self.templates])
            # Check searched_lems return values
            c.get('/search/results?source=advanced&corpus=formulae&q=regnum&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&search_id=1234&submit=True')
            self.assertEqual(self.get_context_variable('searched_lems'), [{'regnum'}],
                                'When a query word matches a lemma, it should be returned.')
            with c.session_transaction() as session:
                session['highlighted_words'] = ['regnum']
            c.get('/search/results?source=advanced&corpus=formulae&q=re*num&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&search_id=1234&submit=True')
            self.assertEqual(self.get_context_variable('searched_lems'), [{'regnum'}],
                                'When a query pattern matches a lemma, it should be returned.')
            c.get('/search/results?source=advanced&corpus=formulae&q=word&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&search_id=1234&submit=True')
            self.assertEqual(self.get_context_variable('searched_lems'), [],
                                'When a query word does not match a lemma, "searched_lems" should be empty.')
            c.get('/search/results?source=advanced&corpus=formulae&q=regnum+domni+ad&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&search_id=1234&submit=True')
            self.assertEqual(self.get_context_variable('searched_lems'), [{'regnum'}, {'dominus'}, {'a', 'ad', 'ab'}],
                                'When all query words match a lemma, all should be returned.')
            c.get('/search/results?source=advanced&corpus=formulae&q=regnum+word+ad&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&search_id=1234&submit=True')
            self.assertEqual(self.get_context_variable('searched_lems'), [],
                                'When not all query words match a lemma, "searched_lems" should be empty.')
            # Check g.corpora
            self.assertIn(('<b>Angers</b>: Angers', 'andecavensis'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')
            # Test to make sure that a capitalized search term is converted to lowercase in advanced search
            params['q'] = 'regnum'
            params['corpus'] = 'chartae'
            params['special_days'] = 'Easter%2BTuesday'
            params['proper_name'] = 'personenname%2Bortsname'
            response = c.get('/search/advanced_search?corpus=chartae&q=Regnum&year=600&month=1&day=31&'
                             'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                             'date_plus_minus=0&special_days=Easter+Tuesday&proper_name=personenname%20ortsname&search_id=1234&submit=Search')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))
            c.get('/search/advanced_search?corpus=chartae&q=Regnum&year=600&month=1&day=31&'
                  'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                  'date_plus_minus=0&search_id=1234&submit=Search', follow_redirects=True)
            # Check g.corpora
            self.assertIn(('<b>St. Gallen</b>: St. Gallen', 'stgallen'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')

    @patch("formulae.search.routes.advanced_query_index")
    def test_simple_search_results(self, mock_search):
        """ Make sure that the correct search results are passed to the search results form"""
        params = dict(corpus='formulae%2Bchartae', q='regnum', sort='urn', source='simple')
        mock_search.return_value = [[], 0, {}, []]
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            response = c.get('/search/simple?corpus=formulae&corpus=chartae&q=Regnum&search_id=4321&simple_search_id=1234')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))
            c.get('/search/simple?corpus=formulae&corpus=chartae&q=Regnum&search_id=4321&simple_search_id=1234',
                  follow_redirects=True)
            mock_search.assert_called_with(corpus=['formulae', 'chartae'], date_plus_minus=0, day=0, day_end=0,
                                           day_start=0, lemma_search='False', fuzziness='0', slop='0', month=0, month_end=0,
                                           month_start=0, page=1, per_page=10000, q='regnum',
                                           in_order='False', year=0, year_end=0, year_start=0,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=None, regest_q=None, old_search=False,
                                           source='simple', regest_field='regest', proper_name='', search_id="1234",
                                           forgeries='include', formulaic_parts="")

    @patch("formulae.nemo.lem_highlight_to_text")
    def test_search_result_highlighting(self, mock_highlight):
        """ Make sure that highlighting of search results works correctly"""
        # Highlighting should cross boundary of parent nodes
        session['previous_search_args'] = {'q': 'Text that I want to search'}
        search_string = ['Text that I want to search']
        expected = search_string[0].split()
        obj_id = 'urn:cts:formulae:salzburg.hauthaler-a0001.lat001'
        xml = self.nemo.get_passage(objectId=obj_id, subreference='1')
        html_input = Markup(self.nemo.transform(xml, xml.export(Mimetypes.PYTHON.ETREE), obj_id))
        mock_highlight.return_value = [[{'sents': search_string, 'sentence_spans': [range(0, 6)]}], []]
        result = etree.fromstring(self.nemo.highlight_found_sents(html_input, [{'sents': search_string, 'sentence_spans': [range(0, 6)]}]))
        self.assertEqual(expected, [y for y in result.xpath('//span[@class="searched"]//text()')])
        # Should be able to deal with editorial punctuation in the text
        search_string = ['Text with special editorial signs in it']
        expected = ['Text', 'with', 'sp<e>cial', '[edi]torial', '[signs', 'in', 'i]t']
        obj_id = 'urn:cts:formulae:salzburg.hauthaler-a0001.lat001'
        xml = self.nemo.get_passage(objectId=obj_id, subreference='1')
        html_input = Markup(self.nemo.transform(xml, xml.export(Mimetypes.PYTHON.ETREE), obj_id))
        mock_highlight.return_value = ([{'sents': search_string, 'sentence_spans': [range(6, 13)]}], [])
        result = etree.fromstring(self.nemo.highlight_found_sents(html_input, [{'sents': search_string, 'sentence_spans': [range(6, 13)]}]))
        self.assertEqual(expected, [y for y in result.xpath('//span[@class="searched"]//text()')])
        # Make sure that results are also returned whether lemma or text, simple or advanced
        session['previous_search_args']['lemma_search'] = 'False'
        result = etree.fromstring(self.nemo.highlight_found_sents(html_input, [{'sents': search_string, 'sentence_spans': [range(6, 13)]}]))
        self.assertEqual(expected, [y for y in result.xpath('//span[@class="searched"]//text()')], 'Advanced with text should work.')
        session['previous_search_args']['lemma_search'] = 'True'
        result = etree.fromstring(self.nemo.highlight_found_sents(html_input, [{'sents': search_string, 'sentence_spans': [range(6, 13)]}]))
        self.assertEqual(expected, [y for y in result.xpath('//span[@class="searched"]//text()')], 'Advanced with lemmas should work.')
        session['previous_search_args'].pop('lemma_search', None)
        session['previous_search_args']['lemma_search'] = 'True'
        result = etree.fromstring(self.nemo.highlight_found_sents(html_input, [{'sents': search_string, 'sentence_spans': [range(6, 13)]}]))
        self.assertEqual(expected, [y for y in result.xpath('//span[@class="searched"]//text()')], 'Simple with lemmas should work.')
        session['previous_search_args'].pop('lemma_search', None)
        session['previous_search_args']['lemma_search'] = 'False'
        result = etree.fromstring(self.nemo.highlight_found_sents(html_input, [{'sents': search_string, 'sentence_spans': [range(6, 13)]}]))
        self.assertEqual(expected, [y for y in result.xpath('//span[@class="searched"]//text()')], 'Simple with text should work.')
        # Should return the same result when passed in the session variable to r_multipassage
        session['previous_search'] = [{'id': obj_id,
                                       'title': 'Salzburg A1',
                                       'sents': search_string,
                                       'sentence_spans': [range(6, 13)]}]
        passage_data = self.nemo.r_multipassage(obj_id, '1')
        result = etree.fromstring(passage_data['objects'][0]['text_passage'])
        self.assertEqual(expected, [y for y in result.xpath('//span[@class="searched"]//text()')])
        # Make sure that when no sentences are highlighted, the original HTML is returned
        mock_highlight.return_value = ([], [])
        result = self.nemo.highlight_found_sents(html_input, [])
        self.assertEqual(html_input, result)

    def test_highlight_charter_parts(self):
        """ Make sure that the parts of a charter are highlighted correctly when there is a hit in that part"""
        session['previous_search_args'] = {'formulaic_parts': 'Arenga+Invocatio'}
        results = [{'highlight': {'Invocatio': ["</small><strong>trinitatis</strong><small>"]}}]
        obj_id = "urn:cts:formulae:stgallen.wartmann0615.lat001"
        xml = self.nemo.get_passage(objectId=obj_id, subreference='1')
        html_input = Markup(self.nemo.transform(xml, xml.export(Mimetypes.PYTHON.ETREE), obj_id))
        html_output = self.nemo.highlight_found_sents(html_input, results)
        self.assertIn('<span function="Invocatio" title="Invocatio" class="searched">',
                      html_output)
        self.assertIn('class="w font-weight-bold">trinitatis</span>', html_output)

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, 'lem_highlight_to_text')
    def test_session_previous_results_set(self, mock_highlight, mock_search):
        """ Make sure that session['previous_results'] is set correctly"""
        test_args = OrderedDict([("corpus", "all"), ("lemma_search", "True"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ('regest_q', ''), ('regest_field', 'regest'),
                                 ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")])
        fake = FakeElasticsearch(TestES().build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for hit in resp['hits']['hits']:
            hit['highlight']['text'][0] = PRE_TAGS + hit['highlight']['text'][0] + POST_TAGS
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = TestES().highlight_side_effect
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            _, _, _, results = advanced_query_index(**test_args)
            session['previous_search'] = results
            self.assertEqual([x['id'] for x in results],
                             [hit['_id'] for hit in resp['hits']['hits']])
            updated_args = copy(test_args)
            updated_args['q'] = 'tex?'
            url = '/search/results?source=advanced&' + '&'.join(['{}={}'.format(x, y) for x, y in updated_args.items()])
            c.get(url)
            self.assertEqual(g.previous_search, [], 'Latest search results should be empty.')
            self.assertEqual(session['previous_search'], [], 'session["previous_search"] should also be reset.')
            c.get(url.replace('q=tex?', 'q=text') + '&old_search=True')
            self.assertEqual([], session['previous_search'],
                             "With old_search set to True, session['previous_search'] should not be changed.")
            c.get(url.replace('q=tex?', 'q=text') + '&old_search=False')
            self.assertEqual(results, session['previous_search'],
                             "With old_search set to FAlse, session['previous_search'] should be reset.")
            c.get(url.replace('q=tex?', 'q=soem') + '&old_search=True')
            self.assertEqual(results, session['previous_search'],
                             "With old_search set to True, session['previous_search'] should not be changed.")
            c.get('/auth/logout', follow_redirects=True)
            c.get(url.replace('q=tex?', 'q=soem') + '&old_search=False')
            self.assertEqual(g.previous_search, session['previous_search'],
                             'Value of g.previous_search should be transferred to session')
            self.assertEqual([x['id'] for x in session['previous_search']],
                             [hit['_id'] for hit in resp['hits']['hits']],
                             'Session should reflect whether a text can be shown or not.')

    def test_session_previous_result_unset(self):
        """ Make sure that session['previous_result'] is unset in the right circumstances"""
        test_urls = {'clearing': [('/', 'index should clear previous_search'),
                                  ('/corpus/urn:cts:formulae:salzburg', 'corpus should clear previous_search')],
                     'not_clearing': [('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/1',
                                       'text reading page should not clear previous_search'),
                                      ('/search/results?corpus=formulae%2Bchartae&q=regnum&source=simple',
                                       'search page should not clear previous search')]}
        for url, message in test_urls['clearing']:
            with self.app.test_request_context(url):
                session['previous_search'] = {'id': 'something', 'title': 'something else'}
                self.assertTrue('previous_search' in session, 'previous_search should be set')
                self.app.preprocess_request()
                self.assertFalse('previous_search' in session, message)
        for url, message in test_urls['not_clearing']:
            with self.app.test_request_context(url):
                session['previous_search'] = {'id': 'something', 'title': 'something else'}
                self.assertTrue('previous_search' in session, 'previous_search should be set')
                self.app.preprocess_request()
                self.assertTrue('previous_search' in session, message)

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, 'lem_highlight_to_text')
    def test_session_previous_search_args_set_corpora(self, mock_highlight, mock_search):
        """ Make sure that session['previous_search_args'] is set correctly with 'all' corpora"""
        search_url = "/search/results?fuzziness=0&day_start=&year=&date_plus_minus=0&q=regnum&year_end=&corpus=all&submit=True&lemma_search=y&year_start=&month_start=0&source=advanced&month=0&day=&in_order=False&exclusive_date_range=False&month_end=0&slop=0&day_end=&regest_q="
        previous_args = {'source': 'advanced', 'corpus': 'all', 'q': 'regnum', 'fuzziness': '0', 'slop': '0',
                         'in_order': 'False', 'year': '', 'month': '0', 'day': '', 'year_start': '', 'month_start': '0',
                         'day_start': '', 'year_end': '', 'month_end': '0', 'day_end': '', 'date_plus_minus': '0',
                         'exclusive_date_range': 'False', 'composition_place': '', 'submit': 'True', 'sort': 'urn',
                         'special_days': '', 'regest_q': '', 'regest_field': 'regest'}
        test_args = OrderedDict([("corpus", "all"), ("lemma_search", "True"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ('regest_q', ''), ('regest_field', 'regest'),
                                 ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")])
        fake = FakeElasticsearch(TestES().build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = TestES().highlight_side_effect
        with self.client as c:
            session['previous_search_args'] = previous_args
            c.get(search_url, follow_redirects=True)
            self.assertRegex(session['previous_search_args']['corpus'],
                             'andecavensis\+[\w\+]*raetien+[\w\+]*salzburg+[\w\+]*stgallen',
                             'Corpus "all" should be expanded to a string with all corpora.')
            c.get(search_url, follow_redirects=True)
            self.assertIn(('<b>St. Gallen</b>: St. Gallen', 'stgallen'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')
            for old_search_arg in ['&old_search=False', '&old_search=True']:
                c.get(search_url + old_search_arg, follow_redirects=True)
                self.assertIn(('<b>Angers</b>: Angers', 'andecavensis'), g.corpora, 'Angers should be in all.')
                self.assertIn(('<b>Lorsch</b>: Lorsch', 'lorsch'), g.corpora, 'Lorsch should be in all.')
                self.assertIn(('<b>Marculf</b>: Marculf', 'marculf'), g.corpora, 'Marculf should be in all.')
                c.get(search_url.replace('corpus=all', 'corpus=formulae') + old_search_arg, follow_redirects=True)
                self.assertIn(('<b>Angers</b>: Angers', 'andecavensis'), g.corpora, 'Angers should be in formulae.')
                self.assertNotIn(('<b>Lorsch</b>: Lorsch', 'lorsch'), g.corpora, 'Bünden should not be in formulae.')
                c.get(search_url.replace('corpus=all', 'corpus=chartae') + old_search_arg, follow_redirects=True)
                self.assertNotIn(('<b>Angers</b>: Angers', 'andecavensis'), g.corpora, 'Angers should not be in chartae.')
                self.assertIn(('<b>Lorsch</b>: Lorsch', 'lorsch'), g.corpora, 'Lorsch should be in chartae.')
                c.get(search_url.replace('corpus=all', 'corpus=marculf+lorsch') + old_search_arg, follow_redirects=True)
                self.assertNotIn(('<b>Angers</b>: Angers', 'andecavensis'), g.corpora, 'Angers should not in marculf+buenden.')
                self.assertIn(('<b>Lorsch</b>: Lorsch', 'lorsch'), g.corpora, 'Lorsch should be in marculf+lorsch.')
                self.assertIn(('<b>Marculf</b>: Marculf', 'marculf'), g.corpora, 'Marculf should be in marculf+lorsch.')

    @patch.object(Elasticsearch, "search")
    def test_flashed_search_form_errors(self, mock_search):
        """ Make sure that errors in the form will result in no search being done and a flashed message"""
        mock_search.return_value = {'hits': {'hits': ''}}
        with self.client as c:
            c.get('/search/advanced_search?year=1500&submit=y')
            self.assertIn('year: ' + _('Die Jahreszahl muss zwischen 500 und 1000 liegen'), [x[0] for x in self.flashed_messages])
            self.assertIn('search::advanced_search.html', [x[0].name for x in self.templates])
            c.get('/search/advanced_search?submit=y')
            self.assertIn(_('Bitte geben Sie Daten in mindestens einem Feld ein.'), [x[0] for x in self.flashed_messages])
            self.assertIn('search::advanced_search.html', [x[0].name for x in self.templates])

    @patch("formulae.search.routes.suggest_word_search")
    def test_word_search_suggester_route(self, mock_suggest):
        """ Make sure that the word search suggester route returns correctly formatted JSON"""
        results = ['ill', '', 'illa curiensis esset distructa et ', 'illa qui possit nobis prestare solatium ',
                   'illam audire desiderabilem „ euge ', 'illam divisionem quam bonae memoriae ',
                   'illam divisionem vel ordinationem ', 'illam indictionem ducatum tibi cedimus ',
                   'ille sicut illi semetipsum hiato terrae ', 'illi et mihi econtra donaretur et ']
        mock_suggest.return_value = results
        expected = dumps(results)
        r = self.client.get('/search/suggest/ill')
        self.assertEqual(expected, r.get_data(as_text=True))

    def test_bibliography_links(self):
        """ Make sure the bibliographical links in the notes work correctly"""
        expected = re.compile('<sup>1</sup>  <a data-content="[^"]*&lt;span class=&quot;surname&quot;&gt;Hegglin&lt;/span&gt;, TITLE')
        with self.client as c:
            response = c.get('/lexicon/urn:cts:formulae:elexicon.abbas.deu001', follow_redirects=True,
                             headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertRegex(response.get_data(as_text=True), expected)
            response = c.get('/texts/urn:cts:formulae:elexicon.abbas.deu001/passage/1', follow_redirects=True)
            self.assertRegex(response.get_data(as_text=True), expected)

    def test_cache_control_header_set(self):
        """ Make sure that the Cache-Control header is set correctly with each request"""
        with self.client as c:
            response = c.get('/assets/nemo/css/theme.min.css')
            self.assertEqual(response.cache_control['max-age'], '86400', 'static files should be cached')
            response = c.get('/', follow_redirects=True)
            self.assertEqual(response.cache_control['max-age'], str(self.app.config['CACHE_MAX_AGE']),
                             'normal pages should be cached according to the default rule.')
            self.assertNotIn('no-cache', response.cache_control,
                             'Normal pages should not have "no-cache" in their Cache-Control header.')
            response = c.get('/texts/urn:cts:formulae:andecavensis.form003.deu001/passage/1')
            self.assertIn('no-cache', response.cache_control, 'Reading pages should not be cached')
            response = c.get('/lang/de')
            self.assertIn('no-cache', response.cache_control,
                          'The response to changing the language should not be cached.')
            response = c.get('/auth/login')
            self.assertIn('no-cache', response.cache_control, 'The login page should not be cached.')

    def test_rendering_from_texts_without_notes_transformation(self):
        """ Make sure that the multipassage template is rendered correctly without a transformation of the notes"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            r = c.get('/texts/urn:cts:formulae:andecavensis.form003.deu001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn('id="header-urn-cts-formulae-andecavensis-form003-deu001"',
                          r.get_data(as_text=True), 'Note card should be rendered for a formula.')
            r = c.get('/texts/urn:cts:formulae:elexicon.abbas.deu001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertIn('id="header-urn-cts-formulae-elexicon-abbas-deu001"',
                          r.get_data(as_text=True), 'Note card should be rendered for elex.')
            r = c.get('/texts/manifest:urn:cts:formulae:andecavensis.form005.lat001/passage/1', follow_redirects=True)
            self.assertNotIn('id="header-urn-cts-formulae-andecavensis-form005-lat001"',
                             r.get_data(as_text=True), 'Note card should not be rendered for a formula in IIIF Viewer.')

        del self.app.config['nemo_app']._transform['notes']
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            r = c.get('/texts/urn:cts:formulae:andecavensis.form003.deu001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertNotIn('id="header-urn-cts-formulae-andecavensis-form003-deu001"',
                             r.get_data(as_text=True), 'No note card should be rendered for a formula.')
            r = c.get('/texts/urn:cts:formulae:elexicon.abbas.deu001/passage/1', follow_redirects=True)
            self.assertIn('main::multipassage.html', [x[0].name for x in self.templates])
            self.assertNotIn('id="header-urn-cts-formulae-elexicon-abbas-deu001"',
                             r.get_data(as_text=True), 'No note card should be rendered for elex.')

class TestFunctions(Formulae_Testing):
    def test_NemoFormulae_get_first_passage(self):
        """ Make sure that the first passage of a text is correctly returned"""
        passage = self.nemo.get_first_passage('urn:cts:formulae:elexicon.abbas.deu001')
        self.assertEqual(passage, '1')
        passage = self.nemo.get_first_passage('urn:cts:formulae:andecavensis.form001.lat001')
        self.assertEqual(passage, '2')

    def test_NemoFormulae_f_replace_indexed_item(self):
        """ Make sure that the replace_indexed_item filter works correctly"""
        old_list = [1, 2, 3, 5, 5, 6, 7]
        new_list = [1, 2, 3, 4, 5, 6, 7]
        test_list = self.nemo.f_replace_indexed_item(old_list, 3, 4)
        self.assertEqual(test_list, new_list)

    def test_NemoFormulae_get_locale(self):
        """ Make sure that the NemoFormulae.get_locale function returns the correct values"""
        with self.client as c:
            c.post('/lang/de')
            self.assertEqual(self.nemo.get_locale(), 'ger')
            c.post('/lang/fr')
            self.assertEqual(self.nemo.get_locale(), 'fre')
            c.post('/lang/en')
            self.assertEqual(self.nemo.get_locale(), 'eng')
            # The following should throw an UnknownLocaleError
            c.post('/lang/none')
            self.assertEqual(self.nemo.get_locale(), 'ger', 'An UnknownLocaleError should return German as the language')

    def test_r_passage_return_values(self):
        """ Make sure the correct values are returned by r_passage"""
        data = self.nemo.r_passage('urn:cts:formulae:elexicon.abbas.deu001', 'all', 'eng')
        self.assertEqual(data['isReferencedBy'][0], 'urn:cts:formulae:andecavensis.form007.lat001',
                         "texts that aren't in the corpus should return a simple string with the URN identifier")
        self.assertEqual(data['isReferencedBy'][1][1], ["uir illo <span class='elex-word'>abbate</span> uel reliquis",
                                                        "fuit ipsius <span class='elex-word'>abbati</span> uel quibus"],
                         "KWIC strings for the inrefs should be correctly split and marked-up")
        self.assertEqual(data['collections']['current']['citation'],
                         'Lößlein, Horst, "Abbas, abbatissa", in: Formulae-Litterae-Chartae. Neuedition der frühmittelalterlichen Formulae, Hamburg (2019-05-07), [URL: https://werkstatt.formulae.uni-hamburg.de/texts/urn:cts:formulae:elexicon.abbas.deu001/passage/all]',
                         'Citaion data should be retrieved correctly.')

    def test_corpus_mv(self):
        """ Make sure the correct values are returned by r_corpus_mv"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            data = self.nemo.r_corpus_mv('urn:cts:formulae:marculf')
            self.assertEqual(data['collections']['readable'],
                             {'editions': [{'edition_name': 'Edition',
                                           'full_edition_name': '',
                                           'links': [['urn:cts:formulae:marculf.form000',
                                                      'urn:cts:formulae:marculf.form003',
                                                      'urn:cts:formulae:marculf.2_capitula'],
                                                     ['urn:cts:formulae:marculf.form000.lat001',
                                                      'urn:cts:formulae:marculf.form003.lat001',
                                                      'urn:cts:formulae:marculf.2_capitula.lat001']],
                                           'name': 'lat001',
                                           'regesten': ['', '', ''],
                                           'titles': ['Marculf Prolog',
                                                      'Marculf I,3',
                                                      'Marculf II Capitula']}],
                             'transcriptions': [{'edition_name': 'Ko2',
                                                 'full_edition_name': 'Kopenhagen, Kongelige Bibliotek, '
                                                                      'Fabr. 84 [fol.69r-fol.70v]',
                                                 'links': [['urn:cts:formulae:marculf.form003'],
                                                           ['urn:cts:formulae:ko2.69r70v.lat001']],
                                                 'name': 'ko2',
                                                 'regesten': [''],
                                                 'titles': ['Marculf I,3']},
                                                {'edition_name': 'Le1',
                                                 'full_edition_name': 'Leiden BPL 114 [fol.109v-fol.110v]',
                                                 'links': [['urn:cts:formulae:marculf.form003'],
                                                           ['urn:cts:formulae:le1.109v110v.lat001']],
                                                 'name': 'le1',
                                                 'regesten': [''],
                                                 'titles': ['Marculf I,3']},
                                                {'edition_name': 'M4',
                                                 'full_edition_name': 'München BSB clm 4650 '
                                                                      '[fol.60v-fol.61v]',
                                                 'links': [['urn:cts:formulae:marculf.form003'],
                                                           ['urn:cts:formulae:m4.60v61v.lat001']],
                                                 'name': 'm4',
                                                 'regesten': [''],
                                                 'titles': ['Marculf I,3']},
                                                {'edition_name': 'P3',
                                                 'full_edition_name': 'Paris BNF 2123 '
                                                                      '[fol.105va-fol.106rb]',
                                                 'links': [['urn:cts:formulae:marculf.form000',
                                                            'urn:cts:formulae:marculf.form003'],
                                                           ['urn:cts:formulae:p3.105va106rb.lat001',
                                                            'urn:cts:formulae:p3.128vb129rb.lat001']],
                                                 'name': 'p3',
                                                 'regesten': ['', ''],
                                                 'titles': ['Marculf Prolog', 'Marculf I,3']},
                                                {'edition_name': 'P12',
                                                 'full_edition_name': 'Paris BNF 4627 [fol.65r-fol.65v]',
                                                 'links': [['urn:cts:formulae:marculf.form003'],
                                                           ['urn:cts:formulae:p12.65r65v.lat001']],
                                                 'name': 'p12',
                                                 'regesten': [''],
                                                 'titles': ['Marculf I,3']},
                                                {'edition_name': 'P16',
                                                 'full_edition_name': 'Paris BNF 10756 [fol.7r-fol.7v]',
                                                 'links': [['urn:cts:formulae:marculf.form003'],
                                                           ['urn:cts:formulae:p16.7r7v.lat001']],
                                                 'name': 'p16',
                                                 'regesten': [''],
                                                 'titles': ['Marculf I,3']}],
                             'translations': []})

    def test_corpus_mv_passau(self):
        """ Make sure the correct values are returned by r_corpus_mv"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            data = self.nemo.r_corpus_mv('urn:cts:formulae:stgallen')
            self.assertEqual(data['collections']['readable'], {
            'editions':[],
            'translations': [],
            'transcriptions': []
            })

    def test_r_corpus_return_values(self):
        """ Make sure that the r_corpus function reacts correctly to the different corpora"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            data = self.nemo.r_corpus('urn:cts:formulae:lorsch')
            self.assertEqual(data['collections']['readable']['0002']['name'], 'Nr. 1 (Reg. 2)',
                             'Lorsch works should be correctly named.')
            data = self.nemo.r_corpus('urn:cts:formulae:marculf')
            self.assertEqual(data['collections']['readable']['(Prolog)']['name'], _('(Prolog)'),
                             'Lorsch works should be correctly named.')
            data = self.nemo.r_corpus('urn:cts:formulae:elexicon')
            self.assertEqual(data['template'], "main::elex_collection.html", "Elexicon should use elex template")
            data = self.nemo.r_corpus('urn:cts:formulae:salzburg')
            self.assertEqual(data['template'], "main::salzburg_collection.html", "Salzburg should use salzburg template")

    def test_get_prev_next_text(self):
        """ Make sure that the previous text and next text in a corpus are correctly returned"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            data = self.nemo.r_multipassage('urn:cts:formulae:salzburg.hauthaler-a0001.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:salzburg.hauthaler-a-vorrede.lat001')
            self.assertEqual(data['objects'][0]['next_version'], None)
            data = self.nemo.r_multipassage('urn:cts:formulae:salzburg.hauthaler-a-vorrede.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:salzburg.hauthaler-bna1.lat001')
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:salzburg.hauthaler-a0001.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:salzburg.hauthaler-na.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], None)
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:salzburg.hauthaler-bn-intro.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:salzburg.hauthaler-bna1.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:salzburg.hauthaler-bn-intro.lat001')
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:salzburg.hauthaler-a-vorrede.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:salzburg.hauthaler-bn-intro.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:salzburg.hauthaler-na.lat001')
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:salzburg.hauthaler-bna1.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:stgallen.wartmann0615.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:stgallen.wartmann0001.lat001')
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:stgallen.wartmann0615.lat002')
            data = self.nemo.r_multipassage('urn:cts:formulae:andecavensis.form000.fu2', '1')
            self.assertEqual(data['objects'][0]['prev_version'], None)
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:andecavensis.form001.fu2')
            data = self.nemo.r_multipassage('urn:cts:formulae:andecavensis.form002.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:andecavensis.form001.lat001')
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:andecavensis.form004.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:andecavensis.form002.deu001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:andecavensis.form001.deu001')
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:andecavensis.form003.deu001')
            data = self.nemo.r_multipassage('urn:cts:formulae:katalonien.vinyals_amermonestirgenís_0002.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:katalonien.vinyals_amermonestirgenís_0001.lat001')
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:katalonien.vinyals_amermonestirgenís_0003.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:katalonien.vinyals_amermonestirgenís_0001.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], None)
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:katalonien.vinyals_amermonestirgenís_0002.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:katalonien.vinyals_amermonestirgenís_0003.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:katalonien.vinyals_amermonestirgenís_0002.lat001')
            self.assertEqual(data['objects'][0]['next_version'], None)
            data = self.nemo.r_multipassage('urn:cts:formulae:p3.105va106rb.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], None)
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:p3.128vb129rb.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:marculf.form000.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], None)
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:marculf.form003.lat001')
            data = self.nemo.r_multipassage('urn:cts:formulae:marculf.2_capitula.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:marculf.form003.lat001')
            self.assertEqual(data['objects'][0]['next_version'], None)
            data = self.nemo.r_multipassage('urn:cts:formulae:marmoutier_serfs.salmon0002.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], None)
            self.assertEqual(data['objects'][0]['next_version'], 'urn:cts:formulae:marmoutier_serfs.salmon0001app.lat001')

    def test_semantic(self):
        """ Make sure that the correct SEO-friendly strings are returned by semantic"""
        c = self.nemo.resolver.id_to_coll['urn:cts:formulae:raetien.erhart0001.lat001']
        p = self.nemo.resolver.id_to_coll['urn:cts:formulae:raetien.erhart0001']
        # Test without parent
        s = self.nemo.semantic(c)
        for ancestor in c.ancestors.values():
            if ancestor.get_label():
                self.assertIn(slugify(ancestor.get_label()), s)
        # Test with parent
        s = self.nemo.semantic(c, p)
        for ancestor in c.ancestors.values():
            if ancestor.get_label():
                self.assertIn(slugify(ancestor.get_label()), s)

    def test_sort_folia(self):
        """ Makes sure that the sort_folia function returns correct strings"""
        test_strings = {'urn:cts:formulae:p16.4v6r': '0004v-6r', 'urn:cts:formulae:m4.39r24r': '0039r-24r',
                        'urn:cts:formulae:p3.130va131rb': '0130va-131rb', 'urn:cts:formulae:fu2.148v': '0148v',
                        'urn:cts:formulae:p3.134vb': '0134vb'}
        for k, v in test_strings.items():
            par = re.sub(r'.*?(\d+[rvab]+)(\d+[rvab]+)?\Z', self.nemo.sort_folia, k)
            self.assertEqual(par, v, '{} does not equal {}'.format(par, v))

    def test_load_inflected_to_lem_mapping(self):
        """ Ensure that the json mapping file is correctly loaded."""
        self.assertEqual(self.nemo.inflected_to_lemma_mapping['domni'],
                         {'dominus'},
                         'Mapping files should have loaded correctly.')
        self.app.config['INFLECTED_LEM_JSONS'] = ["tests/test_data/formulae/inflected_to_lem_error.txt"]
        with patch.object(self.app.logger, 'warning') as mock:
            self.nemo.make_inflected_to_lem_mapping()
            mock.assert_called_with('tests/test_data/formulae/inflected_to_lem_error.txt is not a valid JSON file. Unable to load valid inflected to lemma mapping from it.')

    def test_load_lem_to_lem_mapping(self):
        """ Ensure that the json mapping file is correctly loaded."""
        self.assertEqual(self.nemo.lem_to_lem_mapping['gero'],
                         {'gerere', 'gesta', 'gestus', 'gerereve'},
                         'Mapping files should have loaded correctly.')
        self.app.config['LEM_TO_LEM_JSONS'] = ["tests/test_data/formulae/inflected_to_lem_error.txt"]
        with patch.object(self.app.logger, 'warning') as mock:
            self.nemo.make_lem_to_lem_mapping()
            mock.assert_called_with('tests/test_data/formulae/inflected_to_lem_error.txt is not a valid JSON file. Unable to load valid lemma to lemma mapping from it.')

    def test_load_comp_places_list(self):
        """ Ensure that the json file is correctly loaded."""
        self.assertEqual(self.nemo.comp_places[1],
                         "Aachen",
                         'Mapping files should have loaded correctly.')
        self.app.config['COMP_PLACES'] = ["tests/test_data/formulae/inflected_to_lem_error.txt"]
        with patch.object(self.app.logger, 'warning') as mock:
            self.nemo.make_comp_places_list()
            mock.assert_called_with('tests/test_data/formulae/inflected_to_lem_error.txt is not a valid JSON file. Unable to load valid composition place list from it.')

    def test_load_dead_urls_mapping(self):
        """ Ensure that the json mapping file is correctly loaded."""
        self.assertEqual(self.nemo.dead_urls['urn:cts:formulae:lorsch.gloeckner4233.lat001'],
                         "urn:cts:formulae:lorsch.gloeckner0002.lat001",
                         'Mapping files should have loaded correctly.')
        self.app.config['DEAD_URLS'] = ["tests/test_data/formulae/inflected_to_lem_error.txt"]
        with patch.object(self.app.logger, 'warning') as mock:
            self.nemo.make_dead_url_mapping()
            mock.assert_called_with('tests/test_data/formulae/inflected_to_lem_error.txt is not a valid JSON file. Unable to load valid dead url mapping from it.')

    # def test_load_term_vectors(self):
    #     """ Ensure that the json mapping file is correctly loaded."""
    #     self.assertEqual(self.nemo.term_vectors["urn:cts:formulae:buenden.meyer-marthaler0027.lat001"]["term_vectors"]["text"]["terms"]["a"]["term_freq"],
    #                      4,
    #                      'Mapping files should have loaded correctly.')
    #     self.app.config['TERM_VECTORS'] = "tests/test_data/formulae/inflected_to_lem_error.txt"
    #     with patch.object(self.app.logger, 'warning') as mock:
    #         self.nemo.make_termvectors()
    #         mock.assert_called_with('tests/test_data/formulae/inflected_to_lem_error.txt is not a valid JSON file. Unable to load valid term vector dictionary from it.')

class TestForms(Formulae_Testing):
    def test_validate_success_login_form(self):
        """ Ensure that correct data in form validates

        """
        form = LoginForm(username='not.project', password='some_other_password')
        self.assertTrue(form.validate())

    def test_validate_missing_user_name(self):
        """ Make sure that a missing user name is not validated"""
        form = LoginForm(username='', password='wrong_password')
        self.assertFalse(form.validate())

    def test_validate_missing_password(self):
        """ Make sure that a missing password is not validated"""
        form = LoginForm(username='username', password='')
        self.assertFalse(form.validate())

    def test_validate_success_language_change_form(self):
        """ Ensure that correct data in the Language Change form validates

        """
        form = LanguageChangeForm(new_locale='en')
        self.assertTrue(form.validate())

    def test_validate_incorrect_language_language_change_form(self):
        """ Ensure that inputting a language that is not supported in Language Change form does not validate

        """
        form = LanguageChangeForm(new_locale='ru')
        self.assertFalse(form.validate())

    def test_validate_success_change_password_form(self):
        """ Ensure that correct data in the Password Change form validates

        """
        form = PasswordChangeForm(old_password='old_one', password='new', password2='new')
        self.assertTrue(form.validate())

    def test_validate_invalid_change_password_form(self):
        """ Ensure that Password Change form does not validate when password and password2 do not match

        """
        form = PasswordChangeForm(old_password='old_one', password='new', password2='wrong')
        self.assertFalse(form.validate())

    def test_validate_success_change_email_form(self):
        """ Ensure that correct data in the Email Change form validates

        """
        form = EmailChangeForm(email='a_new_email@email.com', email2='a_new_email@email.com')
        self.assertTrue(form.validate())

    def test_validate_invalid_change_email_form(self):
        """ Ensure that Email Change form does not validate when emails don't match or one of them is invalid

        """
        form = EmailChangeForm(email='a_new_email@email.com', email2='a_different_email@email.com')
        self.assertFalse(form.validate(), "Should not validate when email addresses differ.")
        form = EmailChangeForm(email='an_invalid_email', email2='a_different_email@email.com')
        self.assertFalse(form.validate(), "Should not validate when the first email address is invalid.")
        form = EmailChangeForm(email='a_new_email@email.com', email2='some weird email')
        self.assertFalse(form.validate(), "Should not validate when the second email address is invalid.")

    def test_validate_success_password_reset_request_form(self):
        """ Ensure that the password reset request form validates with a valid email address"""
        form = ResetPasswordRequestForm(email='some@email.com')
        self.assertTrue(form.validate())

    def test_validate_invalid_password_reset_request_form(self):
        """ Ensure that the password reset request form does not validate with an invalid email address"""
        form = ResetPasswordRequestForm(email='some_email')
        self.assertFalse(form.validate())

    def test_validate_success_password_reset_form(self):
        """ Ensure that the password reset form validates when the 2 passwords match"""
        form = ResetPasswordForm(password='new', password2='new')
        self.assertTrue(form.validate())

    def test_validate_invalid_password_reset_form(self):
        """ Ensure that the password reset form does not validate when the 2 passwords do not match"""
        form = ResetPasswordForm(password='new', password2='wrong')
        self.assertFalse(form.validate())

    def test_validate_success_advanced_search_form(self):
        """ Ensure that a form with valid data validates"""
        form = AdvancedSearchForm(corpus=['all'], year=600, month="01", day=31, year_start=600, month_start='12',
                                  day_start=12, year_end=700, month_end="01", day_end=12, special_days=['Easter Tuesday'])
        self.assertTrue(form.validate(), "Errors: {}".format(form.errors))
        form = AdvancedSearchForm(q="regnum", slop=500)
        self.assertTrue(form.validate(), "Errors: {}".format(form.errors))
        form = AdvancedSearchForm(date_plus_minus=100)
        self.assertTrue(form.validate(), "Errors: {}".format(form.errors))

    def test_valid_data_simple_search_form(self):
        """ Ensure that the simple search form validates with valid data"""
        form = SearchForm(corpus=[], q='regnum')
        form.data['corpus'].append('formulae')
        form.validate()
        self.assertTrue(form.validate(), 'Simple search with "regnum" should validate')
        form.data['q'] = 're?num'
        form.validate()
        self.assertTrue(form.validate(), 'Simple search with "re?num" should validate')

    def test_invalid_corpus_simple_search_form(self):
        """ Ensure that the simple search form returns a ValidationError with no corpus"""
        form = SearchForm(corpus=[], q='regnum')
        form.data['corpus'].append('')
        self.assertFalse(form.validate(), 'Search with no corpus specified should not validate')
        # I need two choices here since locally it returns the default Error and on Travis it returns the custom message
        self.assertIn(str(form.corpus.errors[0]),
                      [_('Sie müssen mindestens eine Sammlung für die Suche auswählen (\"Formeln\" und/oder \"Urkunden\").'),
                       _("'' ist kein gültige Auswahl für dieses Feld.")])

    def test_invalid_query_simple_search_form(self):
        """ Ensure that the simple search form returns a ValidationError with no corpus"""
        form = SearchForm(corpus=['formulae'], q=None)
        self.assertFalse(form.validate(), 'Search with no query term specified should not validate')
        # I need two choices here since locally it returns the default Error and on Travis it returns the custom message
        self.assertIn(str(form.q.errors[0]),
                      [_('Dieses Feld wird benötigt.'),
                       _("'' ist kein gültige Auswahl für dieses Feld.")])

    def test_validate_invalid_advanced_search_form(self):
        """ Ensure that a form with invalid data does not validate"""
        # I removed this sub-test because, for some reason, it doesn't pass on Travis, even though it passes locally.
        # form = AdvancedSearchForm(corpus=['some corpus'])
        # self.assertFalse(form.validate(), "Invalid corpus choice should not validate")
        form = AdvancedSearchForm(year=200)
        self.assertFalse(form.validate(), "Invalid year choice should not validate")
        form = AdvancedSearchForm(month="weird")
        self.assertFalse(form.validate(), "Invalid month choice should not validate")
        form = AdvancedSearchForm(day=32)
        self.assertFalse(form.validate(), "Invalid day choice should not validate")
        form = AdvancedSearchForm(year_start=200)
        self.assertFalse(form.validate(), "Invalid year_start choice should not validate")
        form = AdvancedSearchForm(month_start="weird")
        self.assertFalse(form.validate(), "Invalid month_start choice should not validate")
        form = AdvancedSearchForm(day_start=32)
        self.assertFalse(form.validate(), "Invalid day_start choice should not validate")
        form = AdvancedSearchForm(year_end=200)
        self.assertFalse(form.validate(), "Invalid year_end choice should not validate")
        form = AdvancedSearchForm(month_end="weird")
        self.assertFalse(form.validate(), "Invalid month_end choice should not validate")
        form = AdvancedSearchForm(day_end=32)
        self.assertFalse(form.validate(), "Invalid day_end choice should not validate")
        form = AdvancedSearchForm(date_plus_minus=200)
        self.assertFalse(form.validate(), "Invalid date_plus_minus choice should not validate")

    def test_validate_valid_registration_form(self):
        """ Ensure that correct data for new user registration validates"""
        form = RegistrationForm(username='new.user', email='some@email.com', password='some_new_password',
                                password2='some_new_password', default_locale="de")
        self.assertTrue(form.validate())

    def test_validate_invalidate_existing_user_registration_form(self):
        """ Ensure that correct data for new user registration validates"""
        form = RegistrationForm(username="not.project", email="not.project@uni-hamburg.de", password='some_new_password',
                                password2='some_new_password', default_locale="de")
        with self.assertRaisesRegex(ValidationError, _('Bitte wählen Sie einen anderen Benutzername.')):
            form.validate_username(form.username)
        with self.assertRaisesRegex(ValidationError, _('Bitte wählen Sie eine andere Emailaddresse.')):
            form.validate_email(form.email)
        self.assertFalse(form.validate())


class TestAuth(Formulae_Testing):
    def test_correct_login(self):
        """ Ensure that login works with correct credentials"""
        # For some reason this test does not work on Travis but it works locally.
        if os.environ.get('TRAVIS') == 'true':
            return
        with self.client as c:
            rv = c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                        follow_redirects=True)
            self.assertEqual(rv.status_code, 200, 'Login should return 200 code')
            self.assertTrue(current_user.email == "project.member@uni-hamburg.de")
            self.assertTrue(current_user.is_active)
            self.assertTrue(current_user.is_authenticated)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])

    def test_incorrect_login(self):
        """ Ensure that login does not work with incorrect credentials"""
        with self.client as c:
            rv = c.post('/auth/login', data=dict(username='pirate.user', password="incorrect"),
                        follow_redirects=True)
            self.assertEqual(rv.status_code, 200, 'Login should return 200 code')
            self.assertIn(_('Benutzername oder Passwort ist ungültig'), [x[0] for x in self.flashed_messages])
            self.assertFalse(current_user.is_active)
            self.assertFalse(current_user.is_authenticated)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])

    def test_confirm_password_change_token(self):
        """ Confirm that a valid jwt token is created when a user requests a password change"""
        user = User.query.filter_by(username='project.member').first()
        token = user.get_reset_password_token()
        self.assertTrue(user.verify_reset_password_token(token))

    def test_confirm_invalid_password_change_token(self):
        """ Confirm that a valid jwt token created for one user does not work for another"""
        user = User.query.filter_by(username='project.member').first()
        user2 = User.query.filter_by(username='not.project').first()
        token = user.get_reset_password_token()
        self.assertFalse(user2 == user.verify_reset_password_token(token))

    def test_confirm_email_change_token(self):
        """ Confirm that a valid jwt token is created when a user requests an email change"""
        user = User.query.filter_by(username='project.member').first()
        token = user.get_reset_email_token('new_email@email.com')
        self.assertEqual(user, user.verify_reset_email_token(token)[0])
        self.assertEqual(user.email, user.verify_reset_email_token(token)[1])

    def test_confirm_invalid_email_change_token(self):
        """ Confirm that a valid jwt token created for one user does not work for another"""
        user = User.query.filter_by(username='project.member').first()
        user2 = User.query.filter_by(username='not.project').first()
        token = user.get_reset_email_token('new_email@email.com')
        self.assertNotEqual(user2, user.verify_reset_email_token(token)[0])
        self.assertNotEqual(user2.email, user.verify_reset_email_token(token)[1])

    def test_correct_registration(self):
        """ Ensure that new user registration works with correct credentials"""
        with self.client as c:
            rv = c.post('/auth/register', data=dict(username='new.user', email="email@email.com",
                                                    password="some_password", password2="some_password",
                                                    default_locale="de"),
                        follow_redirects=True)
            self.assertEqual(rv.status_code, 200, 'Login should return 200 code')
            self.assertIn(_('Sie sind nun registriert.'), [x[0] for x in self.flashed_messages])
            self.assertTrue(User.query.filter_by(username='new.user').first(), "It should have added new.user.")
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])

    def test_send_email_existing_user(self):
        """ Ensure that emails are constructed correctly"""
        with self.client as c:
            with mail.record_messages() as outbox:
                c.post('/auth/reset_password_request', data=dict(email="project.member@uni-hamburg.de"),
                       follow_redirects=True)
                self.assertEqual(len(outbox), 1, 'One email should be sent')
                self.assertEqual(outbox[0].recipients, ["project.member@uni-hamburg.de"],
                                 'The recipient email address should be correct.')
                self.assertEqual(outbox[0].subject, _('[Formulae - Litterae - Chartae] Passwort zurücksetzen'),
                                 'The Email should have the correct subject.')
                self.assertIn(_('Sehr geehrte(r)') + ' project.member', outbox[0].html,
                              'The email text should be addressed to the correct user.')
                self.assertEqual(outbox[0].sender, 'no-reply@example.com',
                                 'The email should come from the correct sender.')
                self.assertIn(_('Die Anweisung zum Zurücksetzen Ihres Passworts wurde Ihnen per E-mail zugeschickt'), [x[0] for x in self.flashed_messages])
                c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                       follow_redirects=True)
                c.post('/auth/user', data={'email': 'new_email@email.com', 'email2': 'new_email@email.com'},
                       follow_redirects=True)
                self.assertEqual(len(outbox), 2, 'There should now be a second email in the outbox.')
                self.assertEqual(outbox[1].recipients, ["new_email@email.com"],
                                 'The recipient email address should be correct.')
                self.assertEqual(outbox[1].subject, _('[Formulae - Litterae - Chartae] Emailadresse ändern'),
                                 'The Email should have the correct subject.')
                self.assertIn(_('Sehr geehrte(r)') + ' project.member', outbox[1].html,
                              'The email text should be addressed to the correct user.')
                self.assertEqual(outbox[1].sender, 'no-reply@example.com',
                                 'The email should come from the correct sender.')
                self.assertIn(_('Ein Link zur Bestätigung dieser Änderung wurde an Ihre neue Emailadresse zugeschickt'), [x[0] for x in self.flashed_messages])
                self.assertEqual(current_user.email, "project.member@uni-hamburg.de",
                                 "The email address should not be changed only by requesting the token.")

    def test_send_email_not_existing_user(self):
        """ Ensure that no email is sent to a non-registered email address"""
        with self.client as c:
            with mail.record_messages() as outbox:
                c.post('/auth/reset_password_request', data=dict(email="pirate.user@uni-hamburg.de"),
                       follow_redirects=True)
                self.assertEqual(len(outbox), 0, 'No email should be sent when the email is not in the database.')
                self.assertIn(_('Die Anweisung zum Zurücksetzen Ihres Passworts wurde Ihnen per E-mail zugeschickt'), [x[0] for x in self.flashed_messages])

    def test_reset_password_from_email_token(self):
        """ Make sure that a correct email token allows the user to reset their password while an incorrect one doesn't"""
        with self.client as c:
            user = User.query.filter_by(username='project.member').first()
            token = user.get_reset_password_token()
            # Make sure that the template renders correctly with correct token
            c.post(url_for('auth.r_reset_password', token=token, _external=True))
            self.assertIn('auth::reset_password.html', [x[0].name for x in self.templates])
            # Make sure the correct token allows the user to change their password
            c.post(url_for('auth.r_reset_password', token=token, _external=True),
                   data={'password': 'some_new_password', 'password2': 'some_new_password'})
            self.assertTrue(user.check_password('some_new_password'), 'User\'s password should be changed.')
            c.post(url_for('auth.r_reset_password', token='some_weird_token', _external=True),
                   data={'password': 'some_password', 'password2': 'some_password'}, follow_redirects=True)
            self.assertIn('main::index.html', [x[0].name for x in self.templates])
            self.assertTrue(user.check_password('some_new_password'), 'User\'s password should not have changed.')
            # Make sure that a logged in user who comes to this page with a token is redirected to their user page with a flashed message
            c.post('/auth/login', data=dict(username='project.member', password="some_new_password"),
                   follow_redirects=True)
            c.post(url_for('auth.r_reset_password', token=token, _external=True), follow_redirects=True)
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Sie sind schon eingeloggt. Sie können Ihr Password hier ändern.'), [x[0] for x in self.flashed_messages])
            self.assertEqual(repr(user), '<User project.member>')

    def test_reset_email_from_email_token(self):
        """ Make sure that a correct email token changes the user's email address while an incorrect one doesn't"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            user = User.query.filter_by(username='project.member').first()
            token = user.get_reset_email_token('another_new_email@email.com')
            self.assertEqual(user.email, "project.member@uni-hamburg.de",
                             "The email address should not be changed only by requesting the token.")
            # Make sure that the template renders correctly with correct token
            c.post(url_for('auth.r_reset_email', token=token, _external=True))
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            # Make sure the correct token allows the user to change their password
            self.assertEqual(user.email, 'another_new_email@email.com', 'User\'s email should be changed.')
            self.assertIn(_('Ihr Email wurde erfolgreich geändert. Sie lautet jetzt') + ' another_new_email@email.com.', [x[0] for x in self.flashed_messages])
            # Trying to use the same token twice should not work.
            c.post(url_for('auth.r_reset_email', token=token, _external=True))
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Ihre Emailaddresse wurde nicht geändert. Versuchen Sie es erneut.'), [x[0] for x in self.flashed_messages])
            # Using an invalid token should not work.
            c.post(url_for('auth.r_reset_email', token='some_weird_token', _external=True), follow_redirects=True)
            self.assertIn(_('Der Token ist nicht gültig. Versuchen Sie es erneut.'), [x[0] for x in self.flashed_messages])
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertEqual(user.email, 'another_new_email@email.com', 'User\'s email should not have changed.')

    def test_user_logout(self):
        """ Make sure that the user is correctly logged out and redirected"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            self.assertTrue(current_user.is_authenticated, 'User should be logged in.')
            c.get('/auth/logout', follow_redirects=True)
            self.assertFalse(current_user.is_authenticated, 'User should now be logged out.')
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])

    def test_user_change_prefs(self):
        """ Make sure that the user can change their language and password"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            self.assertEqual(current_user.default_locale, 'de', '"de" should be the default language.')
            c.post('/auth/user/project.member', data={'new_locale': "en"})
            self.assertEqual(current_user.default_locale, 'en', 'User language should have been changed to "en"')
            c.post('/auth/user/project.member', data={'old_password': 'some_password', 'password': 'some_new_password',
                                                      'password2': 'some_new_password'},
                   follow_redirects=True)
            self.assertTrue(User.query.filter_by(username='project.member').first().check_password('some_new_password'),
                            'User should have a new password: "some_new_password".')
            self.assertIn('auth::login.html', [x[0].name for x in self.templates])
            self.assertIn(_("Sie haben Ihr Passwort erfolgreich geändert."), [x[0] for x in self.flashed_messages])

    def test_user_change_prefs_incorrect(self):
        """ Make sure that a user who gives the false old password is not able to change their password"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            self.assertTrue(current_user.is_authenticated)
            c.post(url_for('auth.r_user', username='project.member'), data={'old_password': 'some_wrong_password',
                                                                            'password': 'some_new_password',
                                                                            'password2': 'some_new_password'},
                   follow_redirects=True)
            self.assertTrue(User.query.filter_by(username='project.member').first().check_password('some_password'),
                            'User\'s password should not have changed.')
            self.assertIn(_("Das ist nicht Ihr aktuelles Passwort."), [x[0] for x in self.flashed_messages])


class TestES(Formulae_Testing):

    TEST_ARGS = {'test_date_range_search_same_year': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''),
                                                                  ("fuzziness", "0"), ('in_order', 'False'),
                                                                  ("year", 0), ('slop', '0'), ("month", 0),
                                                                  ("day", 0), ("year_start", 814),
                                                                  ("month_start", 10), ("day_start", 29),
                                                                  ("year_end", 814), ("month_end", 11),
                                                                  ("day_end", 20), ('date_plus_minus', 0),
                                                                  ('exclusive_date_range', 'False'),
                                                                  ("composition_place", ''), ('sort', 'urn'),
                                                                  ('special_days', ''), ("regest_q", ''),
                                                                  ("regest_field", "regest"), ("formulaic_parts", ""),
                                                                  ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_same_month': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 10), ("year_end", 800), ("month_end", 10),
                                 ("day_end", 29), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_different_year': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 10), ("year_end", 801), ("month_end", 10),
                                 ("day_end", 29), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_only_year': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 810), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_only_year_and_month_same_year': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 800), ("month_end", 11),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_only_year_and_month_different_year': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 801), ("month_end", 11),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_only_start_year': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_only_end_year': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 801), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_only_start_year_and_month': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_range_search_only_end_year_and_month': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 801), ("month_end", 10),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_normal_date_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 10), ("day", 9), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_normal_date_only_year_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_date_plus_minus_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 10), ("day", 9), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 10), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_exclusive_date_range_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 10), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 10), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_exclusive_date_range_search_only_year': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 0), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_exclusive_date_range_search_same_month_and_day': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 800), ("month_start", 12), ("day_start", 25), ("year_end", 820),
                                 ("month_end", 12), ("day_end", 25), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multi_corpus_search': OrderedDict([("corpus", "andecavensis%2Bmondsee"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', "0"), ("month", 0), ("day", 0),
                                 ("year_start", 814), ("month_start", 10), ("day_start", 29), ("year_end", 814),
                                 ("month_end", 11), ("day_end", 20), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multiword_wildcard_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", 'regnum+dom*'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_lemma_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "True"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_regest_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'tausch'),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_regest_and_word_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'schenk*'),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_regest_advanced_search_with_wildcard': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'tau*'),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multiword_lemma_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "True"), ("q", 'vir+venerabilis'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_v_to_u_multiword': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", 'wolfhart+cvm'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_v_to_u_single_word': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", 'novalium'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_single_word_highlighting': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", 'pettonis'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multi_word_highlighting': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", 'scripsi+et+suscripsi'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_single_lemma_highlighting': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multi_lemma_highlighting': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", 'regnum+domni'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_lemma_advanced_search_with_wildcard': OrderedDict([("corpus", "all"), ("lemma_search", "True"), ("q", 'venerabili?'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_composition_place_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", 'Basel-Augst'),
                                 ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_suggest_composition_places': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 10), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 10), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_suggest_word_search_completion': OrderedDict([("corpus", "buenden"), ("lemma_search", "autocomplete"), ("q", 'scrips'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'y'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_suggest_regest_word_search_completion': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'y'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'sche'),
                                 ("regest_field", "autocomplete_regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_regest_word_search_highlighting': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'y'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'schenkt'),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_suggest_word_search_completion_no_qSource': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", 'illam'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'y'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'tau'),
                                 ("regest_field", "autocomplete_regest"), ("formulaic_parts", ""), ("proper_name", ""), ('qSource', '')]),
                 'test_save_requests': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", 'Basel-Augst'),
                                 ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_specific_day_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', 'Easter'), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multiple_specific_day_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', 'Easter+Saturday'), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_download_search_results': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'schenk*'),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_no_corpus_given': OrderedDict([("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 801), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_mapped_lemma_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "True"), ("q", 'gero'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_mapped_multiword_lemma_advanced_search': OrderedDict([("corpus", "all"), ("lemma_search", "True"), ("q", 'facio+gero'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_proper_name_search': OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", "personenname"), ("forgeries", "include")]),
                 'test_single_word_fuzzy_highlighting': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", 'pettone'), ("fuzziness", "AUTO"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multi_word_fuzzy_highlighting': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", 'regnante+pettone'), ("fuzziness", "AUTO"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multi_word_fuzzy_highlighting_with_wildcard': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"), ("q", 'scripsi+et+suscr*'), ("fuzziness", "AUTO"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_multi_word_highlighting_repeated_words': OrderedDict([("corpus", "buenden"), ("lemma_search", "False"),
                                 ("q", 'signum+uuiliarentis+testes+signum+crespionis+testes'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ("formulaic_parts", ""), ("proper_name", ""), ("forgeries", "include")]),
                 'test_single_charter_part_search': OrderedDict([("corpus", "mondsee"),
                                                                 ("lemma_search", "False"),
                                                                 ("q", 'tempore'),
                                                                 ("fuzziness", "0"),
                                                                 ("in_order", "False"),
                                                                 ("year", 0),
                                                                 ("slop", "0"),
                                                                 ("month", 0),
                                                                 ("day", 0),
                                                                 ("year_start", 0),
                                                                 ("month_start", 0),
                                                                 ("day_start", 0),
                                                                 ("year_end", 0),
                                                                 ("month_end", 0),
                                                                 ("day_end", 0),
                                                                 ('date_plus_minus', 0),
                                                                 ('exclusive_date_range', 'False'),
                                                                 ("composition_place", ''),
                                                                 ('sort', 'urn'),
                                                                 ('special_days', ''),
                                                                 ("regest_q", ''),
                                                                 ("regest_field", "regest"),
                                                                 ("formulaic_parts", "Stipulationsformel"),
                                                                 ("proper_name", ""), ("forgeries", "include")]),
                 'test_single_charter_part_search_with_wildcard': OrderedDict([("corpus", "mondsee"),
                                                                 ("lemma_search", "False"),
                                                                 ("q", 'temp?re'),
                                                                 ("fuzziness", "0"),
                                                                 ("in_order", "False"),
                                                                 ("year", 0),
                                                                 ("slop", "0"),
                                                                 ("month", 0),
                                                                 ("day", 0),
                                                                 ("year_start", 0),
                                                                 ("month_start", 0),
                                                                 ("day_start", 0),
                                                                 ("year_end", 0),
                                                                 ("month_end", 0),
                                                                 ("day_end", 0),
                                                                 ('date_plus_minus', 0),
                                                                 ('exclusive_date_range', 'False'),
                                                                 ("composition_place", ''),
                                                                 ('sort', 'urn'),
                                                                 ('special_days', ''),
                                                                 ("regest_q", ''),
                                                                 ("regest_field", "regest"),
                                                                               ("formulaic_parts", "Stipulationsformel"),
                                                                               ("proper_name", ""), ("forgeries", "include")]),
                 'test_single_charter_part_search_with_wildcard_v_u': OrderedDict([("corpus", "mondsee"),
                                                                 ("lemma_search", "False"),
                                                                 ("q", 'christ*+vener?bili'),
                                                                 ("fuzziness", "0"),
                                                                 ("in_order", "False"),
                                                                 ("year", 0),
                                                                 ("slop", "0"),
                                                                 ("month", 0),
                                                                 ("day", 0),
                                                                 ("year_start", 0),
                                                                 ("month_start", 0),
                                                                 ("day_start", 0),
                                                                 ("year_end", 0),
                                                                 ("month_end", 0),
                                                                 ("day_end", 0),
                                                                 ('date_plus_minus', 0),
                                                                 ('exclusive_date_range', 'False'),
                                                                 ("composition_place", ''),
                                                                 ('sort', 'urn'),
                                                                 ('special_days', ''),
                                                                 ("regest_q", ''),
                                                                 ("regest_field", "regest"),
                                                                                   ("formulaic_parts", "Narratio"),
                                                                                   ("proper_name", ""), ("forgeries", "include")]),
                 'test_multi_charter_part_search': OrderedDict([("corpus", "mondsee"),
                                                                ("lemma_search", "False"),
                                                                ("q", 'christi'),
                                                                ("fuzziness", "0"),
                                                                ("in_order", "False"),
                                                                ("year", 0),
                                                                ("slop", "0"),
                                                                ("month", 0),
                                                                ("day", 0),
                                                                ("year_start", 0),
                                                                ("month_start", 0),
                                                                ("day_start", 0),
                                                                ("year_end", 0),
                                                                ("month_end", 0),
                                                                ("day_end", 0),
                                                                ('date_plus_minus', 0),
                                                                ('exclusive_date_range', 'False'),
                                                                ("composition_place", ''),
                                                                ('sort', 'urn'),
                                                                ('special_days', ''),
                                                                ("regest_q", ''),
                                                                ("regest_field", "regest"),
                                                                ("formulaic_parts", "Poenformel%2BStipulationsformel"),
                                                                ("proper_name", ""), ("forgeries", "include")]),
                 'test_charter_part_search_no_q': OrderedDict([("corpus", "mondsee"),
                                                               ("lemma_search", "False"),
                                                               ("q", ''),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                               ("formulaic_parts", "Poenformel%2BStipulationsformel"),
                                                               ("proper_name", ""), ("forgeries", "include")]),
                 'test_fuzzy_charter_part_search': OrderedDict([("corpus", "mondsee"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'in+loco+qui+nuncupatur'),
                                                               ("fuzziness", "AUTO"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                ("formulaic_parts", "Narratio"),
                                                                ("proper_name", ""), ("forgeries", "include")]),
                 'test_fuzzy_v_to_u_search': OrderedDict([("corpus", "mondsee"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'in+loco+qui+nuncupatur'),
                                                               ("fuzziness", "AUTO"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                          ("formulaic_parts", ""),
                                                          ("proper_name", ""), ("forgeries", "include")]),
                 'test_single_letter_highlighting_one_word': OrderedDict([("corpus", "buenden"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'a'),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                          ("formulaic_parts", ""),
                                                                          ("proper_name", ""), ("forgeries", "include")]),
                 'test_single_letter_highlighting_multiword': OrderedDict([("corpus", "buenden"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'daumerii+a'),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                           ("formulaic_parts", ""),
                                                                           ("proper_name", ""), ("forgeries", "include")]),
                 'test_forgery_exclude': OrderedDict([("corpus", "merowinger1"),
                                                               ("lemma_search", "False"),
                                                               ("q", ''),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                           ("formulaic_parts", ""),
                                                                           ("proper_name", ""),
                                                      ("forgeries", "exclude")]),
                 'test_forgery_only': OrderedDict([("corpus", "merowinger1"),
                                                               ("lemma_search", "False"),
                                                               ("q", ''),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                           ("formulaic_parts", ""),
                                                                           ("proper_name", ""),
                                                      ("forgeries", "only")]),
                 'test_multiword_proper_name_partial_match': OrderedDict([("corpus", "all"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'habraam+usque'),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                           ("formulaic_parts", ""),
                                                                           ("proper_name", "personenname"),
                                                      ("forgeries", "include")]),
                 'test_multiword_proper_name_no_match': OrderedDict([("corpus", "all"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'regnum+domni'),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                           ("formulaic_parts", ""),
                                                                           ("proper_name", "personenname"),
                                                      ("forgeries", "include")]),
                 'test_single_word_proper_name_no_match': OrderedDict([("corpus", "all"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'regnum'),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                           ("formulaic_parts", ""),
                                                                           ("proper_name", "personenname"),
                                                      ("forgeries", "include")]),
                 'test_single_word_proper_name_match_text': OrderedDict([("corpus", "all"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'adam'),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                           ("formulaic_parts", ""),
                                                                           ("proper_name", "personenname"),
                                                      ("forgeries", "include")]),
                 'test_multiword_proper_name_match_text': OrderedDict([("corpus", "all"),
                                                               ("lemma_search", "False"),
                                                               ("q", 'chlodoveo+chlothoario'),
                                                               ("fuzziness", "0"),
                                                               ("in_order", "False"),
                                                               ("year", 0),
                                                               ("slop", "0"),
                                                               ("month", 0),
                                                               ("day", 0),
                                                               ("year_start", 0),
                                                               ("month_start", 0),
                                                               ("day_start", 0),
                                                               ("year_end", 0),
                                                               ("month_end", 0),
                                                               ("day_end", 0),
                                                               ('date_plus_minus', 0),
                                                               ('exclusive_date_range', 'False'),
                                                               ("composition_place", ''),
                                                               ('sort', 'urn'),
                                                               ('special_days', ''),
                                                               ("regest_q", ''),
                                                               ("regest_field", "regest"),
                                                                           ("formulaic_parts", ""),
                                                                           ("proper_name", "personenname"),
                                                      ("forgeries", "include")])
                 }

    MOCK_VECTOR_RETURN_VALUE = {'_index': 'andecavensis_v1',
                                '_type': 'andecavensis',
                                '_id': 'urn:cts:formulae:andecavensis.form001.lat001',
                                '_version': 1,
                                'found': True,
                                'took': 0,
                                'term_vectors': {'text': {'terms':
                                                              {'regnum': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                      'start_offset': 0,
                                                                                                      'end_offset': 3}]},
                                                               'domni': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                     'start_offset': 5,
                                                                                                     'end_offset': 8}]},
                                                               'text': {'term_freq': 1, 'tokens': [{'position': 2,
                                                                                                    'start_offset': 10,
                                                                                                    'end_offset': 13},
                                                                                                   {'position': 3,
                                                                                                    'start_offset': 10,
                                                                                                    'end_offset': 13}]},
                                                               'gerus': {'term_freq': 1, 'tokens': [{'position': 4,
                                                                                                    'start_offset': 10,
                                                                                                    'end_offset': 13}]},
                                                               'geros': {'term_freq': 1, 'tokens': [{'position': 5,
                                                                                                    'start_offset': 10,
                                                                                                    'end_offset': 13}]},
                                                               'chlodoveo': {'term_freq': 1, 'tokens': [{'position': 6,
                                                                                                     'start_offset': 10,
                                                                                                     'end_offset': 13}]},
                                                               'chlothoario': {'term_freq': 1, 'tokens': [{'position': 7,
                                                                                                     'start_offset': 10,
                                                                                                     'end_offset': 13}]},
                                                               'adam': {'term_freq': 1, 'tokens': [{'position': 8,
                                                                                                     'start_offset': 10,
                                                                                                     'end_offset': 13}]},
                                                               'habraam': {'term_freq': 1, 'tokens': [{'position': 9,
                                                                                                     'start_offset': 10,
                                                                                                     'end_offset': 13}]},
                                                               'usque': {'term_freq': 1, 'tokens': [{'position': 10,
                                                                                                     'start_offset': 10,
                                                                                                     'end_offset': 13}]},
                                                               'facus': {'term_freq': 1, 'tokens': [{'position': 11,
                                                                                                     'start_offset': 10,
                                                                                                     'end_offset': 13}]},
                                                               'geribus': {'term_freq': 1, 'tokens': [{'position': 12,
                                                                                                     'start_offset': 10,
                                                                                                     'end_offset': 13}]}
                                                               }
                                                          },
                                                 'lemmas': {'terms':
                                                                {'vir': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                     'start_offset': 0,
                                                                                                     'end_offset': 3}]},
                                                                 'venerabilis': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                             'start_offset': 5,
                                                                                                             'end_offset': 8}]},
                                                                 'regnum': {'term_freq': 1, 'tokens': [{'position': 2,
                                                                                                        'start_offset': 10,
                                                                                                        'end_offset': 13}]},
                                                                 'text': {'term_freq': 1, 'tokens': [{'position': 3,
                                                                                                      'start_offset': 10,
                                                                                                      'end_offset': 13}]},
                                                                 'gerere': {'term_freq': 1, 'tokens': [{'position': 4,
                                                                                                        'start_offset': 14,
                                                                                                        'end_offset': 19}]},
                                                                 'gesta': {'term_freq': 1, 'tokens': [{'position': 5,
                                                                                                       'start_offset': 20,
                                                                                                       'end_offset': 24},
                                                                                                      {'position': 12,
                                                                                                       'start_offset': 20,
                                                                                                       'end_offset': 24}]},
                                                                 'personenname': {'term_freq': 4, 'tokens': [{'position': 6,
                                                                                                              'start_offset': 10,
                                                                                                              'end_offset': 13},
                                                                                                             {'position': 7,
                                                                                                              'start_offset': 10,
                                                                                                              'end_offset': 13},
                                                                                                             {'position': 8,
                                                                                                              'start_offset': 10,
                                                                                                              'end_offset': 13},
                                                                                                             {'position': 9,
                                                                                                              'start_offset': 10,
                                                                                                              'end_offset': 13}]},
                                                                 'usque': {'term_freq': 1, 'tokens': [{'position': 10,
                                                                                                       'start_offset': 10,
                                                                                                       'end_offset': 13}]},
                                                                 'facere': {'term_freq': 1, 'tokens': [{'position': 11,
                                                                                                       'start_offset': 10,
                                                                                                       'end_offset': 13}]}
                                                                 }
                                                            }
                                                 }}

    SEARCH_FILTERS_CORPORA = {'Angers': {'match': {'collection': 'andecavensis'}},
                              "Archives d’Anjou": {'match': {'collection': 'anjou_archives'}},
                              "Chroniques des comtes d’Anjou": {'match': {'collection': 'anjou_comtes_chroniques'}},
                              'Arnulfinger': {'match': {'collection': 'arnulfinger'}},
                              'Auvergne': {'match': {'collection': 'auvergne'}},
                              'Bünden': {'match': {'collection': 'buenden'}},
                              'Chartae Latinae X': {'match': {'collection': 'chartae_latinae_x'}},
                              'Chartae Latinae XI': {'match': {'collection': 'chartae_latinae_xi'}},
                              'Chartae Latinae XII': {'match': {'collection': 'chartae_latinae_xii'}},
                              'Chartae Latinae XLVI': {'match': {'collection': 'chartae_latinae_xlvi'}},
                              'Echternach': {'match': {'collection': 'echternach'}},
                              'Eudes': {'match': {'collection': 'eudes'}},
                              'Freising': {'match': {'collection': 'freising'}},
                              'Fulda (Dronke)': {'match': {'collection': 'fulda_dronke'}},
                              'Fulda (Stengel)': {'match': {'collection': 'fulda_stengel'}},
                              'Gorze': {'match': {'collection': 'gorze'}},
                              'Hersfeld': {'match': {'collection': 'hersfeld'}},
                              'Katalonien': {'match': {'collection': 'katalonien'}},
                              'Codice Diplomatico Longobardo': {'match': {'collection': 'langobardisch'}},
                              'Lorsch': {'match': {'collection': 'lorsch'}},
                              'Luzern': {'match': {'collection': 'luzern'}},
                              'Marculf': {'match': {'collection': 'marculf'}},
                              "Accensement d'une vigne de Marmoutier": {'match': {'collection': 'marmoutier_barthelemy'}},
                              'Marmoutier - Dunois': {'match': {'collection': 'marmoutier_dunois'}},
                              'Marmoutier - Fougères': {'match': {'collection': 'marmoutier_fougères'}},
                              'Un acte faux de Marmoutier': {'match': {'collection': 'marmoutier_laurain'}},
                              'Marmoutier - Trois actes faux ou interpolés': {'match': {'collection': 'marmoutier_leveque'}},
                              'Marmoutier - Manceau': {'match': {'collection': 'marmoutier_manceau'}},
                              'Marmoutier - Pour le perche': {'match': {'collection': 'marmoutier_pour_le_perche'}},
                              'Marmoutier - Serfs': {'match': {'collection': 'marmoutier_serfs'}},
                              'Marmoutier - Vendômois': {'match': {'collection': 'marmoutier_vendomois'}},
                              'Marmoutier - Vendômois, Appendix': {'match': {'collection': 'marmoutier_vendomois_appendix'}},
                              'Merowinger': {'match': {'collection': 'merowinger1'}},
                              'Mittelrheinisch': {'match': {'collection': 'mittelrheinisch'}},
                              'Mondsee': {'match': {'collection': 'mondsee'}},
                              'Papsturkunden Frankreich': {'match': {'collection': 'papsturkunden_frankreich'}},
                              'Passau': {'match': {'collection': 'passau'}},
                              'Rätien': {'match': {'collection': 'raetien'}},
                              'Cartulaire de Redon': {'match': {'collection': 'redon'}},
                              'Regensburg': {'match': {'collection': 'regensburg'}},
                              'Rheinisch': {'match': {'collection': 'rheinisch'}},
                              'Saint-Bénigne de Dijon': {'match': {'collection': 'saint_bénigne'}},
                              'Cormery (TELMA)': {'match': {'collection': 'telma_cormery'}},
                              'Marmoutier (TELMA)': {'match': {'collection': 'telma_marmoutier'}},
                              'Saint-Martin de Tours (TELMA)': {'match': {'collection': 'telma_martin_tours'}},
                              'Salzburg': {'match': {'collection': 'salzburg'}},
                              'Schäftlarn': {'match': {'collection': 'schaeftlarn'}},
                              'St. Gallen': {'match': {'collection': 'stgallen'}},
                              'Une nouvelle charte de Théotolon': {'match': {'collection': 'tours_gasnault'}},
                              'Fragments de Saint-Julien de Tours': {'match': {'collection': 'tours_st_julien_fragments'}},
                              'Weißenburg': {'match': {'collection': 'weissenburg'}},
                              'Werden': {'match': {'collection': 'werden'}},
                              'Zürich': {'match': {'collection': 'zuerich'}}}

    AGGS_ALL_DOCS = {
      "doc_count": 13285,
      "corpus": {
        "buckets": {
          "<b>Angers</b>: Angers": {
            "doc_count": 62
          },
          "<b>Anjou</b>: Archives d’Anjou": {
            "doc_count": 74
          },
          "<b>Anjou</b>: Chroniques des comtes d’Anjou": {
            "doc_count": 10
          },
          "<b>Arnulfinger</b>: Arnulfinger": {
            "doc_count": 24
          },
          "<b>Auvergne</b>: Auvergne": {
            "doc_count": 6
          },
          "<b>Catalunya</b>: Katalonien": {
            "doc_count": 2247
          },
          "<b>Chartae Latinae</b>: Chartae Latinae X": {
            "doc_count": 3
          },
          "<b>Chartae Latinae</b>: Chartae Latinae XI": {
            "doc_count": 2
          },
          "<b>Chartae Latinae</b>: Chartae Latinae XII": {
            "doc_count": 15
          },
          "<b>Chartae Latinae</b>: Chartae Latinae XLVI": {
            "doc_count": 4
          },
          "<b>Dijon</b>: Saint-Bénigne de Dijon": {
            "doc_count": 0
          },
          "<b>Echternach</b>: Echternach": {
            "doc_count": 152
          },
          "<b>Freising</b>: Freising": {
            "doc_count": 1383
          },
          "<b>Fulda</b>: Fulda (Dronke)": {
            "doc_count": 8
          },
          "<b>Fulda</b>: Fulda (Stengel)": {
            "doc_count": 563
          },
          "<b>Gorze</b>: Gorze": {
            "doc_count": 121
          },
          "<b>Graubünden</b>: Bünden": {
            "doc_count": 24
          },
          "<b>Hersfeld</b>: Hersfeld": {
            "doc_count": 121
          },
          "<b>Langobarden</b>: Codice Diplomatico Longobardo": {
            "doc_count": 48
          },
          "<b>Lorsch</b>: Lorsch": {
            "doc_count": 4130
          },
          "<b>Luzern</b>: Luzern": {
            "doc_count": 6
          },
          "<b>Marculf</b>: Marculf": {
            "doc_count": 95
          },
          "<b>Merowinger</b>: Merowinger": {
            "doc_count": 196
          },
          "<b>Mondsee</b>: Mondsee": {
            "doc_count": 137
          },
          "<b>Papsturkunden</b>: Papsturkunden Frankreich": {
            "doc_count": 259
          },
          "<b>Passau</b>: Passau": {
            "doc_count": 102
          },
          "<b>Redon</b>: Cartulaire de Redon": {
            "doc_count": 391
          },
          "<b>Regensburg</b>: Regensburg": {
            "doc_count": 269
          },
          "<b>Rheinland</b>: Mittelrheinisch": {
            "doc_count": 98
          },
          "<b>Rheinland</b>: Rheinisch": {
            "doc_count": 78
          },
          "<b>Rätien</b>: Rätien": {
            "doc_count": 60
          },
          "<b>Salzburg</b>: Salzburg": {
            "doc_count": 229
          },
          "<b>Schäftlarn</b>: Schäftlarn": {
            "doc_count": 37
          },
          "<b>St. Gallen</b>: St. Gallen": {
            "doc_count": 779
          },
          "<b>Touraine</b>: Accensement d'une vigne de Marmoutier": {
            "doc_count": 1
          },
          "<b>Touraine</b>: Cormery (TELMA)": {
            "doc_count": 5
          },
          "<b>Touraine</b>: Eudes": {
            "doc_count": 34
          },
          "<b>Touraine</b>: Fragments de Saint-Julien de Tours": {
            "doc_count": 38
          },
          "<b>Touraine</b>: Marmoutier (TELMA)": {
            "doc_count": 108
          },
          "<b>Touraine</b>: Marmoutier - Dunois": {
            "doc_count": 281
          },
          "<b>Touraine</b>: Marmoutier - Fougères": {
            "doc_count": 7
          },
          "<b>Touraine</b>: Marmoutier - Manceau": {
            "doc_count": 189
          },
          "<b>Touraine</b>: Marmoutier - Pour le perche": {
            "doc_count": 71
          },
          "<b>Touraine</b>: Marmoutier - Serfs": {
            "doc_count": 187
          },
          "<b>Touraine</b>: Marmoutier - Trois actes faux ou interpolés": {
            "doc_count": 6
          },
          "<b>Touraine</b>: Marmoutier - Vendômois": {
            "doc_count": 163
          },
          "<b>Touraine</b>: Marmoutier - Vendômois, Appendix": {
            "doc_count": 50
          },
          "<b>Touraine</b>: Saint-Martin de Tours (TELMA)": {
            "doc_count": 15
          },
          "<b>Touraine</b>: Un acte faux de Marmoutier": {
            "doc_count": 1
          },
          "<b>Touraine</b>: Une nouvelle charte de Théotolon": {
            "doc_count": 1
          },
          "<b>Werden</b>: Werden": {
            "doc_count": 66
          },
          "<b>Wissembourg</b>: Weißenburg": {
            "doc_count": 276
          },
          "<b>Zürich</b>: Zürich": {
            "doc_count": 53
          }
        }},
      "range": {
        "buckets": [
          {
            "key": "<499",
            "from": -62104060800000.0,
            "from_as_string": "0002",
            "to": -46420214400000.0,
            "to_as_string": "0499",
            "doc_count": 11
          },
          {
            "key": "500-599",
            "from": -46388678400000.0,
            "from_as_string": "0500",
            "to": -43264540800000.0,
            "to_as_string": "0599",
            "doc_count": 24
          },
          {
            "key": "600-699",
            "from": -43233004800000.0,
            "from_as_string": "0600",
            "to": -40108867200000.0,
            "to_as_string": "0699",
            "doc_count": 156
          },
          {
            "key": "700-799",
            "from": -40077331200000.0,
            "from_as_string": "0700",
            "to": -36953193600000.0,
            "to_as_string": "0799",
            "doc_count": 4415
          },
          {
            "key": "800-899",
            "from": -36921657600000.0,
            "from_as_string": "0800",
            "to": -33797433600000.0,
            "to_as_string": "0899",
            "doc_count": 3363
          },
          {
            "key": "900-999",
            "from": -33765897600000.0,
            "from_as_string": "0900",
            "to": -30641760000000.0,
            "to_as_string": "0999",
            "doc_count": 2958
          },
          {
            "key": ">1000",
            "from": -30610224000000.0,
            "from_as_string": "1000",
            "doc_count": 1523
          }
        ]
      },
      "no_date": {
        "doc_count": 701
      }
    }

    def my_side_effect(self, id):
        if id == "urn:cts:formulae:buenden.meyer-marthaler0024.lat001":
            with open('tests/test_data/advanced_search/buenden24_term_vectors.json') as f:
                return load(f)
        if id == "urn:cts:formulae:buenden.meyer-marthaler0027.lat001":
            with open('tests/test_data/advanced_search/buenden27_term_vectors.json') as f:
                return load(f)
        if id == "urn:cts:formulae:buenden.meyer-marthaler0025.lat001":
            with open('tests/test_data/advanced_search/buenden25_term_vectors.json') as f:
                return load(f)
        if id == "urn:cts:formulae:buenden.meyer-marthaler0028.lat001":
            with open('tests/test_data/advanced_search/buenden28_term_vectors.json') as f:
                return load(f)
        with open('tests/test_data/advanced_search/buenden24_term_vectors.json') as f:
            return load(f)

    def highlight_side_effect(self, **kwargs):
        return [{'id': hit['_id'],
                 'info': hit['_source'],
                 'sents': [],
                 'sentence_spans': [],
                 'title': hit['_source']['title'],
                 'regest_sents': [],
                 'highlight': []} for hit in kwargs['search']['hits']['hits']], set()

    def vector_side_effect(self, **kwargs):
        ids = [x['_id'] for x in self.term_vectors['docs']]
        rv = self.term_vectors
        for d in kwargs['body']['docs']:
            if d['_id'] not in ids:
                new_vector = copy(self.MOCK_VECTOR_RETURN_VALUE)
                new_vector['_id'] = d['_id']
                rv['docs'].append(new_vector)
        return rv

    def search_side_effect(self, **kwargs):
        if 'suggest' in kwargs['body']:
            return self.suggest_side_effect(**kwargs)
        if 'query' in kwargs['body'] and 'ids' in kwargs['body']['query'].keys():
            return self.search_aggs
        return self.search_response

    def suggest_side_effect(self, **kwargs):
        if 'body' in kwargs.keys() and 'suggest' in kwargs['body'].keys():
            resp = {}
            if kwargs['body']['suggest']['fuzzy_suggest']['term']['field'] == 'text':
                if kwargs['body']['suggest']['fuzzy_suggest']['text'] == 'qui':
                    resp = {"suggest": {
                        "fuzzy_suggest": [{
                            "text": "qui",
                            "offset": 0,
                            "length": 3,
                            "options": [{
                                "text": "quis",
                                "score": 0.75,
                                "freq": 27
                            },
                                {
                                "text": "que",
                                "score": 0.75,
                                "freq": 27
                                },
                                {
                                "text": "qua",
                                "score": 0.75,
                                "freq": 27
                                },
                                {
                                "text": "quia",
                                "score": 0.75,
                                "freq": 27
                                },
                                {
                                "text": "quo",
                                "score": 0.75,
                                "freq": 27
                                }
                            ]
                        }]
                    }}
                elif kwargs['body']['suggest']['fuzzy_suggest']['text'] == 'nuncupatur' and kwargs['body']['suggest']['fuzzy_suggest']['term']['field'] == 'text':
                    resp = {"suggest": {
                        "fuzzy_suggest": [{
                            "text": "qui",
                            "offset": 0,
                            "length": 3,
                            "options": [{
                                "text": "nuncupata",
                                "score": 0.75,
                                "freq": 27
                            }
                            ]
                        }
                        ]
                    }
                    }
            else:
                if kwargs['body']['suggest']['fuzzy_suggest']['text'] == 'qui':
                    resp = {"suggest": {
                        "fuzzy_suggest": [{
                            "text": "qui",
                            "offset": 0,
                            "length": 3,
                            "options": [
                                {
                                "text": "quia",
                                "score": 0.75,
                                "freq": 27
                                },
                                {
                                "text": "qua",
                                "score": 0.75,
                                "freq": 27
                                },
                                {
                                "text": "que",
                                "score": 0.75,
                                "freq": 27
                                }
                            ]
                        }]
                    }}
            return resp
        test_args = copy(self.TEST_ARGS['test_fuzzy_v_to_u_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        return fake.load_response()

    def build_file_name(self, fake_args):
        return '&'.join(["{}".format(str(v)) for k, v in fake_args.items()])

    def test_return_when_no_es(self):
        """ Make sure that when ElasticSearch is not active, calls to the search functions return empty results instead of errors"""
        self.app.elasticsearch = None
        simple_test_args = OrderedDict([("index", ['formulae', "chartae"]), ("query", 'regnum'), ("lemma_search", "False"),
                                        ("page", 1), ("per_page", self.app.config["POSTS_PER_PAGE"]), ('sort', 'urn')])
        hits, total, aggs, prev = advanced_query_index(**simple_test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')
        self.assertEqual(prev, [], 'Previous results should be an empty list.')
        test_args = OrderedDict([("corpus", "all"), ("lemma_search", "False"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 814),
                                 ("month_start", 10), ("day_start", 29), ("year_end", 814), ("month_end", 11),
                                 ("day_end", 20), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn')])
        hits, total, aggs, prev = advanced_query_index(**test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')
        self.assertEqual(prev, [], 'Previous results should be an empty list.')

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_same_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_same_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_same_month(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_same_month'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_different_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_different_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_year_and_month_same_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_year_and_month_same_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_year_and_month_different_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_year_and_month_different_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_start_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_start_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, total, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])
        with self.client as c:
            test_args['source'] = 'advanced'
            r = c.get('/search/results', query_string=test_args, follow_redirects=True)
            d = self.get_context_variable('total_results')
            self.assertEqual(d, total)

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_end_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_end_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_no_corpus_given(self, mock_search):
        fake_args = copy(self.TEST_ARGS['test_date_range_search_only_end_year'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args = self.TEST_ARGS['test_no_corpus_given']
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=['all'], doc_type="", body=body)

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_start_year_and_month(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_start_year_and_month'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_end_year_and_month(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_end_year_and_month'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_normal_date_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_normal_date_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_normal_date_only_year_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_normal_date_only_year_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_plus_minus_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_plus_minus_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_exclusive_date_range_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_exclusive_date_range_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_exclusive_date_range_search_only_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_exclusive_date_range_search_only_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_exclusive_date_range_search_same_month_and_day(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_exclusive_date_range_search_same_month_and_day'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multi_corpus_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_multi_corpus_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, 'lem_highlight_to_text')
    def test_multiword_wildcard_search(self, mock_highlight, mock_search):
        test_args = copy(self.TEST_ARGS['test_multiword_wildcard_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = self.highlight_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, "lem_highlight_to_text")
    def test_lemma_advanced_search(self, mock_highlight, mock_search):
        test_args = copy(self.TEST_ARGS['test_lemma_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = self.highlight_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_mapped_lemma_advanced_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_mapped_lemma_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['search_id'] = '1234'
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertCountEqual(body['query']['bool']['must'][0]['bool']['should'],
                              mock_search.call_args_list[0][1]['body']['query']['bool']['must'][0]['bool']['should'])
        self.assertEqual(ids, [{"id": x['id']} for x in actual])
        self.assertEqual(self.app.redis.get('search_progress_1234').decode('utf-8'), '100%',
                         "Redis should keep track of download progress")

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_mapped_multiword_lemma_advanced_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_mapped_multiword_lemma_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertCountEqual(body['query']['bool']['must'][0]['bool']['should'],
                              mock_search.call_args_list[0][1]['body']['query']['bool']['must'][0]['bool']['should'])
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, "lem_highlight_to_text")
    def test_lemma_simple_search(self, mock_highlight, mock_search):
        test_args = copy(self.TEST_ARGS['test_lemma_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = {'query':
                    {'bool':
                        {'must':
                            [{'bool':
                                {'should':
                                    [{'span_near':
                                        {'clauses':
                                             [{'span_multi':
                                                   {'match':
                                                        {'fuzzy':
                                                             {'lemmas':
                                                                  {'value': 'regnum', 'fuzziness': '0'}
                                                              }
                                                         }
                                                    }
                                               }
                                              ],
                                         'slop': 4,
                                         'in_order': False
                                         }
                                      },
                                     {'span_near':
                                          {'clauses':
                                               [{'span_multi':
                                                     {'match':
                                                          {'fuzzy':
                                                               {'lemmas':
                                                                    {'value': 'regnumque', 'fuzziness': '0'}
                                                                }
                                                           }
                                                      }
                                                 }
                                                ],
                                           'slop': 4,
                                           'in_order': False}}
                                     ],
                                 'minimum_should_match': 1
                                 }
                              }
                             ]
                         }
                     },
                'sort': ['sort_prefix', 'urn'],
                'from': 0,
                'size': 10,
                'highlight':
                    {'fields':
                         {'lemmas': {'fragment_size': 1000},
                          'regest': {'fragment_size': 1000}},
                     'pre_tags': ['</small><strong>'],
                     'post_tags': ['</strong><small>'],
                     'encoder': 'html'}
                }

        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        for hit in resp['hits']['hits']:
            if 'lemmas' not in hit['highlight']:
                hit['highlight']['lemmas'] = hit['highlight']['text']
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = self.highlight_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(corpus=test_args['corpus'], lemma_search='True', q=test_args['q'], page=1,
                                               per_page=10)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, "lem_highlight_to_text")
    def test_mapped_lemma_simple_search(self, mock_highlight, mock_search):
        test_args = copy(self.TEST_ARGS['test_mapped_lemma_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = {'query':
                    {'bool':
                         {'must':
                              [{'bool':
                                    {'should':
                                         [{'span_near':
                                               {'clauses':
                                                    [{'span_multi':
                                                          {'match':
                                                               {'fuzzy':
                                                                    {'lemmas':
                                                                         {'value': 'gero', 'fuzziness': '0'}
                                                                     }
                                                                }
                                                           }
                                                      },
                                                     ],
                                                'slop': 4,
                                                'in_order': False
                                                }
                                           },
                                          {'span_near':
                                               {'clauses':
                                                    [{'span_multi':
                                                          {'match':
                                                               {'fuzzy':
                                                                    {'lemmas':
                                                                         {'value': 'gerere', 'fuzziness': '0'}
                                                                     }
                                                                }
                                                           }
                                                      }
                                                     ],
                                                'slop': 4,
                                                'in_order': False
                                                }
                                           },
                                          {'span_near':
                                               {'clauses':
                                                    [{'span_multi':
                                                          {'match':
                                                               {'fuzzy':
                                                                    {'lemmas':
                                                                         {'value': 'gesta', 'fuzziness': '0'}
                                                                     }
                                                                }
                                                           }
                                                      }
                                                     ],
                                                'slop': 4,
                                                'in_order': False
                                                }
                                           },
                                          {'span_near':
                                               {'clauses':
                                                    [{'span_multi':
                                                          {'match':
                                                               {'fuzzy':
                                                                    {'lemmas':
                                                                         {'value': 'gestus', 'fuzziness': '0'}
                                                                     }
                                                                }
                                                           }
                                                      }
                                                     ],
                                                'slop': 4,
                                                'in_order': False
                                                }
                                           },
                                          {'span_near':
                                               {'clauses':
                                                    [{'span_multi':
                                                          {'match':
                                                               {'fuzzy':
                                                                    {'lemmas':
                                                                         {'value': 'gerereve', 'fuzziness': '0'}
                                                                     }
                                                                }
                                                           }
                                                      }
                                                     ],
                                                'slop': 4,
                                                'in_order': False
                                                }
                                           }
                                          ],
                                     'minimum_should_match': 1
                                     }
                                }
                               ]
                          }
                     },
                'sort': ['sort_prefix', 'urn'],
                'from': 0,
                'size': 10,
                'aggs':
                    {'range':
                         {'date_range':
                              {'field': 'min_date',
                               'format': 'yyyy',
                               'ranges':
                                   [{'key': '<499', 'from': '0002', 'to': '0499'},
                                    {'key': '500-599', 'from': '0500', 'to': '0599'},
                                    {'key': '600-699', 'from': '0600', 'to': '0699'},
                                    {'key': '700-799', 'from': '0700', 'to': '0799'},
                                    {'key': '800-899', 'from': '0800', 'to': '0899'},
                                    {'key': '900-999', 'from': '0900', 'to': '0999'},
                                    {'key': '>1000', 'from': '1000'}
                                    ]
                               }
                          },
                     'corpus':
                         {'filters':
                              {'filters': self.SEARCH_FILTERS_CORPORA}
                          },
                     'no_date':
                         {'missing': {'field': 'min_date'}},
                     'all_docs':
                         {'global': {},
                          'aggs':
                              {'range':
                                   {'date_range':
                                        {'field': 'min_date',
                                         'format': 'yyyy',
                                         'ranges':
                                             [{'key': '<499', 'from': '0002', 'to': '0499'},
                                              {'key': '500-599', 'from': '0500', 'to': '0599'},
                                              {'key': '600-699', 'from': '0600', 'to': '0699'},
                                              {'key': '700-799', 'from': '0700', 'to': '0799'},
                                              {'key': '800-899', 'from': '0800', 'to': '0899'},
                                              {'key': '900-999', 'from': '0900', 'to': '0999'},
                                              {'key': '>1000', 'from': '1000'}
                                              ]
                                         }
                                    },
                               'corpus':
                                   {'filters':
                                        {'filters': self.SEARCH_FILTERS_CORPORA}
                                    },
                               'no_date':
                                   {'missing': {'field': 'min_date'}}
                               }
                          }
                     },
                'highlight':
                    {'fields':
                         {'lemmas': {'fragment_size': 1000},
                          'regest': {'fragment_size': 1000}
                          },
                     'pre_tags': ['</small><strong>'],
                     'post_tags': ['</strong><small>'],
                     'encoder': 'html'}
                }

        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = self.highlight_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(corpus=test_args['corpus'], lemma_search='True', q=test_args['q'], page=1,
                                               per_page=10)
        self.assertCountEqual(body['query']['bool']['must'][0]['bool']['should'],
                              mock_search.call_args_list[0][1]['body']['query']['bool']['must'][0]['bool']['should'])
        # mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, "lem_highlight_to_text")
    def test_proper_name_search(self, mock_highlight, mock_search):
        test_args = copy(self.TEST_ARGS['test_proper_name_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = self.highlight_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        for lem in mock_search.call_args_list[0].kwargs['body']['query']['bool']['must'][0]['bool']['should']:
            self.assertIn(lem, body['query']['bool']['must'][0]['bool']['should'], '{} not found'.format(lem))
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multiword_proper_name_partial_match(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_multiword_proper_name_partial_match'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        for lem in mock_search.call_args_list[0].kwargs['body']['query']['bool']['must'][0]['bool']['should']:
            self.assertIn(lem, body['query']['bool']['must'][0]['bool']['should'], '{} not found'.format(lem))
        self.assertEqual(ids, [{"id": x['id']} for x in actual],
                         "Proper name matching of only a single term in a multi-term q should produce no results.")

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multiword_proper_name_no_match(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_multiword_proper_name_no_match'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        for lem in mock_search.call_args_list[0].kwargs['body']['query']['bool']['must'][0]['bool']['should']:
            self.assertIn(lem, body['query']['bool']['must'][0]['bool']['should'], '{} not found'.format(lem))
        self.assertEqual(ids, [{"id": x['id']} for x in actual],
                         "Proper name matching where neither term is a proper name should produce no results.")

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_single_word_proper_name_no_match(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_single_word_proper_name_no_match'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        for lem in mock_search.call_args_list[0].kwargs['body']['query']['bool']['must'][0]['bool']['should']:
            self.assertIn(lem, body['query']['bool']['must'][0]['bool']['should'], '{} not found'.format(lem))
        self.assertEqual(ids, [{"id": x['id']} for x in actual],
                         "Proper name matching where neither term is a proper name should produce no results.")

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_single_word_proper_name_match_text(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_single_word_proper_name_match_text'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        vector_return_value = {'docs': []}
        non_lemma_vector = dict()
        for k, v in self.MOCK_VECTOR_RETURN_VALUE.items():
            if k != 'term_vectors':
                non_lemma_vector[k] = v
            else:
                non_lemma_vector[k] = {'text': v['text']}
        lemma_vector = copy(self.MOCK_VECTOR_RETURN_VALUE)
        for h in resp['hits']['hits']:
            new_vector = {k: v for k, v in lemma_vector.items()}
            if h['_id'] not in [x['id'] for x in ids]:
                new_vector = {k: v for k, v in non_lemma_vector.items()}
            new_vector['_id'] = h['_id']
            vector_return_value['docs'].append(new_vector)
        mock_vectors.return_value = vector_return_value
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        for lem in mock_search.call_args_list[0].kwargs['body']['query']['bool']['must'][0]['bool']['should']:
            self.assertIn(lem, body['query']['bool']['must'][0]['bool']['should'], '{} not found'.format(lem))
        self.assertEqual(ids, [{"id": x['id']} for x in actual],
                         "Single word proper name matching with text search should work.")

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multiword_proper_name_match_text(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_multiword_proper_name_match_text'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        self.search_response = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = self.search_side_effect
        mock_vectors.side_effect = self.vector_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        for lem in mock_search.call_args_list[0].kwargs['body']['query']['bool']['must'][0]['bool']['should']:
            self.assertIn(lem, body['query']['bool']['must'][0]['bool']['should'], '{} not found'.format(lem))
        self.assertEqual(ids, [{"id": x['id']} for x in actual],
                         "Multi-word proper name matching with text search should work.")

    @patch.object(Elasticsearch, "search")
    def test_regest_advanced_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_regest_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, 'lem_highlight_to_text')
    def test_regest_and_word_advanced_search(self, mock_highlight, mock_search):
        test_args = copy(self.TEST_ARGS['test_regest_and_word_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = self.highlight_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_regest_advanced_search_with_wildcard(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_regest_advanced_search_with_wildcard'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, 'lem_highlight_to_text')
    def test_multiword_lemma_advanced_search(self, mock_highlight, mock_search):
        test_args = copy(self.TEST_ARGS['test_multiword_lemma_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_highlight.side_effect = self.highlight_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_v_to_u_multiword(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_v_to_u_multiword'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        sents = [{'sents':
                      [Markup('seu Irminpald condiderunt, simili modo ad Pipurc quem Rihheri et </small><strong>Uuolfhart</strong><small> </small><strong>cum</strong><small> sociis construxerunt in anno XXXI. regni domni Tassilonis inlustrissimi ducis ')]}]
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_v_to_u_single_word(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_v_to_u_single_word'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        sents = [Markup('fuerit, pro episcopalis officii debito absque molestia uobis prebeant. Sane </small><strong>noualium</strong><small> etc. Quemadmodum autem uos ab omni exactione liberas esse statuimus,')]
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertIn(sents, [x['sents'] for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_single_word_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas
            This also makes sure that a highlighted word that is just the wrong distance from the end of the string
            will not cause an error.
        """
        test_args = copy(self.TEST_ARGS['test_single_word_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        sents = [{'sents': [Markup('testes. Ego Orsacius pro misericordia dei vocatus presbiter ad vice </small><strong>Pettonis</strong><small> presbiteri scripsi et suscripsi.')]},
                 {'sents': [Markup('vico Uaze testes. Ego Orsacius licit indignus presbiteri ad vice </small><strong>Pettonis</strong><small> presbiteri scripsi et suscripsi.')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_single_word_highlighting_wildcard(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas
            This also makes sure that a highlighted word that is just the wrong distance from the end of the string
            will not cause an error.
        """
        test_args = copy(self.TEST_ARGS['test_single_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for i1, hit in enumerate(resp['hits']['hits']):
            for i2, t in enumerate(hit['highlight']['text']):
                resp['hits']['hits'][i1]['highlight']['text'][i2] = re.sub(r'regis', '</small><strong>regis</strong><small>', t)
        sents = [{'sents':
                      [Markup('omnium cartarum adcommodat firmitatem. Facta cartula in civitate Curia, sub </small><strong>regnum</strong><small> domni nostri Charoli gloriosissimi regis, sub die, quod est XV '),
                       Markup('cartula in civitate Curia, sub regnum domni nostri Charoli gloriosissimi </small><strong>regis</strong><small>, sub die, quod est XV kl. madii, sub presenciarum bonorum '),
                       Markup('ab eo rogiti venerunt vel signa fecerunt, Notavi diem et </small><strong>regnum</strong><small> superscripsi. Signum Baselii et filii sui Rofini, qui haec fieri ')]},
                 {'sents':
                      [Markup('Facta donacio in loco Fortunes, sub presencia virorum testium sub </small><strong>regnum</strong><small> domni nostri Caroli regis, Sub die, quod est pridie kl.'),
                       Markup('Fortunes, sub presencia virorum testium sub regnum domni nostri Caroli </small><strong>regis</strong><small>, Sub die, quod est pridie kl. aprilis. Notavi diem et '),
                       Markup('Sub die, quod est pridie kl. aprilis. Notavi diem et </small><strong>regnum</strong><small> superscripsi. Signum Uictorini et Felicianes uxoris ipsius, qui haec fieri ')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = 'reg*'
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_word_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = copy(self.TEST_ARGS['test_multi_word_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        sents = [{'sents': [Markup('Orsacius pro misericordia dei vocatus presbiter ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licit indignus presbiteri ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licet indignus presbiter a vice Augustani diaconis </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('Orsacius per misericordiam dei vocatus presbiter a vice Lubucionis diaconi </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_word_highlighting_repeated_words(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = copy(self.TEST_ARGS['test_multi_word_highlighting_repeated_words'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        sents = [{'sents': [Markup('Prestanti testes. Signum Lobicini presbiteri testes. Signum Seffonis fratris Remedii </small><strong>testes</strong><small>. </small><strong>Signum</strong><small> </small><strong>Uuiliarentis</strong><small> </small><strong>testes</strong><small>. </small><strong>Signum</strong><small> </small><strong>Crespionis</strong><small> testes. Signum Donati testes. Signum Gauuenti testes. Ego Orsacius pro ')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_single_word_fuzzy_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas
            This also makes sure that a highlighted word that is just the wrong distance from the end of the string
            will not cause an error.
        """
        test_args = copy(self.TEST_ARGS['test_single_word_fuzzy_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        sents = [{'sents': [Markup('testes. Ego Orsacius pro misericordia dei vocatus presbiter ad vice </small><strong>Pettonis</strong><small> presbiteri scripsi et suscripsi.')]},
                 {'sents': [Markup('vico Uaze testes. Ego Orsacius licit indignus presbiteri ad vice </small><strong>Pettonis</strong><small> presbiteri scripsi et suscripsi.')]},
                 {'sents': [Markup('aecclesiae fidelibus presentibus scilicet et futuris, qualiter me convenit cum </small><strong>Hattone</strong><small> venerabili episcopo et abbate cenobii Lauresham dicti, quasdam res ipsius ')]},
                 {'sents': [Markup('libras III. Facta in Lopiene, mense februarium, anno II regnante </small><strong>Ottone</strong><small> filio Ottonis. Testes: Laurencius, Vigilius, Dominicus, Saluianus, Soluanus, Orsacius, Maginaldus,')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_word_fuzzy_highlighting_with_wildcard(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when doing fuzzy searches with wildcards"""
        test_args = copy(self.TEST_ARGS['test_multi_word_fuzzy_highlighting_with_wildcard'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        self.search_response = fake.load_response()
        self.search_aggs = fake.load_aggs()
        sents = [{'sents': [Markup('Orsacius pro misericordia dei vocatus presbiter ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licit indignus presbiteri ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licet indignus presbiter a vice Augustani diaconis </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('Orsacius per misericordiam dei vocatus presbiter a vice Lubucionis diaconi </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]}]
        mock_search.side_effect = self.search_side_effect
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_word_fuzzy_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when doing fuzzy searches"""
        test_args = copy(self.TEST_ARGS['test_multi_word_fuzzy_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        sents = [{'sents': [Markup('aurum libras III. Facta in Lopiene, mense februarium, anno II </small><strong>regnante</strong><small> </small><strong>Ottone</strong><small> filio Ottonis. Testes: Laurencius, Vigilius, Dominicus, Saluianus, Soluanus, Orsacius, Maginaldus,')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_word_highlighting_wildcard(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas
            This also makes sure that a highlighted word that is just the wrong distance from the end of the string
            will not cause an error.
        """
        test_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for i1, hit in enumerate(resp['hits']['hits']):
            for i2, t in enumerate(hit['highlight']['text']):
                resp['hits']['hits'][i1]['highlight']['text'][i2] = re.sub(r'regis', '</small><strong>regis</strong><small>', t)
        sents = [{'sents':
                      [Markup('omnium cartarum adcommodat firmitatem. Facta cartula in civitate Curia, sub </small><strong>regnum</strong><small> </small><strong>domni</strong><small> nostri Charoli gloriosissimi regis, sub die, quod est XV kl.'),
                       Markup('cartarum adcommodat firmitatem. Facta cartula in civitate Curia, sub regnum </small><strong>domni</strong><small> nostri Charoli gloriosissimi </small><strong>regis</strong><small>, sub die, quod est XV kl. madii, sub presenciarum bonorum ')]},
                 {'sents':
                      [Markup('Facta donacio in loco Fortunes, sub presencia virorum testium sub </small><strong>regnum</strong><small> </small><strong>domni</strong><small> nostri Caroli regis, Sub die, quod est pridie kl. aprilis.'),
                       Markup('donacio in loco Fortunes, sub presencia virorum testium sub regnum </small><strong>domni</strong><small> nostri Caroli </small><strong>regis</strong><small>, Sub die, quod est pridie kl. aprilis. Notavi diem et ')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = 'reg* domni'
        test_args['slop'] = '3'
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_single_letter_highlighting_one_word(self, mock_vectors, mock_search):
        """ Make sure that single letter words are correctly highlighted (i.e., the word and not the rest of the fragment)
        """
        test_args = copy(self.TEST_ARGS['test_single_letter_highlighting_one_word'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        sents = [{'sents': [Markup('</small><strong>a</strong><small> quem dimisit filio suo Rofino et agrum in Pulueraria modios ')]},
                 {'sents': [Markup('de supra in Theudoranes, dabtus in sancti Petri; alium pratum </small><strong>a</strong><small> Sanguinetum honus I, confinat da una parte in Canilias, da '),
                            Markup('da una parte in Canilias, da alia in via; agrum </small><strong>a</strong><small> Tonbeclo modios II, confinat in Scolchengus, da alia in sancti '),
                            Markup('in Scolchengus, da alia in sancti Petri; alium agrum modios </small><strong>a</strong><small> Tomba maiore, confinat da una parte in Martini, de alia '),
                            Markup('saltarii testes. Signum Exuberii testes. Ego Orsacius licet indignus presbiter </small><strong>a</strong><small> vice Augustani diaconis scripsi et suscripsi.')]},
                 {'sents': [Markup('alia in Uictoriani coloni, da supra in Massanesco. Signum Daumerii </small><strong>a</strong><small> iudicis, qui hanc cartam ob mercedis sue augmentum fieri petiit.'),
                            Markup('Signum Ingenni testes. Ego Orsacius per misericordiam dei vocatus presbiter </small><strong>a</strong><small> vice Lubucionis diaconi scripsi et suscripsi.')]},
                 {'sents': [Markup('In Christi nomine. Ego itaque bresbiter Valencio sanus </small><strong>a</strong><small> sana mente per comiatu senioris Iltebaldi et cum manu – – dono ')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        actual, _, _, _ = advanced_query_index(**test_args)
        for s in sents:
            self.assertIn(s, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_single_letter_highlighting_multiword(self, mock_vectors, mock_search):
        """ Make sure that single letter words are correctly highlighted (i.e., the word and not the rest of the fragment)
        """
        test_args = copy(self.TEST_ARGS['test_single_letter_highlighting_multiword'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        sents = [{'sents': [Markup('da alia in Uictoriani coloni, da supra in Massanesco. Signum </small><strong>Daumerii</strong><small> </small><strong>a</strong><small> iudicis, qui hanc cartam ob mercedis sue augmentum fieri petiit.')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_single_lemma_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = OrderedDict([("corpus", "all"), ("lemma_search", "True"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_single_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': [Markup('omnium cartarum adcommodat firmitatem. Facta cartula in civitate Curia, sub '
                                   '</small><strong>regnum</strong><small> domni nostri Charoli gloriosissimi regis, '
                                   'sub die, quod est XV '),
                            Markup('ab eo rogiti venerunt vel signa fecerunt, Notavi diem et '
                                   '</small><strong>regnum</strong><small> superscripsi. Signum Baselii et filii sui '
                                   'Rofini, qui haec fieri ')]},
                 {'sents': [Markup('Facta donacio in loco Fortunes, sub presencia virorum testium sub '
                                   '</small><strong>regnum</strong><small> domni nostri Caroli regis, Sub die, quod '
                                   'est pridie kl.'),
                            Markup('Sub die, quod est pridie kl. aprilis. Notavi diem et '
                                   '</small><strong>regnum</strong><small> superscripsi. Signum Uictorini et '
                                   'Felicianes uxoris ipsius, qui haec fieri ')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_lemma_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = OrderedDict([("corpus", "buenden"), ("lemma_search", "True"), ("q", 'regnum+domni'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': [Markup('omnium cartarum adcommodat firmitatem. '
                                   'Facta cartula in civitate Curia, sub </small><strong>regnum</strong><small> '
                                   '</small><strong>domni</strong><small> nostri Charoli gloriosissimi regis, sub die, '
                                   'quod est XV kl.')]},
                 {'sents': [Markup('Facta donacio in loco Fortunes, sub '
                                   'presencia virorum testium sub </small><strong>regnum</strong><small> '
                                   '</small><strong>domni</strong><small> nostri Caroli regis, Sub die, quod est '
                                   'pridie kl. aprilis.')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_lemma_highlighting_terms_out_of_order(self, mock_vectors, mock_search):
        """ Make sure that highlighting is correctly transferred when ordered_terms is False"""
        test_args = OrderedDict([("corpus", "buenden"), ("lemma_search", "True"), ("q", 'domni+regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': [Markup('omnium cartarum adcommodat firmitatem. '
                                   'Facta cartula in civitate Curia, sub </small><strong>regnum</strong><small> '
                                   '</small><strong>domni</strong><small> nostri Charoli gloriosissimi regis, sub die, '
                                   'quod est XV kl.')]},
                 {'sents': [Markup('Facta donacio in loco Fortunes, sub '
                                   'presencia virorum testium sub </small><strong>regnum</strong><small> '
                                   '</small><strong>domni</strong><small> nostri Caroli regis, Sub die, quod est '
                                   'pridie kl. aprilis.')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_lemma_highlighting_terms_out_of_order_ordered_terms_True(self, mock_vectors, mock_search):
        """ Make sure that highlighting is correctly transferred when ordered_terms is False"""
        test_args = OrderedDict([("corpus", "buenden"), ("lemma_search", "True"), ("q", 'domni+regnum'), ("fuzziness", "0"),
                                 ("in_order", "True"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = []
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_lemma_highlighting_terms_with_slop(self, mock_vectors, mock_search):
        """ Make sure that highlighting is correctly transferred when ordered_terms is False"""
        test_args = OrderedDict([("corpus", "buenden"), ("lemma_search", "True"), ("q", 'domni+regnum+regis'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "2"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': [Markup('Facta donacio in loco Fortunes, sub '
                                   'presencia virorum testium sub </small><strong>regnum</strong><small> '
                                   '</small><strong>domni</strong><small> nostri Caroli '
                                   '</small><strong>regis</strong><small>, Sub die, quod est '
                                   'pridie kl. aprilis. Notavi diem et ')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_multi_lemma_highlighting_terms_with_slop_in_order(self, mock_vectors, mock_search):
        """ Make sure that highlighting is correctly transferred when ordered_terms is False"""
        test_args = OrderedDict([("corpus", "buenden"), ("lemma_search", "True"), ("q", 'sub+regis'), ("fuzziness", "0"),
                                 ("in_order", "True"), ("year", 0), ("slop", "4"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': [Markup('firmitate. Facta donacio in loco Fortunes, sub '
                                   'presencia virorum testium </small><strong>sub</strong><small> regnum '
                                   'domni nostri Caroli </small><strong>regis</strong><small>, Sub die, quod est '
                                   'pridie kl. aprilis. Notavi diem et ')]}]
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.return_value = self.term_vectors
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_lemma_advanced_search_with_wildcard(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_lemma_advanced_search_with_wildcard'])
        mock_search.return_value = [], 0, {}
        with self.client:
            ids, hits, agg, prev = advanced_query_index(**test_args)
            self.assertEqual(ids, [])
            self.assertEqual(hits, 0)
            self.assertEqual(prev, [])
            self.assertIn(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."), [x[0] for x in self.flashed_messages])

    @patch.object(Elasticsearch, "search")
    def test_lemma_simple_search_with_wildcard(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_lemma_advanced_search_with_wildcard'])
        mock_search.return_value = [], 0, {}
        with self.client:
            ids, hits, agg, prev = advanced_query_index(corpus=test_args['corpus'], lemma_search='True',
                                                        q=test_args['q'], page=1, per_page=10, source='simple')
            self.assertEqual(ids, [])
            self.assertEqual(hits, 0)
            self.assertEqual(prev, [])
            self.assertIn(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."), [x[0] for x in self.flashed_messages])

    @patch.object(Elasticsearch, "search")
    def test_composition_place_advanced_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_composition_place_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, 'lem_highlight_to_text')
    def test_simple_multi_corpus_search(self, mock_highlight, mock_search):
        test_args = OrderedDict([("corpus", ['formulae', 'chartae']), ("q", 'regnum'), ("lemma_search", "False"),
                                 ("page", 1), ("per_page", self.app.config["POSTS_PER_PAGE"]), ('sort', 'urn'),
                                 ('source', 'simple')])
        mock_highlight.side_effect = self.highlight_side_effect
        mock_search.return_value = {"hits": {"hits": [{'_id': 'urn:cts:formulae:stgallen.wartmann0259.lat001',
                                    '_source': {'urn': 'urn:cts:formulae:stgallen.wartmann0259.lat001',
                                                'title': 'St. Gallen 259'},
                                    'highlight': {
                                        'text': ['Notavi die et <strong>regnum</strong>. Signum Mauri et uxores suas Audoaras, qui hanc cartam fieri rogaverunt.'],
                                        'lemmas': ['Notavi die et <strong>regnum</strong>. Signum Mauri et uxores suas Audoaras, qui hanc cartam fieri rogaverunt.']
                                    }}],
                                             'total': {'value': 0,
                                                       "relation": "eq"}},
                                    'aggregations': {'all_docs': self.AGGS_ALL_DOCS,
                                                     "no_date": {
                                                         "doc_count": 14
                                                     },
                                                        "range": {
                                                          "buckets": [
                                                            {
                                                              "key": "<499",
                                                              "from": -62104060800000.0,
                                                              "from_as_string": "0002",
                                                              "to": -46420214400000.0,
                                                              "to_as_string": "0499",
                                                              "doc_count": 0
                                                            },
                                                            {
                                                              "key": "500-599",
                                                              "from": -46388678400000.0,
                                                              "from_as_string": "0500",
                                                              "to": -43264540800000.0,
                                                              "to_as_string": "0599",
                                                              "doc_count": 0
                                                            },
                                                            {
                                                              "key": "600-699",
                                                              "from": -43233004800000.0,
                                                              "from_as_string": "0600",
                                                              "to": -40108867200000.0,
                                                              "to_as_string": "0699",
                                                              "doc_count": 0
                                                            },
                                                            {
                                                              "key": "700-799",
                                                              "from": -40077331200000.0,
                                                              "from_as_string": "0700",
                                                              "to": -36953193600000.0,
                                                              "to_as_string": "0799",
                                                              "doc_count": 0
                                                            },
                                                            {
                                                              "key": "800-899",
                                                              "from": -36921657600000.0,
                                                              "from_as_string": "0800",
                                                              "to": -33797433600000.0,
                                                              "to_as_string": "0899",
                                                              "doc_count": 0
                                                            },
                                                            {
                                                              "key": "900-999",
                                                              "from": -33765897600000.0,
                                                              "from_as_string": "0900",
                                                              "to": -30641760000000.0,
                                                              "to_as_string": "0999",
                                                              "doc_count": 6
                                                            },
                                                            {
                                                              "key": ">1000",
                                                              "from": -30610224000000.0,
                                                              "from_as_string": "1000",
                                                              "doc_count": 177
                                                            }
                                                          ]
                                                        },
                                                     "corpus": {
                                                      "buckets": {k: {'doc_count': 0} if k != '<b>Angers</b>: Angers' else
                                                      {k: {'doc_count': 2}}
                                                                  for k in self.AGGS_ALL_DOCS['corpus']['buckets']
                                                                  }
                                                    }}}
        body = {'query':
                    {'bool':
                         {'must':
                              [{'bool':
                                    {'should':
                                         [{'span_near':
                                               {'clauses':
                                                    [{'span_or':
                                                          {'clauses':
                                                               [{'span_multi':
                                                                     {'match':
                                                                          {'regexp':
                                                                               {'text': 'regn[uv]m'}
                                                                           }
                                                                      }
                                                                 }
                                                                ]
                                                           }
                                                      }
                                                     ],
                                                'slop': 4,
                                                'in_order': False
                                                }
                                           }
                                          ],
                                     'minimum_should_match': 1
                                     }
                                }
                               ]
                          }
                     },
                'sort': ['sort_prefix', 'urn'],
                'from': 0,
                'size': 10,
                'highlight':
                    {'fields':
                         {'text': {'fragment_size': 1000},
                          'regest': {'fragment_size': 1000}
                          },
                     'pre_tags': ['</small><strong>'],
                     'post_tags': ['</strong><small>'],
                     'encoder': 'html'
                     }
                }
        advanced_query_index(**test_args)
        mock_search.assert_any_call(index=['formulae', 'chartae'], doc_type="", body=body)
        test_args['q'] = 'regnum domni'
        body['query']['bool']['must'][0]['bool']['should'][0]['span_near']['clauses'] = [{'span_or':
                                                                                              {'clauses':
                                                                                                   [
                                                                                                       {'span_multi':
                                                                                                            {'match':
                                                                                                                 {'regexp':
                                                                                                                      {'text': 'regn[uv]m'}
                                                                                                                  }
                                                                                                             }
                                                                                                        }
                                                                                                   ]
                                                                                              }},
            {'span_or':
                 {'clauses':
                      [{'span_multi':
                            {'match':
                                 {'regexp':
                                      {'text': 'domn[ij]'}
                                  }
                             }
                        }
                       ]
                  }
             }
        ]
        advanced_query_index(**test_args)
        mock_search.assert_any_call(index=['formulae', 'chartae'], doc_type="", body=body)
        test_args['q'] = 're?num'
        body['query']['bool']['must'][0]['bool']['should'][0]['span_near']['clauses'] = [{'span_multi':
                                                                                              {'match':
                                                                                                   {'regexp':
                                                                                                        {'text': 're.n[uv]m'}
                                                                                                    }
                                                                                               }
                                                                                          }]
        advanced_query_index(**test_args)
        mock_search.assert_any_call(index=['formulae', 'chartae'], doc_type="", body=body)
        self.assertCountEqual({'index': ['formulae', 'chartae'], 'doc_type': "", 'body': body},
                              mock_search.call_args[1])
        test_args['corpus'] = ['']
        hits, total, aggs, prev = advanced_query_index(**test_args)
        self.assertEqual(mock_search.call_args[1]['index'], ['all'],
                         'Empty string for corpus input should default to ["all"]')
        test_args['corpus'] = ['formulae', 'chartae']
        test_args['q'] = ''
        hits, total, aggs, prev = advanced_query_index(**test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')
        with self.client:
            self.client.get('/search/simple?corpus=&q=regnum', follow_redirects=True)
            self.assertIn(_('Sie müssen mindestens eine Sammlung für die Suche auswählen ("Formeln" und/oder "Urkunden").') +
                          _(' Resultate aus "Formeln" und "Urkunden" werden hier gezeigt.'), [x[0] for x in self.flashed_messages])
            old_search_args = session['previous_search_args']
            self.assertIn('fulda_dronke', old_search_args['corpus'],
                          'Charters should automatically be search when no index is given in simple search.')
            self.assertIn('andecavensis', old_search_args['corpus'],
                          'Formulae should automatically be search when no index is given in simple search.')
            self.client.get('/search/results?source=simple&corpus=formulae&q=regnum&old_search=True', follow_redirects=True)
            self.assertEqual(old_search_args['corpus'], session['previous_search_args']['corpus'],
                             'Searches made with the old_search=True argument should not change the previous_search_args.')
            self.client.get('/search/simple?corpus=formulae&q=', follow_redirects=True)
            self.assertIn(_('Dieses Feld wird benötigt.') + _(' Die einfache Suche funktioniert nur mit einem Suchwort.'),
                          [x[0] for x in self.flashed_messages])
            self.client.get('/search/simple?corpus=formulae&q=regnum&lemma_search=True', follow_redirects=True)
            self.assertEqual(session['previous_search_args']['lemma_search'], 'True', '"True" should remain "True"')
            self.client.get('/search/simple?corpus=formulae&q=regnum&lemma_search=y', follow_redirects=True)
            self.assertEqual(session['previous_search_args']['lemma_search'], 'True', '"y" should be converted to "True"')

    # @patch.object(Elasticsearch, "search")
    # def test_suggest_composition_places(self, mock_search):
    #     test_args = copy(self.TEST_ARGS['test_suggest_composition_places'])
    #     fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
    #     resp = fake.load_response()
    #     expected = [' ', 'Bettingen', 'Freising', 'Isen', 'Süstern', 'Weimodo regia villa']
    #     mock_search.side_effect = cycle([resp, aggs])
    #     results = suggest_composition_places()
    #     self.assertEqual(results, expected, 'The true results should match the expected results.')

    @patch.object(Elasticsearch, "search")
    def test_suggest_word_search_completion(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_suggest_word_search_completion'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        expected = ['scripsi',
                    'scripsi diemque et tempus designavi',
                    'scripsi et manu mea propria subscripsi',
                    'scripsi et subscri st psi notavi diem',
                    'scripsi et subscripsi',
                    'scripsi et subscripsi notavi diem v fer',
                    'scripsi et supscripsi notavi diem et',
                    'scripsi et suscripsi',
                    'scripsi et teste me suscripsi',
                    'scripsi signum baselii et filii sui rofini']
        mock_search.side_effect = cycle([resp, aggs])
        test_args['qSource'] = 'text'
        results = suggest_word_search(**test_args)
        self.assertEqual(results, expected, 'The true results should match the expected results.')
        # Make sure that a wildcard in the search term will not call ElasticSearch but, instead, return None
        test_args['q'] = '*'
        results = suggest_word_search(**test_args)
        self.assertIsNone(results, 'Autocomplete should return None when only "*" is in the search string.')
        test_args['q'] = '?'
        results = suggest_word_search(**test_args)
        self.assertIsNone(results, 'Autocomplete should return None when only "?" is in the search string.')
        test_args['q'] = 'ill*'
        results = suggest_word_search(**test_args)
        self.assertIsNone(results, 'Autocomplete should return None when "*" is anywhere in the search string.')
        test_args['q'] = 'ill?'
        results = suggest_word_search(**test_args)
        self.assertIsNone(results, 'Autocomplete should return None when "?" is anywhere in the search string.')

    @patch.object(Elasticsearch, "search")
    def test_suggest_regest_word_search_completion(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_suggest_regest_word_search_completion'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        expected = ['schenkt dem kloster disentis auf ableben',
                    'schenkt dem kloster disentis güter',
                    'schenkt der kirche st hilarius zu seinem',
                    'schenkt seinem neffen priectus seinen',
                    'schenkt zu seinem und seiner eltern',
                    'schenkt zu seinem und seiner gattin',
                    'schenkt zum seelenheil seines bruders']
        mock_search.side_effect = cycle([resp, aggs])
        test_args['qSource'] = 'regest'
        results = suggest_word_search(**test_args)
        self.assertEqual(results, expected, 'The true results should match the expected results.')
        # Make sure that a wildcard in the search term will not call ElasticSearch but, instead, return None
        test_args['regest_q'] = '*'
        results = suggest_word_search(**test_args)
        self.assertIsNone(results, 'Autocomplete should return None when only "*" is in the search string.')
        test_args['regest_q'] = '?'
        results = suggest_word_search(**test_args)
        self.assertIsNone(results, 'Autocomplete should return None when only "?" is in the search string.')
        test_args['regest_q'] = 'tau*'
        results = suggest_word_search(**test_args)
        self.assertIsNone(results, 'Autocomplete should return None when "*" is anywhere in the search string.')
        test_args['regest_q'] = 'tau?'
        results = suggest_word_search(**test_args)
        self.assertIsNone(results, 'Autocomplete should return None when "?" is anywhere in the search string.')

    @patch.object(Elasticsearch, "search")
    def test_regest_word_search_highlighting(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_regest_word_search_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        expected = [{'regest_sents': [Markup('Graf Wido von Lomello </small><strong>schenkt</strong><small> dem Kloster Disentis Güter und Rechte.')]},
                    {'regest_sents': [Markup('Bischof Tello von Chur </small><strong>schenkt</strong><small> dem Kloster Disentis auf Ableben seine Güter in der')]},
                    {'regest_sents': [Markup('Ovilio von Trimmis </small><strong>schenkt</strong><small> zu seinem und seiner Gattin Theoderia Seelenheil der')]},
                    {'regest_sents': [Markup('Victorinus </small><strong>schenkt</strong><small> zu seinem und seiner Eltern Seelenheil der Kirche')]},
                    {'regest_sents': [Markup('Der Richter Daumerius </small><strong>schenkt</strong><small> der Kirche St. Hilarius zu seinem Seelenheil und zum')]},
                    {'regest_sents': [Markup('Vigilius von Trimmis </small><strong>schenkt</strong><small> zum Seelenheil seines Bruders Viktor einen kleinen')]},
                    {'regest_sents': [Markup('Der Priester Valencio </small><strong>schenkt</strong><small> seinem Neffen Priectus seinen ganzen Besitz zu Maienfeld.')]}]
        mock_search.side_effect = cycle([resp, aggs])
        Search.HIGHLIGHT_CHARS_AFTER = 50
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(expected, [{"regest_sents": x['regest_sents']} for x in actual])
        Search.HIGHLIGHT_CHARS_AFTER = 30

    @patch.object(Elasticsearch, "search")
    def test_suggest_word_search_completion_no_qSource(self, mock_search):
        """ Make sure that None is returned if qSource is not an accepted value"""
        test_args = copy(self.TEST_ARGS['test_suggest_word_search_completion_no_qSource'])
        results = suggest_word_search(**test_args)
        self.assertIsNone(results)

    def test_results_sort_option(self):
        self.assertEqual(build_sort_list('urn'), ['sort_prefix', 'urn'])
        self.assertEqual(build_sort_list('min_date_asc'), [{'all_dates': {'order': 'asc', 'mode': 'min'}}, 'urn'])
        self.assertEqual(build_sort_list('max_date_asc'), [{'all_dates': {'order': 'asc', 'mode': 'max'}}, 'urn'])
        self.assertEqual(build_sort_list('min_date_desc'), [{'all_dates': {'order': 'desc', 'mode': 'min'}}, 'urn'])
        self.assertEqual(build_sort_list('max_date_desc'), [{'all_dates': {'order': 'desc', 'mode': 'max'}}, 'urn'])
        self.assertEqual(build_sort_list('urn_desc'), ['sort_prefix', {'urn': {'order': 'desc'}}])

    @patch.object(Elasticsearch, "search")
    def test_save_requests(self, mock_search):
        self.app.config['SAVE_REQUESTS'] = True
        test_args = copy(self.TEST_ARGS['test_save_requests'])
        file_name_base = self.build_file_name(test_args)
        fake = FakeElasticsearch(file_name_base, 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        with patch('builtins.open', new_callable=mock_open()) as m:
            with patch('json.dump') as mock_dump:
                actual, _, _, _ = advanced_query_index(**test_args)
                mock_dump.assert_any_call(resp, m.return_value.__enter__.return_value, indent=2, ensure_ascii=False)
                mock_dump.assert_any_call(body, m.return_value.__enter__.return_value, indent=2, ensure_ascii=False)
                mock_dump.assert_any_call(ids, m.return_value.__enter__.return_value, indent=2, ensure_ascii=False)

    @patch.object(Elasticsearch, "search")
    def test_specific_day_advanced_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_specific_day_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['special_days'] = test_args['special_days'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multiple_specific_day_advanced_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_multiple_specific_day_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['special_days'] = test_args['special_days'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "mtermvectors")
    def test_download_search_results(self, mock_vectors, mock_search):
        with self.client as c:
            c.get('/search/download/1', follow_redirects=True)
            self.assertIn(_('Keine Suchergebnisse zum Herunterladen.'), [x[0] for x in self.flashed_messages])
            self.assertIn('main::index.html', [x[0].name for x in self.templates])
        test_args = copy(self.TEST_ARGS['test_download_search_results'])
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        resp = fake.load_response()
        aggs = fake.load_aggs()
        mock_search.side_effect = cycle([resp, aggs])
        mock_vectors.side_effect = self.vector_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['special_days'] = [test_args['special_days']]
        self.nemo.open_texts += ['urn:cts:formulae:buenden.meyer-marthaler0027.lat001', 'urn:cts:formulae:mondsee.rath0128.lat001']
        with open('tests/test_data/advanced_search/downloaded_search.pdf', mode='rb') as f:
            expected = f.read()
        with open('tests/test_data/advanced_search/downloaded_search_lemmas.pdf', mode='rb') as f:
            expected_lemmas = f.read()
        with open('tests/test_data/advanced_search/downloaded_search_with_parts.pdf', mode='rb') as f:
            expected_parts = f.read()
        with open('tests/test_data/advanced_search/downloaded_search_with_parts_no_q.pdf', mode='rb') as f:
            expected_parts_no_q = f.read()
        with self.client as c:
            c.get('/search/results?source=advanced&sort=urn&q=regnum&fuzziness=0&slop=0&in_order=False&regest_q=schenk*&year=&month=0&day=&year_start=&month_start=0&day_start=&year_end=&month_end=0&day_end=&date_plus_minus=0&exclusive_date_range=False&composition_place=&submit=True&corpus=all&special_days=')
            r = c.get('/search/download/1')
            recreate = False
            # Uncomment this when the mock search download files need to be recreated
            # recreate = True
            if recreate:
                with open('tests/test_data/advanced_search/downloaded_search.pdf', mode='wb') as f:
                    f.write(r.get_data())
            self.assertEqual(re.search(b'>>\nstream\n.*?>endstream', expected).group(0),
                             re.search(b'>>\nstream\n.*?>endstream', r.get_data()).group(0))
            for hit in resp['hits']['hits']:
                hit['highlight']['lemmas'] = hit['highlight'].pop('text')
            c.get('/search/results?source=advanced&sort=urn&q=regnum&fuzziness=0&slop=0&in_order=False&regest_q=schenk*&year=&month=0&day=&year_start=&month_start=0&day_start=&year_end=&month_end=0&day_end=&date_plus_minus=0&exclusive_date_range=False&composition_place=&submit=True&corpus=all&special_days=&lemma_search=True')
            r = c.get('/search/download/1')
            if recreate:
                with open('tests/test_data/advanced_search/downloaded_search_lemmas.pdf', mode='wb') as f:
                    f.write(r.get_data())
            self.assertEqual(re.search(b'>>\nstream\n.*?>endstream', expected_lemmas).group(0),
                             re.search(b'>>\nstream\n.*?>endstream', r.get_data()).group(0))
            test_args = copy(self.TEST_ARGS['test_multi_charter_part_search'])
            test_args['formulaic_parts'] = test_args['formulaic_parts'].replace('%2B', '+')
            fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
            resp = fake.load_response()
            aggs = fake.load_aggs()
            mock_search.side_effect = cycle([resp, aggs])
            test_args['corpus'] = test_args['corpus'].split('+')
            test_args['special_days'] = [test_args['special_days']]
            c.get('/search/results?source=advanced&sort=urn&q=christi&fuzziness=0&slop=0&in_order=False&regest_q=&year=&month=0&day=&year_start=&month_start=0&day_start=&year_end=&month_end=0&day_end=&date_plus_minus=0&exclusive_date_range=False&composition_place=&submit=True&corpus=all&special_days=&formulaic_parts=Poenformel%2BStipulationsformel')
            r = c.get('/search/download/1')
            if recreate:
                with open('tests/test_data/advanced_search/downloaded_search_with_parts.pdf', mode='wb') as f:
                    f.write(r.get_data())
            self.assertEqual(re.search(b'>>\nstream\n.*?>endstream', expected_parts).group(0),
                             re.search(b'>>\nstream\n.*?>endstream', r.get_data()).group(0))
            test_args = copy(self.TEST_ARGS['test_charter_part_search_no_q'])
            test_args['formulaic_parts'] = test_args['formulaic_parts'].replace('%2B', '+')
            fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
            resp = fake.load_response()
            aggs = fake.load_aggs()
            mock_search.side_effect = cycle([resp, aggs])
            test_args['corpus'] = test_args['corpus'].split('+')
            test_args['special_days'] = [test_args['special_days']]
            c.get('/search/results?source=advanced&sort=urn&q=&fuzziness=0&slop=0&in_order=False&regest_q=&year=&month=0&day=&year_start=&month_start=0&day_start=&year_end=&month_end=0&day_end=&date_plus_minus=0&exclusive_date_range=False&composition_place=&submit=True&corpus=all&special_days=&formulaic_parts=Poenformel%2BStipulationsformel')
            r = c.get('/search/download/1')
            if recreate:
                with open('tests/test_data/advanced_search/downloaded_search_with_parts_no_q.pdf', mode='wb') as f:
                    f.write(r.get_data())
            self.assertEqual(re.search(b'>>\nstream\n.*?>endstream', expected_parts_no_q).group(0),
                             re.search(b'>>\nstream\n.*?>endstream', r.get_data()).group(0))

    @patch.object(Elasticsearch, "search")
    def test_single_charter_part_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_single_charter_part_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_single_charter_part_search_with_wildcard(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_single_charter_part_search_with_wildcard'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multi_charter_part_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_multi_charter_part_search'])
        test_args['formulaic_parts'] = test_args['formulaic_parts'].replace('%2B', '+')
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_single_charter_part_search_with_wildcard(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_single_charter_part_search_with_wildcard'])
        test_args['formulaic_parts'] = test_args['formulaic_parts'].replace('%2B', '+')
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_single_charter_part_search_with_wildcard_v_u(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_single_charter_part_search_with_wildcard_v_u'])
        test_args['formulaic_parts'] = test_args['formulaic_parts'].replace('%2B', '+')
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_fuzzy_charter_part_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_fuzzy_charter_part_search'])
        test_args['formulaic_parts'] = test_args['formulaic_parts'].replace('%2B', '+')
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        body = fake.load_request()
        self.search_response = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = self.search_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)

    @patch.object(Elasticsearch, "search")
    @patch.object(Search, 'lem_highlight_to_text')
    def test_fuzzy_v_to_u_search(self, mock_highlight, mock_search):
        test_args = copy(self.TEST_ARGS['test_fuzzy_v_to_u_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        body = fake.load_request()
        self.search_response = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = self.search_side_effect
        mock_highlight.side_effect = self.highlight_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_charter_part_search_no_q(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_charter_part_search_no_q'])
        test_args['formulaic_parts'] = test_args['formulaic_parts'].replace('%2B', '+')
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])
        sents = [{'sents': [Markup('<strong>Poenformel:</strong> Si quis vero, quod futurum esse non credo, aut ego ipse aut ulla opposita persona, quod fieri non credo, contra hanc donationem venire aut eam infringere temptaverit, inprimis in iram dei incurrat, et a liminibus aecclesiae extraneus efficiatur, et sit culpabilis in fisco auri uncias duo et argenti pondera quinque, et effectum, quod inchoavit, obtinere non valeat')]},
                 {'sents': [Markup('<strong>Stipulationsformel:</strong> Et haec traditio a nobis facta omni tempore firma et stabilis permaneat')]},
                 {'sents': [Markup('<strong>Poenformel:</strong> Si quis vero, quod fieri non credo, aut ego ipse aut ullus de hereditaribus meis contra hanc donationem facere volverit, inprimis iram dei et sancti Michahelis et omnium sanctorum eius incurrere pertimescat'),
                            Markup('<strong>Stipulationsformel:</strong> et haec carta a me facta omni tempore firma permaneat, stipulatione subnixa')]},
                 {'sents': [Markup('<strong>Poenformel:</strong> Et si quis ex eis vel de successoribus eorum de ipsis commutationibus quicquam inmutare vellet, ipsam rem, quam pro concanbio accepit, ammittat, et quod repetit, nihil evindicet'),
                            Markup('<strong>Stipulationsformel:</strong> sed presentes commutationes inter eos et successores eorum omni tempore firmae permaneant')]},
                 {'sents': [Markup('<strong>Stipulationsformel:</strong> sed in evum et inconvulsum valeat permanere')]},
                 {'sents': [Markup('<strong>Stipulationsformel:</strong> et haec donacio a mae facta omni tempore firma et stabilis permaneat, stipulacione subnixa')]},
                 {'sents': [Markup('<strong>Poenformel:</strong> Si quis vero, quod futurum esse non credo, si ego ipse aut ullus [de heredibus] aut proheredibus meis, quislibet ulla opposita persona, qui contra hanc donacionem venire conaverit aut eam infrangere temptaverit'),
                            Markup('<strong>Stipulationsformel:</strong> et quod repetit, ullum umquam tempore vindicare [non] valeat, sed presens tradicio omni tempore firma permaneat cum stipulacione subnixa')]},
                 {'sents': [Markup('<strong>Poenformel:</strong> Si quis autem contra hanc cartam tradicionis, quelibet opposita persona, contraire volverit, iram dei omnipotentis incurrat, et causam [habeat] cum beato Mihhaelo archangelo et partem cum Iuda traditore'),
                            Markup('<strong>Stipulationsformel:</strong> et carta haec nihilominus firma permaneat')]},
                 {'sents': [Markup('<strong>Poenformel:</strong> Si quis vero, quod futurum esse non credo, aut ego ipse aut ullus de heredibus seu proheredibus meis, quislibet ulla opposita persona, qui contra hanc tradicionem venire conaverit aut eam infrangere temptaverit'),
                            Markup('<strong>Stipulationsformel:</strong> et quod repetit, nullatenus evindicare valeat, sed presens tradicio omni tempore firma permaneat cum stipulacione subnixa')]},
                 {'sents': [Markup('<strong>Poenformel:</strong> ut nullus obtineat ei effectum hoc mutare vel refragare'),
                            Markup('<strong>Stipulationsformel:</strong> sed presens ista tradicio stabilis in evum permaneat')]}]
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual[:10]])

    @patch.object(Elasticsearch, "search")
    def test_forgery_only(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_forgery_only'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_forgery_exclude(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_forgery_exclude'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.side_effect = cycle([resp, aggs])
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])


class TestErrors(Formulae_Testing):
    def test_404(self):
        with self.client as c:
            response = c.get('/trying.php', follow_redirects=True)
            self.assertEqual(response.status_code, 404, 'A URL that does not exist on the server should return a 404.')

    def test_UnknownCollection_error_mv(self):
        with self.client as c:
            response = c.get('/corpus_m/urn:cts:formulae:buendner', follow_redirects=True)
            self.assertEqual(response.status_code, 404, 'An Unknown Collection Error should also return 404.')
            self.assertIn("errors::unknown_collection.html", [x[0].name for x in self.templates])

    def test_UnknownCollection_error(self):
        with self.client as c:
            response = c.get('/corpus/urn:cts:formulae:buendner', follow_redirects=True)
            self.assertEqual(response.status_code, 404, 'An Unknown Collection Error should also return 404.')
            self.assertIn("errors::unknown_collection.html", [x[0].name for x in self.templates])

    def test_500(self):
        with self.client as c:
            expected = "<h4>{}</h4><p>{}</p>".format(_('Ein unerwarteter Fehler ist aufgetreten'),
                                                     _('Der Administrator wurde benachrichtigt. Bitte entschuldigen Sie die Unannehmlichkeiten!'))
            response = c.get('/500', follow_redirects=True)
            self.assertEqual(response.status_code, 500, 'Should raise 500 error.')
            self.assertIn(expected, response.get_data(as_text=True))


def rebuild_search_mock_files(url_base="http://127.0.0.1:5000"):
    """Automatically rebuilds the mock files for the ElasticSearch tests.
    This requires that a local version of the app is running at url_base and that the config variable
    SAVE_REQUESTS is set to True.

    :param url_base: The base url at which the app is currently running.
    """
    import requests
    test_args = TestES.TEST_ARGS.items()
    for k, v in test_args:
        url_ext = []
        for x, y in v.items():
            url_ext.append('{}={}'.format(x, y))
        url = '{}/search/results?source=advanced&sort=urn&{}'.format(url_base, '&'.join(url_ext))
        r = requests.get(url)
        if r.status_code != 200:
            print(url + ' did not succeed. Status code: ' + str(r.status_code))
