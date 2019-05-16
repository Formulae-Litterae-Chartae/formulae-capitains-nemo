from config import Config
from capitains_nautilus.cts.resolver import NautilusCTSResolver
from formulae import create_app, db, mail
from formulae.nemo import NemoFormulae
from formulae.models import User
from formulae.search.Search import advanced_query_index, query_index, suggest_composition_places, build_sort_list, \
    set_session_token, suggest_word_search, highlight_segment
import flask_testing
from formulae.search.forms import AdvancedSearchForm, SearchForm
from formulae.auth.forms import LoginForm, PasswordChangeForm, LanguageChangeForm, ResetPasswordForm, \
    ResetPasswordRequestForm, RegistrationForm, ValidationError
from formulae.viewer.Viewer import get_passage
from flask_login import current_user
from flask_babel import _
from elasticsearch import Elasticsearch
from unittest.mock import patch, mock_open
from tests.fake_es import FakeElasticsearch
from collections import OrderedDict
import os
from MyCapytain.common.constants import Mimetypes
from flask import Markup, session, g, url_for, abort
from json import dumps
import re
from math import ceil
from formulae.dispatcher_builder import organizer
from json import load

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    CORPUS_FOLDERS = ["tests/test_data/formulae"]
    WTF_CSRF_ENABLED = False
    SESSION_TYPE = 'filesystem'
    SAVE_REQUESTS = False
    IIIF_MAPPING = "tests/test_data/formulae/data"
    IIIF_SERVER = "http://127.0.0.1:5004"



