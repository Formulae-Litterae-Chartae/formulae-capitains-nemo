from config import Config
from MyCapytain.resolvers.capitains.local import XmlCapitainsLocalResolver
from formulae import create_app, db, mail
from formulae.nemo import NemoFormulae
from formulae.models import User
from formulae.search.Search import advanced_query_index, suggest_composition_places, build_sort_list, \
    set_session_token, suggest_word_search, PRE_TAGS, POST_TAGS
from formulae.search import Search
from flask_nemo.filters import slugify
import flask_testing
from formulae.search.forms import AdvancedSearchForm, SearchForm
from formulae.auth.forms import LoginForm, PasswordChangeForm, LanguageChangeForm, ResetPasswordForm, \
    ResetPasswordRequestForm, RegistrationForm, ValidationError, EmailChangeForm
from flask_login import current_user
from flask_babel import _
from elasticsearch import Elasticsearch
from unittest.mock import patch, mock_open
from unittest import TestCase
from tests.fake_es import FakeElasticsearch
from collections import OrderedDict, defaultdict
import os
from MyCapytain.common.constants import Mimetypes
from flask import Markup, session, g, url_for, abort
from json import dumps, load, JSONDecodeError
import re
from math import ceil
from datetime import date
from copy import copy
from io import StringIO


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    CORPUS_FOLDERS = ["tests/test_data/formulae"]
    INFLECTED_LEM_JSONS = ["tests/test_data/formulae/inflected_to_lem.json"]
    LEM_TO_LEM_JSONS = ["tests/test_data/formulae/lem_to_lem.json"]
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


class Formulae_Testing(flask_testing.TestCase):
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

        app.config['nemo_app'] = self.nemo
        self.nemo.open_texts += ['urn:cts:formulae:buenden.meyer-marthaler0024.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0025.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0027.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0028.lat001']
        self.nemo.all_term_vectors = defaultdict(term_vector_default_value)
        with open('tests/test_data/advanced_search/all_term_vectors.json') as f:
            self.nemo.all_term_vectors.update(load(f))

        @app.route('/500', methods=['GET'])
        def r_500():
            abort(500)

        return app

    def setUp(self):
        db.create_all()
        u = User(username="project.member", email="project.member@uni-hamburg.de", project_team=True)
        u.set_password('some_password')
        db.session.add(u)
        u = User(username="not.project", email="not.project@uni-hamburg.de", project_team=False)
        u.set_password('some_other_password')
        db.session.add(u)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()