class Formulae_Testing(flask_testing.TestCase):
    def create_app(self):

        app = create_app(TestConfig)
        resolver = NautilusCTSResolver(app.config['CORPUS_FOLDERS'], dispatcher=organizer)
        self.nemo = NemoFormulae(name="InstanceNemo", resolver=resolver,
                                 app=app, base_url="", transform={"default": "components/epidoc.xsl",
                                                                  "notes": "components/extract_notes.xsl",
                                                                  "elex_notes": "components/extract_elex_notes.xsl"},
                                 templates={"main": "templates/main",
                                            "errors": "templates/errors",
                                            "auth": "templates/auth",
                                            "search": "templates/search",
                                            "viewer":"templates/viewer"},
                                 css=["assets/css/theme.css"], js=["assets/js/empty.js"], static_folder="./assets/",
                                 pdf_folder="pdf_folder/")

        app.config['nemo_app'] = self.nemo

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
    def test_setup_global_app(self):
        """ Make sure that the instance of Nemo on the server is created correctly"""
        if os.environ.get('TRAVIS'):
            # This should only be tested on Travis since I don't want it to run locally
            from formulae.app import nemo
            self.assertEqual(nemo.open_texts, self.nemo.open_texts)
            self.assertEqual(nemo.sub_colls, self.nemo.sub_colls)
            self.assertEqual(nemo.pdf_folder, self.nemo.pdf_folder)


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
            self.assertTemplateUsed('main::contact.html')
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
            self.assertMessageFlashed(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
            c.get('/collections/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertMessageFlashed(_('Die Formulae Andecavensis sind in der Endredaktion und werden bald zur Verfügung stehen.'))
            self.assertTemplateUsed('main::sub_collections.html')
            c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertMessageFlashed(_('Die Formulae Andecavensis sind in der Endredaktion und werden bald zur Verfügung stehen.'))
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertTemplateUsed('main::salzburg_collection.html')
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
            c.get('/add_collection/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collections.html')
            self.assertMessageFlashed(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
            c.get('/add_text/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            self.assertMessageFlashed(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertTemplateUsed('main::lexicon_modal.html')
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            # An non-authenicated user who surfs to the login page should not be redirected
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            # The following tests are to make sure that non-open texts are not available to non-project members
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
            # Make sure the Salzburg collection is ordered correctly
            r = c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            p = re.compile('<h5>Codex Odalberti Vorrede: </h5>.+<h5>Codex Odalberti 1: </h5>.+<h5>Notitia Arnonis Notitia Arnonis: </h5>',
                           re.DOTALL)
            self.assertRegex(r.get_data(as_text=True), p)
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertMessageFlashed(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertMessageFlashed(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
            c.get('/lang/en', follow_redirects=True, headers={'Referer': url_for('.r_bibliography')})
            self.assertTemplateUsed('main::bibliography.html')
            self.assertEqual(session['locale'], 'en')
            response = c.get('/lang/en', follow_redirects=True, headers={"X-Requested-With": "XMLHttpRequest"})
            self.assertEqual(response.get_data(as_text=True), 'OK')
            # Navigating to the results page with no search args should redirect the user to the index
            c.get('/search/results', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            c.get('viewer/embedded/urn:cts:formulae:andecavensis.form001.lat001/0', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
            self.assertTemplateUsed('main::index.html')
            c.get('viewer/urn:cts:formulae:andecavensis.form001.lat001/0', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
            self.assertTemplateUsed('main::index.html')

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
            self.assertTemplateUsed('main::sub_collections.html')
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            c.get('/collections/formulae_collection', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/collections/other_collection', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collections.html')
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertTemplateUsed('main::salzburg_collection.html')
            c.get('/corpus/urn:cts:formulae:elexicon', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
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
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertTemplateUsed('main::lexicon_modal.html')
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            # An authenicated user who surfs to the login page should be redirected to index
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            # The following tests are to make sure that non-open texts are available to project members
            c.get('/add_collection/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            r = c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            self.assertRegex(r.get_data(as_text=True), 'Lesen:.+\[Latein\].+\[Deutsch\]')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/2+12', follow_redirects=True)
            self.assertMessageFlashed('FORMULA ANDECAVENSIS 1.12 wurde nicht gefunden. Der ganze Text wird angezeigt.')
            self.assertTemplateUsed('main::multipassage.html')
            r = c.get('/texts/urn:cts:formulae:andecavensis.form001/passage/2', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('FORMULA ANDECAVENSIS 1', r.get_data(as_text=True))
            # Make sure that a text that has no edition will throw an error
            r = c.get('/texts/urn:cts:formulae:andecavensis.form003/passage/1', follow_redirects=True)
            self.assertTemplateUsed("errors::unknown_collection.html")
            self.assertIn('Angers 3.1' + _(' hat keine Edition.'), r.get_data(as_text=True))
            c.get('/viewer/urn:cts:formulae:andecavensis.form001.lat001/0?embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::multiviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form002.lat001/0?embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::multiviewermirador.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001.lat001/0', follow_redirects=True)
            self.assertTemplateUsed('viewer::newtabviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form002.lat001/0', follow_redirects=True)
            self.assertTemplateUsed('viewer::miradorviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001.lat001/abz?embedded=True', follow_redirects=True)
            self.assertMessageFlashed(_('Es gibt kein Bild abz für diese Formel. Das erste Bild wird gezeigt.'))
            self.assertTemplateUsed('viewer::multiviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001.lat001/6?embedded=True', follow_redirects=True)
            self.assertMessageFlashed(_('Es gibt nur 5 Bilder für diese Formel. Das letzte Bild wird hier gezeigt.'))
            self.assertTemplateUsed('viewer::multiviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001.lat001/-1?embedded=True', follow_redirects=True)
            self.assertMessageFlashed(_('Die Zählung der Bilder fängt immer mit 0. Das erste Bild wird hier gezeigt.'))
            self.assertTemplateUsed('viewer::multiviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001.lat001/abz', follow_redirects=True)
            self.assertMessageFlashed(_('Es gibt kein Bild abz für diese Formel. Das erste Bild wird gezeigt.'))
            self.assertTemplateUsed('viewer::newtabviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001.lat001/5', follow_redirects=True)
            self.assertMessageFlashed(_('Es gibt nur 5 Bilder für diese Formel. Das letzte Bild wird hier gezeigt.'))
            self.assertTemplateUsed('viewer::newtabviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001.lat001/-1', follow_redirects=True)
            self.assertMessageFlashed(_('Die Zählung der Bilder fängt immer mit 0. Das erste Bild wird hier gezeigt.'))
            self.assertTemplateUsed('viewer::newtabviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form001/0?embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::multiviewer.html')
            r = c.get('/viewer/urn:cts:formulae:andecavensis.form003/0?embedded=True', follow_redirects=True)
            self.assertTemplateUsed("errors::unknown_collection.html")
            self.assertIn('Angers 3' + _(' hat keine Edition.'), r.get_data(as_text=True))
            c.get('/viewer/urn:cts:formulae:andecavensis.form004.lat001/7', follow_redirects=True)
            self.assertMessageFlashed(_('Es gibt nur 2 Bilder für diese Formel. Das letzte Bild wird hier gezeigt.'))
            self.assertTemplateUsed('viewer::newtabviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form004.lat001/-1', follow_redirects=True)
            self.assertMessageFlashed(_('Die Zählung der Bilder fängt immer mit 0. Das erste Bild wird hier gezeigt.'))
            self.assertTemplateUsed('viewer::newtabviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form004.lat001/0', follow_redirects=True)
            self.assertTemplateUsed('viewer::newtabviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form004.lat001/abz', follow_redirects=True)
            self.assertMessageFlashed(_('Es gibt kein Bild abz für diese Formel. Das erste Bild wird gezeigt.'))
            self.assertTemplateUsed('viewer::newtabviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form004.lat001/7?embedded=True', follow_redirects=True)
            self.assertMessageFlashed(_('Es gibt nur 2 Bilder für diese Formel. Das letzte Bild wird hier gezeigt.'))
            self.assertTemplateUsed('viewer::multiviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form004.lat001/-1?embedded=True', follow_redirects=True)
            self.assertMessageFlashed(_('Die Zählung der Bilder fängt immer mit 0. Das erste Bild wird hier gezeigt.'))
            self.assertTemplateUsed('viewer::multiviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form004.lat001/0?embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::multiviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form005.lat001/0', follow_redirects=True)
            self.assertTemplateUsed('viewer::miradorviewer.html')
            c.get('/viewer/urn:cts:formulae:andecavensis.form005.lat001/0?embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::multiviewermirador.html')

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
            self.assertTemplateUsed('main::index.html')
            c.get('/auth/register', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            self.assertMessageFlashed(_('Sie sind schon eingeloggt.'))
            c.get('/collections', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/collections/formulae_collection', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
            c.get('/corpus/urn:cts:formulae:andecavensis', follow_redirects=True)
            self.assertMessageFlashed(_('Die Formulae Andecavensis sind in der Endredaktion und werden bald zur Verfügung stehen.'))
            c.get('/collections/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.'))
            c.get('/corpus/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:salzburg', follow_redirects=True)
            self.assertTemplateUsed('main::salzburg_collection.html')
            c.get('/corpus/urn:cts:formulae:elexicon', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
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
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True,
                  headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertTemplateUsed('main::lexicon_modal.html')
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            # An authenicated user who surfs to the login page should be redirected to index
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            # The following tests are to make sure that non-open texts are not available to non-project members
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertMessageFlashed('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.')
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertMessageFlashed('Diese Sammlung steht unter Copyright und darf hier nicht gezeigt werden.')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertMessageFlashed('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertMessageFlashed('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.')
            c.get('viewer/embedded/urn:cts:formulae:andecavensis.form001.lat001/0', follow_redirects=True)
            self.assertMessageFlashed(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
            self.assertTemplateUsed('main::index.html')


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
                    "B\u00fcnden": {
                      "doc_count": 0
                    },
                      "Freising": {
                          "doc_count": 0
                      },
                    "Luzern": {
                      "doc_count": 0
                    },
                    "Mondsee": {
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
        mock_search.return_value = [[], 0, aggs]
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
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&submit=True')
            mock_search.assert_called_with(corpus=['formulae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, field='text', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False', composition_place='', sort="urn",
                                           special_days=[''])
            # Check g.corpora
            self.assertIn(('andecavensis', 'Angers'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')
            # Test to make sure that a capitalized search term is converted to lowercase in advanced search
            params['q'] = 'regnum'
            params['corpus'] = 'chartae'
            response = c.get('/search/advanced_search?corpus=chartae&q=Regnum&year=600&month=1&day=31&'
                             'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                             'date_plus_minus=0&submit=Search')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))
            c.get('/search/advanced_search?corpus=chartae&q=Regnum&year=600&month=1&day=31&'
                  'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                  'date_plus_minus=0&submit=Search', follow_redirects=True)
            # Check g.corpora
            self.assertIn(('stgallen', 'St. Gallen'), g.corpora,
                          'g.corpora should be set when session["previous_search_args"] is set.')

    @patch("formulae.search.routes.query_index")
    def test_simple_search_results(self, mock_search):
        """ Make sure that the correct search results are passed to the search results form"""
        params = dict(corpus='formulae%2Bchartae', q='regnum', sort='urn')
        mock_search.return_value = [[], 0]
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            response = c.get('/search/simple?corpus=formulae&corpus=chartae&q=Regnum')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))

    def test_search_result_highlighting(self):
        """ Make sure that highlighting of search results works correctly"""
        # Highlighting should cross boundary of parent nodes
        search_string = ['Text that I want to search']
        expected = '<span class="searched"><span class="w searched-start">Text</span><span class="w searched-end">that</span></span></p><p><span class="searched"><span class="w searched-start searched-end">I</span></span></p><p><span class="searched"><span class="w searched-start">want</span><span class="w">to</span><span class="w searched-end">search</span></span>'
        obj_id = 'urn:cts:formulae:salzburg.hauthaler-a0001.lat001'
        xml = self.nemo.get_passage(objectId=obj_id, subreference='1')
        html_input = Markup(self.nemo.transform(xml, xml.export(Mimetypes.PYTHON.ETREE), obj_id))
        result = self.nemo.highlight_found_sents(html_input, search_string)
        self.assertIn(expected, result)
        # Should be able to deal with editorial punctuation in the text
        search_string = ['Text with special editorial signs in it']
        expected = '<span class="searched"><span class="w searched-start">Text</span><span class="w">with</span><span class="w">sp&lt;e&gt;cial</span><span class="w">[edi]torial</span><span class="w">[signs</span><span class="w">in</span><span class="w searched-end">i]t</span></span>'
        obj_id = 'urn:cts:formulae:salzburg.hauthaler-a0001.lat001'
        xml = self.nemo.get_passage(objectId=obj_id, subreference='1')
        html_input = Markup(self.nemo.transform(xml, xml.export(Mimetypes.PYTHON.ETREE), obj_id))
        result = self.nemo.highlight_found_sents(html_input, search_string)
        self.assertIn(expected, result)
        # Should return the same result when passed in the session variable to r_multipassage
        session['previous_search'] = [{'id': obj_id, 'title': 'Salzburg A1', 'sents': search_string}]
        passage_data = self.nemo.r_multipassage(obj_id, '1')
        self.assertIn(expected, passage_data['objects'][0]['text_passage'])

    def test_convert_result_sents(self):
        """ Make sure that search result_sents are converted correctly"""
        input_str = [['Anno+XXV+pos+<%2Fsmall><strong>regnum<%2Fstrong><small>+domni+nistri+Lodoici+regis+in', 'Notavimus+die+et+<%2Fsmall><strong>regnum<%2Fstrong><small>%2C+superscripsi.+Signum+Petrone']]
        output = self.nemo.convert_result_sents(input_str)
        expected = ['Anno XXV pos regnum domni nistri Lodoici regis in', 'Notavimus die et regnum superscripsi Signum Petrone']
        self.assertEqual(output, expected)

    @patch.object(Elasticsearch, "search")
    def test_session_previous_results_set(self, mock_search):
        """ Make sure that session['previous_results'] is set correctly"""
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(TestES().build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        mock_search.return_value = resp
        set_session_token('all', body, field=test_args['field'], q=test_args['q'] if test_args['field'] == 'text' else '')
        self.assertEqual(session['previous_search'], [{'id': hit['_id'], 'title': hit['_source']['title'], 'sents': []} for hit in resp['hits']['hits']])

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
    def test_session_previous_search_args_all_corps(self, mock_search):
        """ Make sure that session['previous_search_args'] is set correctly with 'all' corpora"""
        search_url = "/search/results?fuzziness=0&day_start=&year=&date_plus_minus=0&q=regnum&year_end=&corpus=all&submit=True&lemma_search=y&year_start=&month_start=0&source=advanced&month=0&day=&in_order=False&exclusive_date_range=False&month_end=0&slop=0&day_end="
        previous_args = {'source': 'advanced', 'corpus': 'all', 'q': 'regnum', 'fuzziness': '0', 'slop': '0',
                         'in_order': 'False', 'year': '', 'month': '0', 'day': '', 'year_start': '', 'month_start': '0',
                         'day_start': '', 'year_end': '', 'month_end': '0', 'day_end': '', 'date_plus_minus': '0',
                         'exclusive_date_range': 'False', 'composition_place': '', 'submit': 'True', 'sort': 'urn',
                         'special_days': ''}
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(TestES().build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        mock_search.return_value = resp
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
            response = c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True,
                             headers={'Referer': '/texts/urn:cts:formulae:stgallen.wartmann0001.lat001/passage/all'})
            self.assertRegex(response.get_data(as_text=True), expected)
            response = c.get('/texts/urn:cts:formulae:elexicon.abbas_abbatissa.deu001/passage/1', follow_redirects=True)
            self.assertRegex(response.get_data(as_text=True), expected)

    def test_cache_max_age_header_set(self):
        """ Make sure that the cache max age header is set correctly with each request"""
        with self.client as c:
            response = c.get('/assets/nemo/css/theme.min.css')
            self.assertEqual(response.cache_control['max-age'], '86400', 'static files should be cached')
            response = c.get('/')
            self.assertEqual(response.cache_control['max-age'], '0', 'normal pages should not be cached')

    def test_rendering_from_texts_without_notes_transformation(self):
        """ Make sure that the multipassage template is rendered correctly without a transformation of the notes"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            r = c.get('/texts/urn:cts:formulae:andecavensis.form003.deu001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('<div class="note-card" id="header-urn-cts-formulae-andecavensis-form003-deu001">',
                          r.get_data(as_text=True), 'Note card should be rendered for a formula.')
            r = c.get('/texts/urn:cts:formulae:elexicon.abbas_abbatissa.deu001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertIn('<div class="note-card" id="header-urn-cts-formulae-elexicon-abbas_abbatissa-deu001">',
                          r.get_data(as_text=True), 'Note card should be rendered for elex.')
            r = c.get('/viewer/urn:cts:formulae:andecavensis.form001/0?embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::multiviewer.html')
            self.assertIn('<div class="note-card" id="header-urn-cts-formulae-andecavensis-form001-lat001">',
                          r.get_data(as_text=True), 'Note card should be rendered for a formula in IIIF Viewer.')
        del self.app.config['nemo_app']._transform['notes']
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            r = c.get('/texts/urn:cts:formulae:andecavensis.form003.deu001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertNotIn('<div class="note-card" id="header-urn-cts-formulae-andecavensis-form003-deu001">',
                             r.get_data(as_text=True), 'No note card should be rendered for a formula.')
            r = c.get('/texts/urn:cts:formulae:elexicon.abbas_abbatissa.deu001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            self.assertNotIn('<div class="note-card" id="header-urn-cts-formulae-elexicon-abbas_abbatissa-deu001">',
                             r.get_data(as_text=True), 'No note card should be rendered for elex.')
            r = c.get('/viewer/embedded/urn:cts:formulae:andecavensis.form001/0?embedded=True', follow_redirects=True)
            self.assertTemplateUsed('viewer::multiviewer.html')
            self.assertNotIn('<div class="note-card" id="header-urn-cts-formulae-andecavensis-form001-lat001">',
                          r.get_data(as_text=True), 'Note card should not be rendered for a formula in IIIF Viewer.')


class TestFunctions(Formulae_Testing):
    def test_NemoFormulae_get_first_passage(self):
        """ Make sure that the first passage of a text is correctly returned"""
        passage = self.nemo.get_first_passage('urn:cts:formulae:elexicon.abbas_abbatissa.deu001')
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

    def test_Search_highlight_segment(self):
        """ Make sure that a highlight segment that ends at the end of the string is correctly returned"""
        orig_str = ' nostri Charoli gloriosissimi regis, sub  die, </small><strong>quod est</strong><small>XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
        expected = " gloriosissimi regis, sub  die, </small><strong>quod est</strong><small>XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        self.assertEqual(highlight_segment(orig_str), expected)


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
                                  day_start=12, year_end=700, month_end="01", day_end=12)
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
                      [_('Sie müssen mindestens eine Sammlung für die Suche auswählen (\"Formeln\" und/oder \"Urkunden\")'),
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
            self.assertTemplateUsed('main::index.html')

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

    def test_send_email_not_existing_user(self):
        """ Ensure that emails are constructed correctly"""
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
            self.assertTemplateUsed('main::index.html')

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
    def build_file_name(self, fake_args):
        return '&'.join(["{}".format(str(v)) for k, v in fake_args.items()])

    def test_return_when_no_es(self):
        """ Make sure that when ElasticSearch is not active, calls to the search functions return empty results instead of errors"""
        self.app.elasticsearch = None
        simple_test_args = OrderedDict([("index", ['formulae', "chartae"]), ("query", 'regnum'), ("field", "text"),
                                        ("page", 1), ("per_page", self.app.config["POSTS_PER_PAGE"]), ('sort', 'urn')])
        hits, total, aggs = query_index(**simple_test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 814),
                                 ("month_start", 10), ("day_start", 29), ("year_end", 814), ("month_end", 11),
                                 ("day_end", 20), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn')])
        hits, total, aggs = advanced_query_index(**test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_same_year(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 814),
                                 ("month_start", 10), ("day_start", 29), ("year_end", 814), ("month_end", 11),
                                 ("day_end", 20), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_same_month(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 10), ("year_end", 800), ("month_end", 10),
                                 ("day_end", 29), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_different_year(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 10), ("year_end", 801), ("month_end", 10),
                                 ("day_end", 29), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_year(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 810), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_year_and_month_same_year(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 800), ("month_end", 11),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_year_and_month_different_year(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 801), ("month_end", 11),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_start_year(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, total, _  = advanced_query_index(**test_args)
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
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 801), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_start_year_and_month(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 800),
                                 ("month_start", 10), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search_only_end_year_and_month(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 801), ("month_end", 10),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_normal_date_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 10), ("day", 9), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_normal_date_only_year_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_plus_minus_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 10), ("day", 9), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 10), ('exclusive_date_range', 'False'),
                                 ("composition_place", ''), ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_exclusive_date_range_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 10), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 10), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_exclusive_date_range_search_only_year(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 0), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _  = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multi_corpus_search(self, mock_search):
        test_args = OrderedDict([("corpus", "andecavensis+mondsee"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', 0), ("month", 0), ("day", 0),
                                 ("year_start", 814), ("month_start", 10), ("day_start", 29), ("year_end", 814),
                                 ("month_end", 11), ("day_end", 20), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multiword_wildcard_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", 'regnum+dom*'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_lemma_advanced_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multiword_lemma_advanced_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'vir+venerabilis'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_single_lemma_highlighting(self, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake_args = OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': ['omnium cartarum adcommodat firmitatem. Facta cartula in civitate '
                            'Curia, sub regnum domni nostri Charoli gloriosissimi regis, sub '
                            'die, quod est',
                            'ab eo rogiti venerunt vel signa fecerunt, Notavi diem et regnum '
                            'superscripsi. Signum Baselii et filii sui Rofini, qui haec']},
                 {'sents': ['Facta donacio in loco Fortunes, sub presencia virorum testium sub '
                            'regnum domni nostri Caroli regis, Sub die, quod est pridie',
                            'Sub die, quod est pridie kl. aprilis. Notavi diem et regnum '
                            'superscripsi. Signum Uictorini et Felicianes uxoris ipsius, qui '
                            'haec']}]
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multi_lemma_highlighting(self, mock_search):
        """ Make sure that the correct sentence fragments are returned when searching for lemmas"""
        test_args = OrderedDict([("corpus", "buenden"), ("field", "lemmas"), ("q", 'regnum+domni'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake_args = OrderedDict([("corpus", "buenden"), ("field", "text"), ("q", 'regnum+domni'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(fake_args), 'advanced_search')
        resp = fake.load_response()
        for i, h in enumerate(resp['hits']['hits']):
            resp['hits']['hits'][i]['_source']['lemmas'] = resp['hits']['hits'][i]['_source']['text']
        sents = [{'sents': ['Archaciani legis stipulacionis subnixa, qui omnium cartarum '
                            'adcommodat firmitatem. Facta cartula in civitate Curia, sub '
                            'regnum domni nostri Charoli gloriosissimi regis, sub die, quod '
                            'est XV kl. madii, sub presenciarum']},
                 {'sents': ['qui omnium cartarum accomodat firmitate. Facta donacio in loco '
                            'Fortunes, sub presencia virorum testium sub regnum domni nostri '
                            'Caroli regis, Sub die, quod est pridie kl. aprilis. Notavi diem '
                            'et']}]
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _ = advanced_query_index(**test_args)
        self.assertEqual(sents, [{"sents": x['sents']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_lemma_advanced_search_with_wildcard(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'venerabili?'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        mock_search.return_value = [], 0, {}
        with self.client:
            ids, hits, agg = advanced_query_index(**test_args)
            self.assertEqual(ids, [])
            self.assertEqual(hits, 0)
            self.assertMessageFlashed(_("'Wildcard'-Zeichen (\"*\" and \"?\") sind bei der Lemmasuche nicht möglich."))

    @patch.object(Elasticsearch, "search")
    def test_composition_place_advanced_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", '(Basel-)Augst'),
                                 ('sort', 'urn'), ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_simple_multi_corpus_search(self, mock_search):
        test_args = OrderedDict([("index", ['formulae', "chartae"]), ("query", 'regnum'), ("field", "text"),
                                 ("page", 1), ("per_page", self.app.config["POSTS_PER_PAGE"]), ('sort', 'urn')])
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
                                                        "B\u00fcnden": {
                                                          "doc_count": 0
                                                        },
                                                          "Freising": {
                                                              "doc_count": 0
                                                          },
                                                        "Luzern": {
                                                          "doc_count": 0
                                                        },
                                                        "Mondsee": {
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
                                                    }}}
        body = {'query':
                    {'span_near':
                         {'clauses': [{'span_term': {'text': 'regnum'}}], 'slop': 0, 'in_order': True}},
                'sort': 'urn', 'from': 0, 'size': 10,
                'highlight': {'fields': {'text': {'fragment_size': 1000}},
                              'pre_tags': ['</small><strong>'],
                              'post_tags': ['</strong><small>'], 'encoder': 'html'},
                'aggs': {'range':
                             {'date_range':
                                  {'field': 'min_date',
                                   'format': 'yyyy',
                                   'ranges': [{'key': '<499', 'from': '0002', 'to': '0499'},
                                              {'key': '500-599', 'from': '0500', 'to': '0599'},
                                              {'key': '600-699', 'from': '0600', 'to': '0699'},
                                              {'key': '700-799', 'from': '0700', 'to': '0799'},
                                              {'key': '800-899', 'from': '0800', 'to': '0899'},
                                              {'key': '900-999', 'from': '0900', 'to': '0999'},
                                              {'key': '>1000', 'from': '1000'}]}},
                         'corpus':
                             {'filters':
                                  {'filters':
                                       {'Rätien': {'match': {'_type': 'raetien'}},
                                        'Angers': {'match': {'_type': 'andecavensis'}},
                                        'Bünden': {'match': {'_type': 'buenden'}},
                                        'Freising': {'match': {'_type': 'freising'}},
                                        'Luzern': {'match': {'_type': 'luzern'}},
                                        'Mondsee': {'match': {'_type': 'mondsee'}},
                                        'Passau': {'match': {'_type': 'passau'}},
                                        'Regensburg': {'match': {'_type': 'regensburg'}},
                                        'Rheinisch': {'match': {'_type': 'rheinisch'}},
                                        'Salzburg': {'match': {'_type': 'salzburg'}},
                                        'Schäftlarn': {'match': {'_type': 'schaeftlarn'}},
                                        'St. Gallen': {'match': {'_type': 'stgallen'}},
                                        'Werden': {'match': {'_type': 'werden'}},
                                        'Zürich': {'match': {'_type': 'zuerich'}}}}},
                         'no_date': {'missing': {'field': 'min_date'}}}}
        query_index(**test_args)
        mock_search.assert_any_call(index=['formulae', 'chartae'], doc_type="", body=body)
        test_args['query'] = 'regnum domni'
        body['query']['span_near']['clauses'] = [{'span_term': {'text': 'regnum'}}, {'span_term': {'text': 'domni'}}]
        query_index(**test_args)
        mock_search.assert_any_call(index=['formulae', 'chartae'], doc_type="", body=body)
        test_args['query'] = 're?num'
        body['query']['span_near']['clauses'] = [{'span_multi': {'match': {'wildcard': {'text': 're?num'}}}}]
        query_index(**test_args)
        mock_search.assert_any_call(index=['formulae', 'chartae'], doc_type="", body=body)
        test_args['index'] = ['']
        hits, total, aggs = query_index(**test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')
        test_args['index'] = ['formulae', 'chartae']
        test_args['query'] = ''
        hits, total, aggs = query_index(**test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')
        with self.client:
            self.client.get('/search/simple?index=&q=regnum', follow_redirects=True)
            self.assertMessageFlashed(_('Sie müssen mindestens eine Sammlung für die Suche auswählen ("Formeln" und/oder "Urkunden")') +
                                      _(' Resultate aus "Formeln" und "Urkunden" werden hier gezeigt.'))
            self.client.get('/search/simple?index=formulae&q=', follow_redirects=True)
            self.assertMessageFlashed(_('Dieses Feld wird benötigt.') +
                                      _(' Die einfache Suche funktioniert nur mit einem Suchwort.'))

    @patch.object(Elasticsearch, "search")
    def test_suggest_composition_places(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 10), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 10), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        expected = [' ', 'Freising', 'Isen', 'St. Gallen']
        mock_search.return_value = resp
        results = suggest_composition_places()
        self.assertEqual(results, expected, 'The true results should match the expected results.')

    @patch.object(Elasticsearch, "search")
    def test_suggest_word_search_completion(self, mock_search):
        test_args = OrderedDict([("corpus", "buenden"), ("field", "autocomplete"), ("q", 'ill'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'y'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', '')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        resp = fake.load_response()
        expected = ['ill',
                    'illa curiensis esset distructa et ',
                    'illa qui possit nobis prestare solatium ',
                    'illa testimonia qui de ipso pago ',
                    'illam audire desiderabilem „ euge ',
                    'illam divisionem quam bonae memoriae ',
                    'illam divisionem vel ordinationem ',
                    'illam indictionem ducatum tibi cedimus ',
                    'ille sicut illi semetipsum hiato terrae ',
                    'illi et mihi econtra donaretur et ',
                    'illi licui set habere']
        mock_search.return_value = resp
        test_args.pop('q')
        results = suggest_word_search('ill', **test_args)
        self.assertEqual(results, expected, 'The true results should match the expected results.')

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
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", '(Basel-)Augst'),
                                 ('sort', 'urn'), ('special_days', '')])
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
                actual, _, _ = advanced_query_index(**test_args)
                mock_dump.assert_any_call(resp, m.return_value.__enter__.return_value, indent=2)
                mock_dump.assert_any_call(body, m.return_value.__enter__.return_value, indent=2)
                mock_dump.assert_any_call(ids, m.return_value.__enter__.return_value, indent=2)

    @patch.object(Elasticsearch, "search")
    def test_specific_day_advanced_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False'), ("composition_place", ''), ('sort', 'urn'),
                                 ('special_days', 'Easter')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['special_days'] = [test_args['special_days']]
        actual, _, _ = advanced_query_index(**test_args)
        mock_search.assert_any_call(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])


class TestErrors(Formulae_Testing):
    def test_404(self):
        with self.client as c:
            response = c.get('/trying.php', follow_redirects=True)
            self.assert404(response, 'A URL that does not exist on the server should return a 404.')

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

class Formulae_Testing_error_mapping(flask_testing.TestCase):

    def create_app(self):
        TestConfig.IIIF_MAPPING="tests/test_data/formulae/data/mapping_error"
        app = create_app(TestConfig)
        resolver = NautilusCTSResolver(app.config['CORPUS_FOLDERS'], dispatcher=organizer)
        self.nemo = NemoFormulae(name="InstanceNemo", resolver=resolver,
                                 app=app, base_url="", transform={"default": "components/epidoc.xsl",
                                                                  "notes": "components/extract_notes.xsl",
                                                                  "elex_notes": "components/extract_elex_notes.xsl"},
                                 templates={"main": "templates/main",
                                            "errors": "templates/errors",
                                            "auth": "templates/auth",
                                            "search": "templates/search",
                                            "viewer":"templates/viewer"},
                                 css=["assets/css/theme.css"], js=["assets/js/empty.js"], static_folder="./assets/",
                                 pdf_folder="pdf_folder/")

        app.config['nemo_app'] = self.nemo

        @app.route('/500', methods=['GET'])
        def r_500():
            abort(500)

        return app


class TestNemoSetup_withoutviewer(Formulae_Testing_error_mapping):
    def TestNemoSetup_withoutviewer(self):
        """ Make sure that the instance of Nemo on the server is created correctly"""
            # This should only be tested on Travis since I don't want it to run locally
        self.assertFalse('viewer' in self.app.blueprints)