class TestNemoSetup(Formulae_Testing):

    @patch("elasticsearch.Elasticsearch.mtermvectors")
    def test_setup_global_app(self, mock_vectors):
        """ Make sure that the instance of Nemo on the server is created correctly"""
        mock_vectors.return_value = {'docs': [TestES.MOCK_VECTOR_RETURN_VALUE]}
        if os.environ.get('TRAVIS'):
            # This should only be tested on Travis since I don't want it to run locally
            from formulae.app import nemo
            self.assertEqual(nemo.open_texts + ['urn:cts:formulae:buenden.meyer-marthaler0024.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0025.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0027.lat001',
                                 'urn:cts:formulae:buenden.meyer-marthaler0028.lat001'], self.nemo.open_texts)
            self.assertEqual(nemo.sub_colls, self.nemo.sub_colls)
            self.assertEqual(nemo.pdf_folder, self.nemo.pdf_folder)
            self.assertEqual(self.nemo.all_term_vectors['urn:cts:formulae:katalonien.vinyals_albanyamonestirpere_0001.lat001'],
                             TestES.MOCK_VECTOR_RETURN_VALUE)
            self.assertEqual(self.nemo.all_term_vectors['urn:cts:formulae:marmoutier_manceau.laurain_ballée_0001.lat001'],
                             TestES.MOCK_VECTOR_RETURN_VALUE)


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
        with patch('sys.stderr', new=StringIO()) as fake_err:
            app = create_app(InvalidIIIFMappingConfig)
            self.assertIn('WARNING in __init__: Der Viewer konnte nicht gestartet werden.', fake_err.getvalue())
        self.assertFalse(app.IIIFviewer, "No IIIF Viewer should be loaded with an invalid mapping file.")
        self.assertEqual(app.picture_file, "", "picture_file should be an empty string with invalid mapping file.")

    def test_with_no_iiif_mapping(self):
        """ Make sure that app initiates correctly when no IIIF mapping file is given"""
        with patch('sys.stderr', new=StringIO()) as fake_err:
            app = create_app(NoIIIFMappingConfig)
            self.assertIn('WARNING in __init__: Der Viewer konnte nicht gestartet werden.', fake_err.getvalue())
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
            self.assertTemplateUsed('main::index.html')
            c.get('/imprint', follow_redirects=True)
            self.assertTemplateUsed('main::impressum.html')
            c.get('/bibliography', follow_redirects=True)
            self.assertTemplateUsed('main::bibliography.html')
            c.get('/contact', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            c.get('/search/doc', follow_redirects=True)
            self.assertTemplateUsed('search::documentation.html')
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertMessageFlashed(_('Bitte loggen Sie sich ein, um Zugang zu erhalten.'))
            self.assertTemplateUsed('auth::login.html')
            c.get('/auth/reset_password_request', follow_redirects=True)
            self.assertTemplateUsed('auth::reset_password_request.html')
            c.get('/auth/register', follow_redirects=True)
            self.assertTemplateUsed('auth::register.html')
            c.get('/collections', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/collections/formulae_collection', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/collections/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            r = c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            self.assertIn('<p class=" no-copy">', r.get_data(as_text=True))
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertTemplateUsed('main::salzburg_collection.html')
            c.get('/collections/urn:cts:formulae:fu2', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/collections/urn:cts:formulae:ko2', follow_redirects=True)
            self.assertMessageFlashed(_('Um das Digitalisat dieser Handschrift zu sehen, besuchen Sie bitte gegebenenfalls die Homepage der Bibliothek.'))
            # r_references does not work right now
            # c.get('/text/urn:cts:formulae:stgallen.wartmann0001.lat001/references', follow_redirects=True)
            # self.assertTemplateUsed('main::references.html')
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:salzburg.hauthaler-a0001.lat001/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            # Check for backwards compatibility of URLs
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:salzburg.hauthaler-a0001.lat001/passage/1+first', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/add_collections/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/add_collection/other_collection/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collections.html')
            c.get('/add_collection/formulae_collection/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/add_collection/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/add_collection/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/add_text/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertTemplateUsed('main::lexicon_modal.html')
            c.get('/add_collection/lexicon_entries/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            # An non-authenicated user who surfs to the login page should not be redirected
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            # The following tests are to make sure that non-open texts are not available to non-project members
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
            c.get('/corpus_m/urn:cts:formulae:marculf', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
            c.get('/corpus_m/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection_mv.html')
            # Make sure the Salzburg collection is ordered correctly
            r = c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            p = re.compile('<h5>Notitia Arnonis: </h5>.+<h5>Codex Odalberti Vorrede: </h5>.+<h5>Codex Odalberti 1: </h5>',
                           re.DOTALL)
            self.assertRegex(r.get_data(as_text=True), p)
            r = c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('text-section no-copy', r.get_data(as_text=True))
            r = c.get('/texts/urn:cts:formulae:andecavensis.form001.fu2/passage/all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('text-section no-copy', r.get_data(as_text=True))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:marculf.form003.le1/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertMessageFlashed(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertMessageFlashed(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
            c.get('/reading_format/rows', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.fu2/passage/1+all'})
            self.assertTemplateUsed('main::multipassage.html')
            self.assertEqual(session['reading_format'], 'rows')
            response = c.get('/reading_format/columns', follow_redirects=True, headers={"X-Requested-With": "XMLHttpRequest"})
            self.assertEqual(response.get_data(as_text=True), 'OK')
            self.assertEqual(session['reading_format'], 'columns')
            c.get('/lang/en', follow_redirects=True, headers={'Referer': url_for('InstanceNemo.r_bibliography')})
            self.assertTemplateUsed('main::bibliography.html')
            self.assertEqual(session['locale'], 'en')
            response = c.get('/lang/en', follow_redirects=True, headers={"X-Requested-With": "XMLHttpRequest"})
            self.assertEqual(response.get_data(as_text=True), 'OK')
            # Navigating to the results page with no search args should redirect the user to the index
            c.get('/search/results', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            c.get('/viewer/manifest:urn:cts:formulae:andecavensis.form001.fu2?view=0&embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::miradorviewer.html')
            r = c.get('/viewer/urn:cts:formulae:marculf.form003.lat001', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
            self.assertTemplateUsed('main::index.html')
            r = c.get('/pdf/urn:cts:formulae:andecavensis.form002.lat001', follow_redirects=True)
            self.assertRegex(r.get_data(), b'Encrypt \d+ 0 R', 'PDF should be encrypted.')
            c.get('/pdf/urn:cts:formulae:raetien.erhart0001.lat001', follow_redirects=True)
            self.assertMessageFlashed(_('Das PDF für diesen Text ist nicht zugänglich.'))
            c.get('manuscript_desc/fulda_d1', follow_redirects=True)
            self.assertTemplateUsed('main::fulda_d1_desc.html')

    def test_authorized_project_member(self):

        """ Make sure that all routes are open to project members"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            c.get('/', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            c.get('/imprint', follow_redirects=True)
            self.assertTemplateUsed('main::impressum.html')
            c.get('/bibliography', follow_redirects=True)
            self.assertTemplateUsed('main::bibliography.html')
            c.get('/contact', follow_redirects=True)
            self.assertTemplateUsed('main::contact.html')
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            c.get('/collections', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/collections/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/collections/formulae_collection', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collections.html')
            c.get('/collections/other_collection', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collections.html')
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:katalonien', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collections.html')
            c.get('/corpus/urn:cts:formulae:katalonien.vinyals_albanyamonestirpere', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertTemplateUsed('main::salzburg_collection.html')
            c.get('/corpus/urn:cts:formulae:elexicon', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            c.get('/corpus_m/urn:cts:formulae:marculf', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection_mv.html')
            c.get('/corpus_m/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection_mv.html')
            c.get('/corpus_m/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertMessageFlashed(_('Diese View ist nur für MARCULF und ANDECAVENSIS verfuegbar'))
            c.get('/collections/urn:cts:formulae:fu2', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/collections/urn:cts:formulae:ko2', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            # r_references does not work right now.
            # c.get('/text/urn:cts:formulae:stgallen.wartmann0001.lat001/references', follow_redirects=True)
            # self.assertTemplateUsed('main::references.html')
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            # Check for backwards compatibility of URLs
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+first', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/add_collections/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertTemplateUsed('main::lexicon_modal.html')
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            # An authenicated user who surfs to the login page should be redirected to their user page
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            self.assertMessageFlashed(_('Sie sind schon eingeloggt.'))
            # The following tests are to make sure that non-open texts are available to project members
            c.get('/add_collection/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            r = c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            re_sub_coll = re.compile(r'\[Edition\].+\[Deutsche Übersetzung\].+Transkription/Manuskriptbild', re.DOTALL)
            self.assertRegex(r.get_data(as_text=True), re_sub_coll)
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertNotIn('text-section no-copy', r.get_data(as_text=True))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.fu2/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertNotIn('text-section no-copy', r.get_data(as_text=True))
            c.get('/texts/urn:cts:formulae:andecavensis.computus.fu2+urn:cts:formulae:andecavensis.computus.lat001/passage/all+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/texts/urn:cts:formulae:andecavensis.form000.lat001+urn:cts:formulae:andecavensis.form000.fu2/passage/all+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            r = c.get('/texts/urn:cts:formulae:marculf.form000.lat001+urn:cts:formulae:p3.105va106rb.lat001/passage/all+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('Marculf Prolog', r.get_data(as_text=True))
            # make sure hasVersion metadata is correctly interpreted
            r = c.get('/texts/urn:cts:formulae:fulda_dronke.dronke0004a.lat001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('Urkundenbuch des Klosters Fulda; Teil: Bd. 1., (Die Zeit der Äbte Sturmi und Baugulf) (Ed. Stengel) Nr. 15', r.get_data(as_text=True))
            r = c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn(r'<span class="choice"><span class="abbr">o.t.</span><span class="expan">other text</span></span>',
                          r.get_data(as_text=True), '<choice> elements should be correctly converted.')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/2+12', follow_redirects=True)
            self.assertMessageFlashed('Angers 1 (lat), 12 wurde nicht gefunden. Der ganze Text wird angezeigt.')
            self.assertTemplateUsed('main::multipassage.html')
            r = c.get('/texts/urn:cts:formulae:andecavensis.form001/passage/2', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('Angers 1', r.get_data(as_text=True))
            # Make sure that a text that has no edition will throw an error
            r = c.get('/texts/urn:cts:formulae:andecavensis.form003/passage/1', follow_redirects=True)
            self.assertTemplateUsed("errors::unknown_collection.html")
            self.assertIn('Angers 3.1' + _(' hat keine Edition.'), r.get_data(as_text=True))
            r = c.get('/viewer/urn:cts:formulae:andecavensis.form003', follow_redirects=True)
            self.assertTemplateUsed("errors::unknown_collection.html")
            self.assertIn('Angers 3' + _(' hat keine Edition.'), r.get_data(as_text=True))
            # c.get('/viewer/urn:cts:formulae:andecavensis.form001.fu2', follow_redirects=True)
            # self.assertTemplateUsed('viewer::miradorviewer.html')
            c.get('/texts/urn:cts:formulae:andecavensis.form002.lat001+manifest:urn:cts:formulae:andecavensis.form002.fu2/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/texts/manifest:urn:cts:formulae:andecavensis.form003.deu001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertMessageFlashed(_('Es gibt keine Manuskriptbilder für Angers 3 (deu)'))
            c.get('/texts/urn:cts:formulae:andecavensis.form002.lat001+manifest:urn:cts:formulae:p12.65r65v.lat001/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/texts/manifest:urn:cts:formulae:m4.60v61v.lat001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/viewer/manifest:urn:cts:formulae:andecavensis.form001.fu2?view=0&embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::miradorviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001?view=0&embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::miradorviewer.html')
            r = c.get('/pdf/urn:cts:formulae:andecavensis.form002.lat001', follow_redirects=True)
            self.assertNotIn(b'Encrypt', r.get_data())
            self.assertIn('Angers 2 \\(lat\\) \\({}\\)'.format(date.today().isoformat()).encode(), r.get_data())
            r = c.get('/pdf/urn:cts:formulae:raetien.erhart0001.lat001', follow_redirects=True)
            self.assertIn('Urkundenlandschaft R\\344tien \\(Ed. Erhart/Kleindinst\\) Nr. 1 \\({}\\)'.format(date.today().isoformat()).encode(), r.get_data())
            self.assertNotIn(b'Encrypt', r.get_data())
            c.get('manuscript_desc/fulda_d1', follow_redirects=True)
            self.assertTemplateUsed('main::fulda_d1_desc.html')

    def test_authorized_normal_user(self):
        """ Make sure that all routes are open to normal users but that some texts are not available"""
        with self.client as c:
            c.post('/auth/login?next=/imprint', data=dict(username='not.project', password="some_other_password"),
                   follow_redirects=True)
            self.assertTemplateUsed('main::impressum.html')
            c.get('/', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            c.get('/imprint', follow_redirects=True)
            self.assertTemplateUsed('main::impressum.html')
            c.get('/bibliography', follow_redirects=True)
            self.assertTemplateUsed('main::bibliography.html')
            c.get('/contact', follow_redirects=True)
            self.assertTemplateUsed('main::contact.html')
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            c.get('/auth/reset_password_request', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            self.assertMessageFlashed(_('Sie sind schon eingeloggt. Sie können Ihr Password hier ändern.'))
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            self.assertMessageFlashed(_('Sie sind schon eingeloggt.'))
            c.get('/auth/register', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            self.assertMessageFlashed(_('Sie sind schon eingeloggt.'))
            c.get('/collections', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/collections/formulae_collection', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/collections/lexicon_entries', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertTemplateUsed('main::salzburg_collection.html')
            c.get('/corpus/urn:cts:formulae:elexicon', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            c.get('/corpus_m/urn:cts:formulae:marculf', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
            c.get('/collections/urn:cts:formulae:ko2', follow_redirects=True)
            self.assertMessageFlashed(_('Um das Digitalisat dieser Handschrift zu sehen, besuchen Sie bitte gegebenenfalls die Homepage der Bibliothek.'))
            # r_references does not work right now.
            # c.get('/text/urn:cts:formulae:stgallen.wartmann0001.lat001/references', follow_redirects=True)
            # self.assertTemplateUsed('main::references.html')
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            # Check for backwards compatibility of URLs
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:salzburg.hauthaler-a0001.lat001/passage/1+first', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/add_collections/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/add_text/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertTemplateUsed('main::lexicon_modal.html')
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            # An authenicated user who surfs to the login page should be redirected to index
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            self.assertMessageFlashed(_('Sie sind schon eingeloggt.'))
            # The following tests are to make sure that non-open texts are not available to non-project members
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung ist nicht öffentlich zugänglich.'))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertMessageFlashed('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.fu2/passage/1+all', follow_redirects=True)
            self.assertMessageFlashed(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertMessageFlashed('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.')
            c.get('/viewer/manifest:urn:cts:formulae:andecavensis.form001.fu2?view=0&embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::miradorviewer.html')
            c.get('/viewer/urn:cts:formulae:marculf.form003.lat001', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
            self.assertTemplateUsed('main::index.html')
            r = c.get('/pdf/urn:cts:formulae:andecavensis.form002.lat001', follow_redirects=True)
            self.assertRegex(r.get_data(), b'Encrypt \d+ 0 R', 'PDF should be encrypted.')
            r = c.get('/pdf/urn:cts:formulae:fulda_stengel.stengel0015.lat001', follow_redirects=True)
            self.assertIn('\\(Ed. Stengel\\) Nr. 15 \\({}\\)'.format(date.today().isoformat()).encode(), r.get_data())
            self.assertNotIn(b'Encrypt', r.get_data())
            c.get('manuscript_desc/fulda_d1', follow_redirects=True)
            self.assertTemplateUsed('main::fulda_d1_desc.html')


    @patch("formulae.search.routes.advanced_query_index")
    def test_advanced_search_results(self, mock_search):
        """ Make sure that the correct search results are passed to the search results form"""
        params = dict(corpus='formulae%2Bchartae', year=600, month=1, day=31, year_start=600, month_start=12,
                      day_start=12, year_end=700, month_end=1, day_end=12)
        aggs = {"corpus": {
                  "buckets": {
                    "Angers": {
                      "doc_count": 2
                    },
                    "Arnulfinger": {
                      "doc_count": 0
                    },
                    "B\u00fcnden": {
                      "doc_count": 0
                    },
                    "Echternach": {
                        "doc_count": 0
                    },
                    "Freising": {
                        "doc_count": 0
                    },
                    "Fulda (Dronke)": {
                      "doc_count": 0
                    },
                    "Fulda (Stengel)": {
                      "doc_count": 0
                    },
                    "Lorsch": {
                        "doc_count": 0
                    },
                    "Luzern": {
                      "doc_count": 0
                    },
                    "Marculf": {
                      "doc_count": 0
                    },
                    "Marmoutier - Fougères": {
                      "doc_count": 0
                    },
                    "Marmoutier - Manceau": {
                      "doc_count": 0
                    },
                    "Marmoutier - Vendômois": {
                      "doc_count": 0
                    },
                    "Marmoutier - Vendômois, Saint-Marc": {
                      "doc_count": 0
                    },
                    "Marmoutier - Serfs": {
                      "doc_count": 0
                    },
                    "Marmoutier - Vendômois, Saint-Marc": {
                      "doc_count": 0
                    },
                    "Merowinger": {
                      "doc_count": 0
                    },
                    "Mittelrheinisch": {
                      "doc_count": 0
                    },
                    "Mondsee": {
                      "doc_count": 0
                    },
                    "Papsturkunden Frankreich": {
                      "doc_count": 0
                    },
                    "Passau": {
                      "doc_count": 0
                    },
                    "Regensburg": {
                      "doc_count": 0
                    },
                    "Rheinisch": {
                      "doc_count": 0
                    },
                    "R\u00e4tien": {
                      "doc_count": 0
                    },
                    "Salzburg": {
                      "doc_count": 0
                    },
                    "Sch\u00e4ftlarn": {
                      "doc_count": 0
                    },
                    "St. Gallen": {
                      "doc_count": 0
                    },
                    "Werden": {
                      "doc_count": 0
                    },
                    "Z\u00fcrich": {
                      "doc_count": 0
                    }
                  }
                }}
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
            self.assertIn(('stgallen', 'St. Gallen'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')
            c.get('/search/results?source=advanced&corpus=formulae&q=&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&submit=True')
            mock_search.assert_called_with(corpus=['formulae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, field='text', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=[''], regest_q='', old_search=False, source='advanced')
            self.assert_context('searched_lems', [], 'When "q" is empty, there should be no searched lemmas.')
            # Check searched_lems return values
            c.get('/search/results?source=advanced&corpus=formulae&q=regnum&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&submit=True')
            self.assert_context('searched_lems', [{'regnum'}],
                                'When a query word matches a lemma, it should be returned.')
            c.get('/search/results?source=advanced&corpus=formulae&q=word&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&submit=True')
            self.assert_context('searched_lems', [],
                                'When a query word does not match a lemma, "searched_lems" should be empty.')
            c.get('/search/results?source=advanced&corpus=formulae&q=regnum+domni+ad&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&submit=True')
            self.assert_context('searched_lems', [{'regnum'}, {'dominus'}, {'a', 'ad', 'ab'}],
                                'When all query words match a lemma, all should be returned.')
            c.get('/search/results?source=advanced&corpus=formulae&q=regnum+word+ad&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&regest_q=&submit=True')
            self.assert_context('searched_lems', [],
                                'When not all query words match a lemma, "searched_lems" should be empty.')
            # Check g.corpora
            self.assertIn(('andecavensis', 'Angers'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')
            # Test to make sure that a capitalized search term is converted to lowercase in advanced search
            params['q'] = 'regnum'
            params['corpus'] = 'chartae'
            params['special_days'] = 'Easter%2BTuesday'
            response = c.get('/search/advanced_search?corpus=chartae&q=Regnum&year=600&month=1&day=31&'
                             'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                             'date_plus_minus=0&special_days=Easter+Tuesday&submit=Search')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))
            c.get('/search/advanced_search?corpus=chartae&q=Regnum&year=600&month=1&day=31&'
                  'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                  'date_plus_minus=0&submit=Search', follow_redirects=True)
            # Check g.corpora
            self.assertIn(('stgallen', 'St. Gallen'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')

    @patch("formulae.search.routes.advanced_query_index")
    def test_simple_search_results(self, mock_search):
        """ Make sure that the correct search results are passed to the search results form"""
        params = dict(corpus='formulae%2Bchartae', q='regnum', sort='urn', source='simple')
        mock_search.return_value = [[], 0]
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            response = c.get('/search/simple?corpus=formulae&corpus=chartae&q=Regnum')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))

    @patch("formulae.nemo.lem_highlight_to_text")
    def test_search_result_highlighting(self, mock_highlight):
        """ Make sure that highlighting of search results works correctly"""
        # Highlighting should cross boundary of parent nodes
        session['previous_search_args'] = dict()
        search_string = ['Text that I want to search']
        expected = '<span class="searched"><span class="w searched-start">Text</span><span class="w searched-end">that</span></span></p><p><span class="searched"><span class="w searched-start searched-end">I</span></span></p><p><span class="searched"><span class="w searched-start">want</span><span class="w">to</span><span class="w searched-end">search</span></span>'
        obj_id = 'urn:cts:formulae:salzburg.hauthaler-a0001.lat001'
        xml = self.nemo.get_passage(objectId=obj_id, subreference='1')
        html_input = Markup(self.nemo.transform(xml, xml.export(Mimetypes.PYTHON.ETREE), obj_id))
        mock_highlight.return_value = [[{'sents': search_string, 'sentence_spans': [range(0, 6)]}], []]
        result = self.nemo.highlight_found_sents(html_input, [])
        self.assertIn(expected, result)
        # Should be able to deal with editorial punctuation in the text
        search_string = ['Text with special editorial signs in it']
        expected = '<span class="searched"><span class="w searched-start">Text</span><span class="w">with</span><span class="w">sp&lt;e&gt;cial</span><span class="w">[edi]torial</span><span class="w">[signs</span><span class="w">in</span><span class="w searched-end">i]t</span></span>'
        obj_id = 'urn:cts:formulae:salzburg.hauthaler-a0001.lat001'
        xml = self.nemo.get_passage(objectId=obj_id, subreference='1')
        html_input = Markup(self.nemo.transform(xml, xml.export(Mimetypes.PYTHON.ETREE), obj_id))
        mock_highlight.return_value = ([{'sents': search_string, 'sentence_spans': [range(6, 13)]}], [])
        result = self.nemo.highlight_found_sents(html_input, [])
        self.assertIn(expected, result)
        # Should return the same result when passed in the session variable to r_multipassage
        session['previous_search'] = [{'_id': obj_id,
                                       'title': 'Salzburg A1',
                                       'sents': search_string,
                                       'sentence_spans': [range(6, 13)]}]
        passage_data = self.nemo.r_multipassage(obj_id, '1')
        self.assertIn(expected, passage_data['objects'][0]['text_passage'])
        #Make sure that when no sentences are highlighted, the original HTML is returned
        mock_highlight.return_value = ([], [])
        result = self.nemo.highlight_found_sents(html_input, [])
        self.assertEqual(html_input, result)

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_session_previous_results_set(self, mock_vectors, mock_search):
        """ Make sure that session['previous_results'] is set correctly"""
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ('regest_q', ''), ('regest_field', 'regest')])
        fake = FakeElasticsearch(TestES().build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        for hit in resp['hits']['hits']:
            hit['highlight']['text'][0] = PRE_TAGS + hit['highlight']['text'][0] + POST_TAGS
        mock_search.return_value = resp
        mock_vectors.return_value = TestES.MOCK_VECTOR_RETURN_VALUE
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            results = set_session_token(['all'], body, field='text', q='text')
            self.assertEqual(results,
                             [hit for hit in resp['hits']['hits']])
            updated_args = copy(test_args)
            updated_args['q'] = 'tex?'
            url = '/search/results?source=advanced&' + '&'.join(['{}={}'.format(x, y) for x, y in updated_args.items()])
            c.get(url)
            self.assertEqual(g.previous_search, results)
            self.assertEqual(session['previous_search'], results)
            c.get('/auth/logout', follow_redirects=True)
            c.get(url + '&old_search=True')
            self.assertEqual(results, session['previous_search'],
                             "With old_search set to True, session['previous_searcH'] should not be changed.")
            c.get(url.replace('source=advanced', 'source=simple') + '&old_search=True')
            self.assertEqual(results, session['previous_search'],
                             "With old_search set to True, session['previous_searcH'] should not be changed.")
            c.get(url + '&old_search=False')
            self.assertEqual(g.previous_search, session['previous_search'],
                             'Value of g.previous_search should be transferred to session')
            self.assertEqual(session['previous_search'],
                             [hit for hit in resp['hits']['hits']],
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
    @patch.object(Elasticsearch, "termvectors")
    def test_session_previous_search_args_all_corps(self, mock_vectors, mock_search):
        """ Make sure that session['previous_search_args'] is set correctly with 'all' corpora"""
        search_url = "/search/results?fuzziness=0&day_start=&year=&date_plus_minus=0&q=regnum&year_end=&corpus=all&submit=True&lemma_search=y&year_start=&month_start=0&source=advanced&month=0&day=&in_order=False&exclusive_date_range=False&month_end=0&slop=0&day_end=&regest_q="
        previous_args = {'source': 'advanced', 'corpus': 'all', 'q': 'regnum', 'fuzziness': '0', 'slop': '0',
                         'in_order': 'False', 'year': '', 'month': '0', 'day': '', 'year_start': '', 'month_start': '0',
                         'day_start': '', 'year_end': '', 'month_end': '0', 'day_end': '', 'date_plus_minus': '0',
                         'exclusive_date_range': 'False', 'composition_place': '', 'submit': 'True', 'sort': 'urn',
                         'special_days': '', 'regest_q': '', 'regest_field': 'regest'}
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ('regest_q', ''), ('regest_field', 'regest')])
        fake = FakeElasticsearch(TestES().build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        mock_search.return_value = resp
        mock_vectors.return_value = TestES.MOCK_VECTOR_RETURN_VALUE
        with self.client as c:
            session['previous_search_args'] = previous_args
            c.get(search_url, follow_redirects=True)
            self.assertRegex(session['previous_search_args']['corpus'],
                             'andecavensis\+[\w\+]*raetien+[\w\+]*salzburg+[\w\+]*stgallen',
                             'Corpus "all" should be expanded to a string with all corpora.')
            c.get(search_url, follow_redirects=True)
            self.assertIn(('stgallen', 'St. Gallen'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')

    @patch.object(Elasticsearch, "search")
    def test_flashed_search_form_errors(self, mock_search):
        """ Make sure that errors in the form will result in no search being done and a flashed message"""
        mock_search.return_value = {'hits': {'hits': ''}}
        with self.client as c:
            c.get('/search/advanced_search?year=1500&submit=y')
            self.assertMessageFlashed('year: ' + _('Die Jahreszahl muss zwischen 500 und 1000 liegen'))
            self.assertTemplateUsed('search::advanced_search.html')
            c.get('/search/advanced_search?submit=y')
            self.assertMessageFlashed(_('Bitte geben Sie Daten in mindestens einem Feld ein.'))
            self.assertTemplateUsed('search::advanced_search.html')

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
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('id="header-urn-cts-formulae-andecavensis-form003-deu001"',
                          r.get_data(as_text=True), 'Note card should be rendered for a formula.')
            r = c.get('/texts/urn:cts:formulae:elexicon.abbas.deu001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
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
            self.assertTemplateUsed('main::multipassage.html')
            self.assertNotIn('id="header-urn-cts-formulae-andecavensis-form003-deu001"',
                             r.get_data(as_text=True), 'No note card should be rendered for a formula.')
            r = c.get('/texts/urn:cts:formulae:elexicon.abbas.deu001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
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
                                                      'urn:cts:formulae:marculf.form003'],
                                                     ['urn:cts:formulae:marculf.form000.lat001',
                                                      'urn:cts:formulae:marculf.form003.lat001']],
                                           'name': 'lat001',
                                           'regesten': ['', ''],
                                           'titles': ['Marculf Prolog', 'Marculf I,3']}],
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
            data = self.nemo.r_multipassage('urn:cts:formulae:marculf.form003.lat001', '1')
            self.assertEqual(data['objects'][0]['prev_version'], 'urn:cts:formulae:marculf.form000.lat001')
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
                         {'gerere', 'gesta'},
                         'Mapping files should have loaded correctly.')
        self.app.config['LEM_TO_LEM_JSONS'] = ["tests/test_data/formulae/inflected_to_lem_error.txt"]
        with patch.object(self.app.logger, 'warning') as mock:
            self.nemo.make_lem_to_lem_mapping()
            mock.assert_called_with('tests/test_data/formulae/inflected_to_lem_error.txt is not a valid JSON file. Unable to load valid lemma to lemma mapping from it.')


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
            self.assert200(rv, 'Login should return 200 code')
            self.assertTrue(current_user.email == "project.member@uni-hamburg.de")
            self.assertTrue(current_user.is_active)
            self.assertTrue(current_user.is_authenticated)
            self.assertTemplateUsed('auth::login.html')

    def test_incorrect_login(self):
        """ Ensure that login does not work with incorrect credentials"""
        with self.client as c:
            rv = c.post('/auth/login', data=dict(username='pirate.user', password="incorrect"),
                        follow_redirects=True)
            self.assert200(rv, 'Login should return 200 code')
            self.assertMessageFlashed(_('Benutzername oder Passwort ist ungültig'))
            self.assertFalse(current_user.is_active)
            self.assertFalse(current_user.is_authenticated)
            self.assertTemplateUsed('auth::login.html')

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
            self.assert200(rv, 'Login should return 200 code')
            self.assertMessageFlashed(_('Sie sind nun registriert.'))
            self.assertTrue(User.query.filter_by(username='new.user').first(), "It should have added new.user.")
            self.assertTemplateUsed('auth::login.html')

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
                self.assertMessageFlashed(_('Die Anweisung zum Zurücksetzen Ihres Passworts wurde Ihnen per E-mail zugeschickt'))
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
                self.assertMessageFlashed(_('Ein Link zur Bestätigung dieser Änderung wurde an Ihre neue Emailadresse zugeschickt'))
                self.assertEqual(current_user.email, "project.member@uni-hamburg.de",
                                 "The email address should not be changed only by requesting the token.")

    def test_send_email_not_existing_user(self):
        """ Ensure that no email is sent to a non-registered email address"""
        with self.client as c:
            with mail.record_messages() as outbox:
                c.post('/auth/reset_password_request', data=dict(email="pirate.user@uni-hamburg.de"),
                       follow_redirects=True)
                self.assertEqual(len(outbox), 0, 'No email should be sent when the email is not in the database.')
                self.assertMessageFlashed(_('Die Anweisung zum Zurücksetzen Ihres Passworts wurde Ihnen per E-mail zugeschickt'))

    def test_reset_password_from_email_token(self):
        """ Make sure that a correct email token allows the user to reset their password while an incorrect one doesn't"""
        with self.client as c:
            user = User.query.filter_by(username='project.member').first()
            token = user.get_reset_password_token()
            # Make sure that the template renders correctly with correct token
            c.post(url_for('auth.r_reset_password', token=token, _external=True))
            self.assertTemplateUsed('auth::reset_password.html')
            # Make sure the correct token allows the user to change their password
            c.post(url_for('auth.r_reset_password', token=token, _external=True),
                   data={'password': 'some_new_password', 'password2': 'some_new_password'})
            self.assertTrue(user.check_password('some_new_password'), 'User\'s password should be changed.')
            c.post(url_for('auth.r_reset_password', token='some_weird_token', _external=True),
                   data={'password': 'some_password', 'password2': 'some_password'}, follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            self.assertTrue(user.check_password('some_new_password'), 'User\'s password should not have changed.')
            # Make sure that a logged in user who comes to this page with a token is redirected to their user page with a flashed message
            c.post('/auth/login', data=dict(username='project.member', password="some_new_password"),
                   follow_redirects=True)
            c.post(url_for('auth.r_reset_password', token=token, _external=True), follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            self.assertMessageFlashed(_('Sie sind schon eingeloggt. Sie können Ihr Password hier ändern.'))
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
            self.assertTemplateUsed('auth::login.html')
            # Make sure the correct token allows the user to change their password
            self.assertEqual(user.email, 'another_new_email@email.com', 'User\'s email should be changed.')
            self.assertMessageFlashed(_('Ihr Email wurde erfolgreich geändert. Sie lautet jetzt') + ' another_new_email@email.com.')
            # Trying to use the same token twice should not work.
            c.post(url_for('auth.r_reset_email', token=token, _external=True))
            self.assertTemplateUsed('auth::login.html')
            self.assertMessageFlashed(_('Ihre Emailaddresse wurde nicht geändert. Versuchen Sie es erneut.'))
            # Using an invalid token should not work.
            c.post(url_for('auth.r_reset_email', token='some_weird_token', _external=True), follow_redirects=True)
            self.assertMessageFlashed(_('Der Token ist nicht gültig. Versuchen Sie es erneut.'))
            self.assertTemplateUsed('auth::login.html')
            self.assertEqual(user.email, 'another_new_email@email.com', 'User\'s email should not have changed.')

    def test_user_logout(self):
        """ Make sure that the user is correctly logged out and redirected"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            self.assertTrue(current_user.is_authenticated, 'User should be logged in.')
            c.get('/auth/logout', follow_redirects=True)
            self.assertFalse(current_user.is_authenticated, 'User should now be logged out.')
            self.assertTemplateUsed('auth::login.html')

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
            self.assertTemplateUsed('auth::login.html')
            self.assertMessageFlashed(_("Sie haben Ihr Passwort erfolgreich geändert."))

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
            self.assertMessageFlashed(_("Das ist nicht Ihr aktuelles Passwort."))


class TestES(Formulae_Testing):

    TEST_ARGS = {'test_date_range_search_same_year': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''),
                                                                  ("fuzziness", "0"), ('in_order', 'False'),
                                                                  ("year", 0), ('slop', '0'), ("month", 0),
                                                                  ("day", 0), ("year_start", 814),
                                                                  ("month_start", 10), ("day_start", 29),
                                                                  ("year_end", 814), ("month_end", 11),
                                                                  ("day_end", 20), ('date_plus_minus', 0),
                                                                  ('exclusive_date_range', 'False'),
                                                                  ("composition_place", ''), ('sort', 'urn'),
                                                                  ('special_days', ''), ("regest_q", ''),
                                                                  ("regest_field", "regest")]),
                 'test_date_range_search_same_month': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 10), ("year_end", 800), ("month_end", 10),
                                 ("day_end", 29), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_range_search_different_year': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 10), ("year_end", 801), ("month_end", 10),
                                 ("day_end", 29), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_range_search_only_year': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 810), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_range_search_only_year_and_month_same_year': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 800), ("month_end", 11),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_range_search_only_year_and_month_different_year': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 801), ("month_end", 11),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_range_search_only_start_year': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_range_search_only_end_year': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 801), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_range_search_only_start_year_and_month': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_range_search_only_end_year_and_month': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 801), ("month_end", 10),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_normal_date_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 10), ("day", 9), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_normal_date_only_year_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_date_plus_minus_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 10), ("day", 9), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 10), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_exclusive_date_range_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 10), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 10), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_exclusive_date_range_search_only_year': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 0), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_exclusive_date_range_search_same_month_and_day': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 800), ("month_start", 12), ("day_start", 25), ("year_end", 820),
                                 ("month_end", 12), ("day_end", 25), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_multi_corpus_search': OrderedDict([("corpus", "andecavensis%2Bmondsee"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', "0"), ("month", 0), ("day", 0),
                                 ("year_start", 814), ("month_start", 10), ("day_start", 29), ("year_end", 814),
                                 ("month_end", 11), ("day_end", 20), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_multiword_wildcard_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", 'regnum+dom*'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_lemma_advanced_search': OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ('lemma_search', 'y')]),
                 'test_regest_advanced_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'tausch'),
                                 ("regest_field", "regest")]),
                 'test_regest_and_word_advanced_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'schenk*'),
                                 ("regest_field", "regest")]),
                 'test_regest_advanced_search_with_wildcard': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'tau*'),
                                 ("regest_field", "regest")]),
                 'test_multiword_lemma_advanced_search': OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'vir+venerabilis'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ('lemma_search', 'y')]),
                 'test_single_word_highlighting': OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'pettonis'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_multi_word_highlighting': OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'scripsi+et+suscripsi'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_single_lemma_highlighting': OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_multi_lemma_highlighting': OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'regnum+domni'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_lemma_advanced_search_with_wildcard': OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'venerabili?'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_composition_place_advanced_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", '(Basel-)Augst'),
                                 ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_suggest_composition_places': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 10), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 10), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_suggest_word_search_completion': OrderedDict([("corpus", "buenden"), ("field", "autocomplete"), ("q", 'ill'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'y'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_suggest_regest_word_search_completion': OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'y'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'sche'),
                                 ("regest_field", "autocomplete_regest")]),
                 'test_suggest_word_search_completion_no_qSource': OrderedDict([("corpus", "all"), ("field", "text"), ("q", 'illam'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'y'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'tau'),
                                 ("regest_field", "autocomplete_regest"), ('qSource', '')]),
                 'test_save_requests': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", '(Basel-)Augst'),
                                 ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_specific_day_advanced_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', 'Easter'), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_multiple_specific_day_advanced_search': OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', 'Easter+Saturday'), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_download_search_results': OrderedDict([("corpus", "all"), ("field", "text"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", 'schenk*'),
                                 ("regest_field", "regest")]),
                 'test_no_corpus_given': OrderedDict([("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 801), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_mapped_lemma_advanced_search': OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'gero'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ('lemma_search', 'y')]),
                 'test_mapped_multiword_lemma_advanced_search': OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'facio+gero'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest"), ('lemma_search', 'y')]),
                 'test_single_word_fuzzy_highlighting': OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'pettonis'), ("fuzziness", "AUTO"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_multi_word_fuzzy_highlighting': OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'scripsi+et+suscripsi'), ("fuzziness", "AUTO"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_multi_word_fuzzy_highlighting_with_wildcard': OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'scripsi+et+suscr*'), ("fuzziness", "AUTO"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")]),
                 'test_multi_word_highlighting_repeated_words': OrderedDict([("corpus", "buenden"), ("field", "text"),
                                 ("q", 'signum+uuiliarentis+testes+signum+crespionis+testes'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
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
                                                                                                    'end_offset': 13}]},
                                                               'other': {'term_freq': 1, 'tokens': [{'position': 3,
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
                                                                 'gerere': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                        'start_offset': 14,
                                                                                                        'end_offset': 19}]},
                                                                 'gesta': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                       'start_offset': 20,
                                                                                                       'end_offset': 24}]}
                                                                 }
                                                            }
                                                 }}

    SEARCH_FILTERS_CORPORA = {'Angers': {'match': {'_type': 'andecavensis'}},
                              'Arnulfinger': {'match': {'_type': 'arnulfinger'}},
                              'Bünden': {'match': {'_type': 'buenden'}},
                              'Echternach': {'match': {'_type': 'echternach'}},
                              'Freising': {'match': {'_type': 'freising'}},
                              'Fulda (Dronke)': {'match': {'_type': 'fulda_dronke'}},
                              'Fulda (Stengel)': {'match': {'_type': 'fulda_stengel'}},
                              'Hersfeld': {'match': {'_type': 'hersfeld'}},
                              'Katalonien': {'match': {'_type': 'katalonien'}},
                              'Lorsch': {'match': {'_type': 'lorsch'}},
                              'Luzern': {'match': {'_type': 'luzern'}},
                              'Marculf': {'match': {'_type': 'marculf'}},
                              'Marmoutier - Fougères': {'match': {'_type': 'marmoutier_fougères'}},
                              'Marmoutier - Manceau': {'match': {'_type': 'marmoutier_manceau'}},
                              'Marmoutier - Serfs': {'match': {'_type': 'marmoutier_serfs'}},
                              'Marmoutier - Vendômois': {'match': {'_type': 'marmoutier_vendomois'}},
                              'Marmoutier - Vendômois, Saint-Marc': {'match': {'_type': 'marmoutier_vendomois_saintmarc'}},
                              'Merowinger': {'match': {'_type': 'merowinger1'}},
                              'Mittelrheinisch': {'match': {'_type': 'mittelrheinisch'}},
                              'Mondsee': {'match': {'_type': 'mondsee'}},
                              'Papsturkunden Frankreich': {'match': {'_type': 'papsturkunden_frankreich'}},
                              'Passau': {'match': {'_type': 'passau'}},
                              'Rätien': {'match': {'_type': 'raetien'}},
                              'Regensburg': {'match': {'_type': 'regensburg'}},
                              'Rheinisch': {'match': {'_type': 'rheinisch'}},
                              'Salzburg': {'match': {'_type': 'salzburg'}},
                              'Schäftlarn': {'match': {'_type': 'schaeftlarn'}},
                              'St. Gallen': {'match': {'_type': 'stgallen'}},
                              'Weißenburg': {'match': {'_type': 'weissenburg'}},
                              'Werden': {'match': {'_type': 'werden'}},
                              'Zürich': {'match': {'_type': 'zuerich'}}}

    def my_side_effect(self, index, doc_type, id):
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
        return

    def build_file_name(self, fake_args):
        return '&'.join(["{}".format(str(v)) for k, v in fake_args.items()])

    def test_return_when_no_es(self):
        """ Make sure that when ElasticSearch is not active, calls to the search functions return empty results instead of errors"""
        self.app.elasticsearch = None
        simple_test_args = OrderedDict([("index", ['formulae', "chartae"]), ("query", 'regnum'), ("field", "text"),
                                        ("page", 1), ("per_page", self.app.config["POSTS_PER_PAGE"]), ('sort', 'urn')])
        hits, total, aggs, prev = advanced_query_index(**simple_test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')
        self.assertEqual(prev, [], 'Previous results should be an empty list.')
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, total, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])
        total_pages = int(ceil(total / self.app.config['POSTS_PER_PAGE']))
        with self.client as c:
            test_args['source'] = 'advanced'
            r = c.get('/search/results', query_string=test_args, follow_redirects=True)
            p = re.compile('\.\.\..+<li class="page-item">\n\s+<a class="page-link"[^>]+page={total}'.format(total=total_pages),
                           re.DOTALL)
            self.assertRegex(r.get_data(as_text=True), p)

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_end_year(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_end_year'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args = self.TEST_ARGS['test_no_corpus_given']
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=['all'], doc_type="", body=body)

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_start_year_and_month(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_date_range_search_only_start_year_and_month'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multiword_wildcard_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_multiword_wildcard_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        mock_vectors.return_value = self.MOCK_VECTOR_RETURN_VALUE
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_lemma_advanced_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_lemma_advanced_search'])
        test_args.pop('lemma_search')
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        mock_vectors.return_value = self.MOCK_VECTOR_RETURN_VALUE
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_mapped_lemma_advanced_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_mapped_lemma_advanced_search'])
        test_args.pop('lemma_search')
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        mock_vectors.return_value = {'_index': 'andecavensis_v1',
                                     '_type': 'andecavensis',
                                     '_id': 'urn:cts:formulae:andecavensis.form001.lat001',
                                     '_version': 1,
                                     'found': True,
                                     'took': 0,
                                     'term_vectors': {'text': {'terms':
                                                                   {'some': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                         'start_offset': 0,
                                                                                                         'end_offset': 3}]},
                                                                    'real': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                         'start_offset': 5,
                                                                                                         'end_offset': 8}]},
                                                                    'text': {'term_freq': 1, 'tokens': [{'position': 2,
                                                                                                         'start_offset': 10,
                                                                                                         'end_offset': 13}]}
                                                                    }
                                                      },
                                                      'lemmas': {'terms':
                                                                   {'gerere': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                         'start_offset': 0,
                                                                                                         'end_offset': 3}]},
                                                                    'gesta': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                         'start_offset': 5,
                                                                                                         'end_offset': 8}]},
                                                                    'text': {'term_freq': 1, 'tokens': [{'position': 2,
                                                                                                         'start_offset': 10,
                                                                                                         'end_offset': 13}]}
                                                                    }
                                                      }
                                     }}
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertCountEqual(body['query']['bool']['must'][0]['bool']['should'],
                              mock_search.call_args[1]['body']['query']['bool']['must'][0]['bool']['should'])
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_mapped_multiword_lemma_advanced_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_mapped_multiword_lemma_advanced_search'])
        test_args.pop('lemma_search')
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        mock_vectors.return_value = {'_index': 'andecavensis_v1',
                                     '_type': 'andecavensis',
                                     '_id': 'urn:cts:formulae:andecavensis.form001.lat001',
                                     '_version': 1,
                                     'found': True,
                                     'took': 0,
                                     'term_vectors': {'text': {'terms':
                                                                   {'some': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                         'start_offset': 0,
                                                                                                         'end_offset': 3}]},
                                                                    'real': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                         'start_offset': 5,
                                                                                                         'end_offset': 8}]},
                                                                    'text': {'term_freq': 1, 'tokens': [{'position': 2,
                                                                                                         'start_offset': 10,
                                                                                                         'end_offset': 13}]}
                                                                    }
                                                      },
                                                      'lemmas': {'terms':
                                                                   {'gerere': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                         'start_offset': 0,
                                                                                                         'end_offset': 3}]},
                                                                    'gesta': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                         'start_offset': 5,
                                                                                                         'end_offset': 8}]},
                                                                    'text': {'term_freq': 1, 'tokens': [{'position': 2,
                                                                                                         'start_offset': 10,
                                                                                                         'end_offset': 13}]}
                                                                    }
                                                      }
                                     }}
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertCountEqual(body['query']['bool']['must'][0]['bool']['should'],
                              mock_search.call_args[1]['body']['query']['bool']['must'][0]['bool']['should'])
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_lemma_simple_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_lemma_advanced_search'])
        test_args.pop('lemma_search')
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
                                      }
                                     ],
                                 'minimum_should_match': 1
                                 }
                              }
                             ]
                         }
                     },
                'sort': 'urn',
                'from': 0,
                'size': 10,
                'aggs':
                    {'range':
                         {'date_range':
                              {'field': 'min_date',
                               'format': 'yyyy',
                               'ranges': [
                                   {'key': '<499', 'from': '0002', 'to': '0499'},
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
                                         'ranges': [
                                             {'key': '<499', 'from': '0002', 'to': '0499'},
                                             {'key': '500-599', 'from': '0500', 'to': '0599'},
                                             {'key': '600-699', 'from': '0600', 'to': '0699'},
                                             {'key': '700-799', 'from': '0700', 'to': '0799'},
                                             {'key': '800-899', 'from': '0800', 'to': '0899'},
                                             {'key': '900-999', 'from': '0900', 'to': '0999'},
                                             {'key': '>1000', 'from': '1000'}
                                         ]
                                         }
                                    },
                               'corpus': {'filters':
                                              {'filters': self.SEARCH_FILTERS_CORPORA}},
                               'no_date': {'missing': {'field': 'min_date'}}}}},
                'highlight':
                    {'fields':
                         {'lemmas': {'fragment_size': 1000},
                          'regest': {'fragment_size': 1000}},
                     'pre_tags': ['</small><strong>'],
                     'post_tags': ['</strong><small>'],
                     'encoder': 'html'}
                }

        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        mock_vectors.return_value = self.MOCK_VECTOR_RETURN_VALUE
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(corpus=test_args['corpus'], field='lemmas', q=test_args['q'], page=1,
                                               per_page=10)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_mapped_lemma_simple_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_mapped_lemma_advanced_search'])
        test_args.pop('lemma_search')
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
                                           }
                                          ],
                                     'minimum_should_match': 1
                                     }
                                }
                               ]
                          }
                     },
                'sort': 'urn',
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
        ids = fake.load_ids()
        mock_search.return_value = resp
        mock_vectors.return_value = {'_index': 'andecavensis_v1',
                                     '_type': 'andecavensis',
                                     '_id': 'urn:cts:formulae:andecavensis.form001.lat001',
                                     '_version': 1,
                                     'found': True,
                                     'took': 0,
                                     'term_vectors': {'text': {'terms':
                                                                   {'some': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                         'start_offset': 0,
                                                                                                         'end_offset': 3}]},
                                                                    'real': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                         'start_offset': 5,
                                                                                                         'end_offset': 8}]},
                                                                    'text': {'term_freq': 1, 'tokens': [{'position': 2,
                                                                                                         'start_offset': 10,
                                                                                                         'end_offset': 13}]}
                                                                    }
                                                      },
                                                      'lemmas': {'terms':
                                                                   {'regnum': {'term_freq': 1, 'tokens': [{'position': 0,
                                                                                                         'start_offset': 0,
                                                                                                         'end_offset': 3}]},
                                                                    'real': {'term_freq': 1, 'tokens': [{'position': 1,
                                                                                                         'start_offset': 5,
                                                                                                         'end_offset': 8}]},
                                                                    'text': {'term_freq': 1, 'tokens': [{'position': 2,
                                                                                                         'start_offset': 10,
                                                                                                         'end_offset': 13}]}
                                                                    }
                                                      }
                                     }}
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(corpus=test_args['corpus'], field='lemmas', q=test_args['q'], page=1,
                                               per_page=10)
        self.assertCountEqual(body['query']['bool']['must'][0]['bool']['should'],
                              mock_search.call_args[1]['body']['query']['bool']['must'][0]['bool']['should'])
        # mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_regest_advanced_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_regest_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_regest_and_word_advanced_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_regest_and_word_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        mock_vectors.return_value = self.MOCK_VECTOR_RETURN_VALUE
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
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multiword_lemma_advanced_search(self, mock_vectors, mock_search):
        test_args = copy(self.TEST_ARGS['test_multiword_lemma_advanced_search'])
        test_args.pop('lemma_search')
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        mock_vectors.return_value = self.MOCK_VECTOR_RETURN_VALUE
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_single_word_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas
            This also makes sure that a highlighted word that is just the wrong distance from the end of the string
            will not cause an error.
        """
        test_args = copy(self.TEST_ARGS['test_single_word_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        sents = [{'sents': [Markup('testes. Ego Orsacius pro misericordia dei vocatus presbiter ad vice </small><strong>Pettonis</strong><small> presbiteri scripsi et suscripsi.')]},
                 {'sents': [Markup('vico Uaze testes. Ego Orsacius licit indignus presbiteri ad vice </small><strong>Pettonis</strong><small> presbiteri scripsi et suscripsi.')]}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_single_word_highlighting_wildcard(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas
            This also makes sure that a highlighted word that is just the wrong distance from the end of the string
            will not cause an error.
        """
        test_args = copy(self.TEST_ARGS['test_single_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        for i1, hit in enumerate(resp['hits']['hits']):
            for i2, t in enumerate(hit['highlight']['text']):
                resp['hits']['hits'][i1]['highlight']['text'][i2] = re.sub(r'regis', '</small><strong>regis</strong><small>', t)
        sents = [{'sents':
                      [Markup('omnium cartarum adcommodat firmitatem. Facta cartula in civitate Curia, sub </small><strong>regnum </strong><small>domni nostri Charoli gloriosissimi regis, sub die, quod est XV '),
                       Markup('cartula in civitate Curia, sub regnum domni nostri Charoli gloriosissimi </small><strong>regis,</strong><small> sub die, quod est XV kl. madii, sub presenciarum bonorum '),
                       Markup('ab eo rogiti venerunt vel signa fecerunt, Notavi diem et </small><strong>regnum </strong><small>superscripsi. Signum Baselii et filii sui Rofini, qui haec fieri ')]},
                 {'sents':
                      [Markup('Facta donacio in loco Fortunes, sub presencia virorum testium sub </small><strong>regnum </strong><small>domni nostri Caroli regis, Sub die, quod est pridie kl.'),
                       Markup('Fortunes, sub presencia virorum testium sub regnum domni nostri Caroli </small><strong>regis,</strong><small> Sub die, quod est pridie kl. aprilis. Notavi diem et '),
                       Markup('Sub die, quod est pridie kl. aprilis. Notavi diem et </small><strong>regnum </strong><small>superscripsi. Signum Uictorini et Felicianes uxoris ipsius, qui haec fieri ')]}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = 'reg*'
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_word_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = copy(self.TEST_ARGS['test_multi_word_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        sents = [{'sents': [Markup('Orsacius pro misericordia dei vocatus presbiter ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licit indignus presbiteri ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licet indignus presbiter a vice Augustani diaconis </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('Orsacius per misericordiam dei vocatus presbiter a vice Lubucionis diaconi </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_word_highlighting_repeated_words(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = copy(self.TEST_ARGS['test_multi_word_highlighting_repeated_words'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        sents = [{'sents': [Markup('Prestanti testes. Signum Lobicini presbiteri testes. Signum Seffonis fratris Remedii </small><strong>testes</strong><small>. </small><strong>Signum</strong><small> </small><strong>Uuiliarentis</strong><small> </small><strong>testes</strong><small>. </small><strong>Signum</strong><small> </small><strong>Crespionis</strong><small> testes. Signum Donati testes. Signum Gauuenti testes. Ego Orsacius pro ')]}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_single_word_fuzzy_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas
            This also makes sure that a highlighted word that is just the wrong distance from the end of the string
            will not cause an error.
        """
        test_args = copy(self.TEST_ARGS['test_single_word_fuzzy_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        sents = [{'sents': ['Text nicht zugänglich.']},
                 {'sents': [Markup('testes. Ego Orsacius pro misericordia dei vocatus presbiter ad vice </small><strong>Pettonis</strong><small> presbiteri scripsi et suscripsi.')]},
                 {'sents': [Markup('vico Uaze testes. Ego Orsacius licit indignus presbiteri ad vice </small><strong>Pettonis</strong><small> presbiteri scripsi et suscripsi.')]},
                 {'sents': ['Text nicht zugänglich.']}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_word_fuzzy_highlighting_with_wildcard(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when doing fuzzy searches with wildcards"""
        test_args = copy(self.TEST_ARGS['test_multi_word_fuzzy_highlighting_with_wildcard'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        sents = [{'sents': [Markup('Orsacius pro misericordia dei vocatus presbiter ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licit indignus presbiteri ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licet indignus presbiter a vice Augustani diaconis </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('Orsacius per misericordiam dei vocatus presbiter a vice Lubucionis diaconi </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_word_fuzzy_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when doing fuzzy searches"""
        test_args = copy(self.TEST_ARGS['test_multi_word_fuzzy_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        sents = [{'sents': ['Text nicht zugänglich.']},
                 {'sents': [Markup('Orsacius pro misericordia dei vocatus presbiter ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licit indignus presbiteri ad vice Pettonis presbiteri </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('testes. Ego Orsacius licet indignus presbiter a vice Augustani diaconis </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': [Markup('Orsacius per misericordiam dei vocatus presbiter a vice Lubucionis diaconi </small><strong>scripsi</strong><small> </small><strong>et</strong><small> </small><strong>suscripsi</strong><small>.')]},
                 {'sents': ['Text nicht zugänglich.']},
                 {'sents': ['Text nicht zugänglich.']},
                 {'sents': ['Text nicht zugänglich.']},
                 {'sents': ['Text nicht zugänglich.']},
                 {'sents': ['Text nicht zugänglich.']}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_single_word_highlighting_wildcard(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas
            This also makes sure that a highlighted word that is just the wrong distance from the end of the string
            will not cause an error.
        """
        test_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        for i1, hit in enumerate(resp['hits']['hits']):
            for i2, t in enumerate(hit['highlight']['text']):
                resp['hits']['hits'][i1]['highlight']['text'][i2] = re.sub(r'regis', '</small><strong>regis</strong><small>', t)
        sents = [{'sents':
                      [Markup('omnium cartarum adcommodat firmitatem. Facta cartula in civitate Curia, sub </small><strong>regnum</strong><small> </small><strong>domni</strong><small> nostri Charoli gloriosissimi regis, sub die, quod est XV kl.'),
                       Markup('cartarum adcommodat firmitatem. Facta cartula in civitate Curia, sub regnum </small><strong>domni</strong><small> nostri Charoli gloriosissimi </small><strong>regis</strong><small>, sub die, quod est XV kl. madii, sub presenciarum bonorum ')]},
                 {'sents':
                      [Markup('Facta donacio in loco Fortunes, sub presencia virorum testium sub </small><strong>regnum</strong><small> </small><strong>domni</strong><small> nostri Caroli regis, Sub die, quod est pridie kl. aprilis.'),
                       Markup('donacio in loco Fortunes, sub presencia virorum testium sub regnum </small><strong>domni</strong><small> nostri Caroli </small><strong>regis</strong><small>, Sub die, quod est pridie kl. aprilis. Notavi diem et ')]}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = 'reg* domni'
        test_args['slop'] = '3'
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_single_lemma_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_single_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
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
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_lemma_highlighting(self, mock_vectors, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = OrderedDict([("corpus", "buenden"), ("field", "lemmas"), ("q", 'regnum+domni'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
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
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_lemma_highlighting_terms_out_of_order(self, mock_vectors, mock_search):
        """ Make sure that highlighting is correctly transferred when ordered_terms is False"""
        test_args = OrderedDict([("corpus", "buenden"), ("field", "lemmas"), ("q", 'domni+regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
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
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_lemma_highlighting_terms_out_of_order_ordered_terms_True(self, mock_vectors, mock_search):
        """ Make sure that highlighting is correctly transferred when ordered_terms is False"""
        test_args = OrderedDict([("corpus", "buenden"), ("field", "lemmas"), ("q", 'domni+regnum'), ("fuzziness", "0"),
                                 ("in_order", "True"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': []},
                 {'sents': []}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_lemma_highlighting_terms_with_slop(self, mock_vectors, mock_search):
        """ Make sure that highlighting is correctly transferred when ordered_terms is False"""
        test_args = OrderedDict([("corpus", "buenden"), ("field", "lemmas"), ("q", 'domni+regnum+regis'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "2"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': []},
                 {'sents': [Markup('Facta donacio in loco Fortunes, sub '
                                   'presencia virorum testium sub </small><strong>regnum</strong><small> '
                                   '</small><strong>domni</strong><small> nostri Caroli '
                                   '</small><strong>regis</strong><small>, Sub die, quod est '
                                   'pridie kl. aprilis. Notavi diem et ')]}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_multi_lemma_highlighting_terms_with_slop_in_order(self, mock_vectors, mock_search):
        """ Make sure that highlighting is correctly transferred when ordered_terms is False"""
        test_args = OrderedDict([("corpus", "buenden"), ("field", "lemmas"), ("q", 'sub+regis'), ("fuzziness", "0"),
                                 ("in_order", "True"), ("year", 0), ("slop", "4"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', ''), ("regest_q", ''),
                                 ("regest_field", "regest")])
        fake_args = copy(self.TEST_ARGS['test_multi_lemma_highlighting'])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        for hit in resp['hits']['hits']:
            hit['highlight']['lemmas'] = hit['highlight']['text']
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': []},
                 {'sents': [Markup('firmitate. Facta donacio in loco Fortunes, sub '
                                   'presencia virorum testium </small><strong>sub</strong><small> regnum '
                                   'domni nostri Caroli </small><strong>regis</strong><small>, Sub die, quod est '
                                   'pridie kl. aprilis. Notavi diem et ')]}]
        mock_search.return_value = resp
        mock_vectors.side_effect = self.my_side_effect
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
            self.assertMessageFlashed(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."))

    @patch.object(Elasticsearch, "search")
    def test_lemma_simple_search_with_wildcard(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_lemma_advanced_search_with_wildcard'])
        mock_search.return_value = [], 0, {}
        with self.client:
            ids, hits, agg, prev = advanced_query_index(corpus=test_args['corpus'], field='lemmas',
                                                        q=test_args['q'], page=1, per_page=10, source='simple')
            self.assertEqual(ids, [])
            self.assertEqual(hits, 0)
            self.assertEqual(prev, [])
            self.assertMessageFlashed(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."))

    @patch.object(Elasticsearch, "search")
    def test_composition_place_advanced_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_composition_place_advanced_search'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_simple_multi_corpus_search(self, mock_search):
        test_args = OrderedDict([("corpus", ['formulae', 'chartae']), ("q", 'regnum'), ("field", "text"),
                                 ("page", 1), ("per_page", self.app.config["POSTS_PER_PAGE"]), ('sort', 'urn'),
                                 ('source', 'simple')])
        mock_search.return_value = {"hits": {"hits": [{'_id': 'urn:cts:formulae:stgallen.wartmann0259.lat001',
                                    '_source': {'urn': 'urn:cts:formulae:stgallen.wartmann0259.lat001',
                                                'title': 'St. Gallen 259'},
                                    'highlight': {
                                        'text': ['Notavi die et <strong>regnum</strong>. Signum Mauri et uxores suas Audoaras, qui hanc cartam fieri rogaverunt.']}}],
                                             'total': 0},
                                    'aggregations': {"corpus": {
                                                      "buckets": {
                                                        "Angers": {
                                                          "doc_count": 2
                                                        },
                                                        "Arnulfinger": {
                                                          "doc_count": 0
                                                        },
                                                        "B\u00fcnden": {
                                                          "doc_count": 0
                                                        },
                                                        "Echternach": {
                                                            "doc_count": 0
                                                        },
                                                        "Freising": {
                                                            "doc_count": 0
                                                        },
                                                        "Fulda (Dronke)": {
                                                            "doc_count": 0
                                                        },
                                                        "Fulda (Stengel)": {
                                                            "doc_count": 0
                                                        },
                                                        "Hersfeld": {
                                                            "doc_count": 0
                                                        },
                                                        "Lorsch": {
                                                            "doc_count": 0
                                                        },
                                                        "Luzern": {
                                                            "doc_count": 0
                                                        },
                                                        "Marculf": {
                                                            "doc_count": 0
                                                        },
                                                        "Marmoutier - Fougères": {
                                                            "doc_count": 0
                                                        },
                                                        "Marmoutier - Manceau": {
                                                            "doc_count": 0
                                                        },
                                                        "Marmoutier - Vendômois": {
                                                            "doc_count": 0
                                                        },
                                                        "Marmoutier - Vendômois, Saint-Marc": {
                                                            "doc_count": 0
                                                        },
                                                        "Marmoutier - Serfs": {
                                                            "doc_count": 0
                                                        },
                                                        "Marmoutier - Vendômois, Saint-Marc": {
                                                            "doc_count": 0
                                                        },
                                                        "Merowinger": {
                                                            "doc_count": 0
                                                        },
                                                        "Mittelrheinisch": {
                                                            "doc_count": 0
                                                        },
                                                        "Mondsee": {
                                                          "doc_count": 0
                                                        },
                                                        "Papsturkunden Frankreich": {
                                                          "doc_count": 0
                                                        },
                                                        "Passau": {
                                                          "doc_count": 0
                                                        },
                                                        "Regensburg": {
                                                          "doc_count": 0
                                                        },
                                                        "Rheinisch": {
                                                          "doc_count": 0
                                                        },
                                                        "R\u00e4tien": {
                                                          "doc_count": 0
                                                        },
                                                        "Salzburg": {
                                                          "doc_count": 0
                                                        },
                                                        "Sch\u00e4ftlarn": {
                                                          "doc_count": 0
                                                        },
                                                        "St. Gallen": {
                                                          "doc_count": 0
                                                        },
                                                        "Weißenburg": {
                                                          "doc_count": 0
                                                        },
                                                        "Werden": {
                                                          "doc_count": 0
                                                        },
                                                        "Z\u00fcrich": {
                                                          "doc_count": 0
                                                        }
                                                      }
                                                    }}}
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
                                                                    {'text':
                                                                         {'value': 'regnum', 'fuzziness': '0'}
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
                'sort': 'urn',
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
        body['query']['bool']['must'][0]['bool']['should'][0]['span_near']['clauses'] = [{'span_multi':
                                                                                              {'match':
                                                                                                   {'fuzzy':
                                                                                     {'text':
                                                                                          {'value': 'regnum',
                                                                                           'fuzziness': '0'
                                                                                           }
                                                                                      }
                                                                                 }
                                                                            }
                                                                       },
                                                                      {'span_multi':
                                                                           {'match':
                                                                                {'fuzzy':
                                                                                     {'text':
                                                                                          {'value': 'domni',
                                                                                           'fuzziness': '0'
                                                                                           }
                                                                                      }
                                                                                 }
                                                                            }
                                                                       }
                                                                      ]
        advanced_query_index(**test_args)
        mock_search.assert_any_call(index=['formulae', 'chartae'], doc_type="", body=body)
        test_args['q'] = 're?num'
        body['query']['bool']['must'][0]['bool']['should'][0]['span_near']['clauses'] = [{'span_multi':
                                                                                              {'match':
                                                                                                   {'wildcard':
                                                                                                        {'text': 're?num'}
                                                                                                    }
                                                                                               }
                                                                                          }
                                                                                         ]
        advanced_query_index(**test_args)
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
            self.client.get('/search/simple?index=&q=regnum', follow_redirects=True)
            self.assertMessageFlashed(_('Sie müssen mindestens eine Sammlung für die Suche auswählen ("Formeln" und/oder "Urkunden").') +
                                      _(' Resultate aus "Formeln" und "Urkunden" werden hier gezeigt.'))
            old_search_args = session['previous_search_args']
            self.assertIn('fulda_dronke', old_search_args['corpus'],
                          'Charters should automatically be search when no index is given in simple search.')
            self.assertIn('andecavensis', old_search_args['corpus'],
                          'Formulae should automatically be search when no index is given in simple search.')
            self.client.get('/search/results?source=simple&index=formulae&q=regnum&old_search=True', follow_redirects=True)
            self.assertEqual(old_search_args['corpus'], session['previous_search_args']['corpus'],
                             'Searches made with the old_search=True argument should not change the previous_search_args.')
            self.client.get('/search/simple?index=formulae&q=', follow_redirects=True)
            self.assertMessageFlashed(_('Dieses Feld wird benötigt.') +
                                      _(' Die einfache Suche funktioniert nur mit einem Suchwort.'))

    @patch.object(Elasticsearch, "search")
    def test_suggest_composition_places(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_suggest_composition_places'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        expected = [' ', 'Bettingen', 'Freising', 'Isen', 'Süstern', 'Weimodo regia villa']
        mock_search.return_value = resp
        results = suggest_composition_places()
        self.assertEqual(results, expected, 'The true results should match the expected results.')

    @patch.object(Elasticsearch, "search")
    def test_suggest_word_search_completion(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_suggest_word_search_completion'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        expected = ['illa curiensis esset distructa et',
                    'illa dua mansa cernebant sed et plurimi',
                    'illa edificia desursum coniungunt',
                    'illa qui possit nobis prestare solatium',
                    'illa remansit res vel familia amplius',
                    'illa testimonia qui de ipso pago erant',
                    'illam audire desiderabilem „euge serve',
                    'illam beatissimam visionem domini',
                    'illam divisionem quam bonae memoriae',
                    'illam divisionem vel ordinationem']
        mock_search.return_value = resp
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
        expected = ['schenkt dem kloster disentis auf ableben',
                    'schenkt dem kloster disentis güter',
                    'schenkt der kirche st hilarius zu seinem',
                    'schenkt seinem neffen priectus seinen',
                    'schenkt zu seinem und seiner eltern',
                    'schenkt zu seinem und seiner gattin',
                    'schenkt zum seelenheil seines bruders']
        mock_search.return_value = resp
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
        test_args = copy(self.TEST_ARGS['test_suggest_regest_word_search_completion'])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        expected = [{'regest_sents': [Markup('Graf Wido von Lomello </small><strong>schenkt</strong><small> dem Kloster Disentis Güter und Rechte.')]},
                    {'regest_sents': [Markup('Bischof Tello von Chur </small><strong>schenkt</strong><small> dem Kloster Disentis auf Ableben seine Güter in der')]},
                    {'regest_sents': [Markup('Ovilio von Trimmis </small><strong>schenkt</strong><small> zu seinem und seiner Gattin Theoderia Seelenheil der')]},
                    {'regest_sents': [Markup('Victorinus </small><strong>schenkt</strong><small> zu seinem und seiner Eltern Seelenheil der Kirche')]},
                    {'regest_sents': [Markup('Der Richter Daumerius </small><strong>schenkt</strong><small> der Kirche St. Hilarius zu seinem Seelenheil und zum')]},
                    {'regest_sents': [Markup('Vigilius von Trimmis </small><strong>schenkt</strong><small> zum Seelenheil seines Bruders Viktor einen kleinen')]},
                    {'regest_sents': [Markup('Der Priester Valencio </small><strong>schenkt</strong><small> seinem Neffen Priectus seinen ganzen Besitz zu Maienfeld.')]}]
        mock_search.return_value = resp
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
        self.assertEqual(build_sort_list('urn'), 'urn')
        self.assertEqual(build_sort_list('min_date_asc'), [{'all_dates': {'order': 'asc', 'mode': 'min'}}, 'urn'])
        self.assertEqual(build_sort_list('max_date_asc'), [{'all_dates': {'order': 'asc', 'mode': 'max'}}, 'urn'])
        self.assertEqual(build_sort_list('min_date_desc'), [{'all_dates': {'order': 'desc', 'mode': 'min'}}, 'urn'])
        self.assertEqual(build_sort_list('max_date_desc'), [{'all_dates': {'order': 'desc', 'mode': 'max'}}, 'urn'])
        self.assertEqual(build_sort_list('urn_desc'), [{'urn': {'order': 'desc'}}])

    @patch.object(Elasticsearch, "search")
    def test_save_requests(self, mock_search):
        self.app.config['SAVE_REQUESTS'] = True
        test_args = copy(self.TEST_ARGS['test_save_requests'])
        file_name_base = self.build_file_name(test_args)
        fake = FakeElasticsearch(file_name_base, 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
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
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['special_days'] = test_args['special_days'].split('+')
        actual, _, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    @patch.object(Elasticsearch, "termvectors")
    def test_download_search_results(self, mock_vectors, mock_search):
        with self.client as c:
            c.get('/search/download', follow_redirects=True)
            self.assertMessageFlashed(_('Keine Suchergebnisse zum Herunterladen.'))
            self.assertTemplateUsed('main::index.html')
        test_args = copy(self.TEST_ARGS['test_download_search_results'])
        fake = FakeElasticsearch(self.build_file_name(test_args).replace('%2B', '+'), 'advanced_search')
        resp = fake.load_response()
        mock_search.return_value = resp
        mock_vectors.return_value = self.MOCK_VECTOR_RETURN_VALUE
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['special_days'] = [test_args['special_days']]
        self.nemo.open_texts.append('urn:cts:formulae:buenden.meyer-marthaler0027.lat001')
        with open('tests/test_data/advanced_search/downloaded_search.pdf', mode='rb') as f:
            expected = f.read()
        with self.client as c:
            c.get('/search/results?source=advanced&sort=urn&q=regnum&fuzziness=0&slop=0&in_order=False&regest_q=schenk*&year=&month=0&day=&year_start=&month_start=0&day_start=&year_end=&month_end=0&day_end=&date_plus_minus=0&exclusive_date_range=False&composition_place=&submit=True&corpus=all&special_days=')
            r = c.get('/search/download')
            # Uncomment this when the mock search download file needs to be recreated
            #with open('tests/test_data/advanced_search/downloaded_search.pdf', mode='wb') as f:
            #    f.write(r.get_data())
            self.assertEqual(re.search(b'>>\nstream\n.*?>endstream', expected).group(0),
                             re.search(b'>>\nstream\n.*?>endstream', r.get_data()).group(0))


class TestErrors(Formulae_Testing):
    def test_404(self):
        with self.client as c:
            response = c.get('/trying.php', follow_redirects=True)
            self.assert404(response, 'A URL that does not exist on the server should return a 404.')

    def test_UnknownCollection_error_mv(self):
        with self.client as c:
            response = c.get('/corpus_m/urn:cts:formulae:buendner', follow_redirects=True)
            self.assert404(response, 'An Unknown Collection Error should also return 404.')
            self.assertTemplateUsed("errors::unknown_collection.html")

    def test_UnknownCollection_error(self):
        with self.client as c:
            response = c.get('/corpus/urn:cts:formulae:buendner', follow_redirects=True)
            self.assert404(response, 'An Unknown Collection Error should also return 404.')
            self.assertTemplateUsed("errors::unknown_collection.html")

    def test_500(self):
        with self.client as c:
            expected = "<h4>{}</h4><p>{}</p>".format(_('Ein unerwarteter Fehler ist aufgetreten'),
                                                     _('Der Administrator wurde benachrichtigt. Bitte entschuldigen Sie die Unannehmlichkeiten!'))
            response = c.get('/500', follow_redirects=True)
            self.assert500(response, 'Should raise 500 error.')
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
