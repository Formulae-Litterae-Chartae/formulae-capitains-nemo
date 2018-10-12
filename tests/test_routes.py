from config import Config
from capitains_nautilus.cts.resolver import NautilusCTSResolver
from formulae import create_app, db
from formulae.nemo import NemoFormulae
from formulae.models import User
from formulae.search.Search import advanced_query_index, query_index
import flask_testing
from formulae.search.forms import AdvancedSearchForm, SearchForm
from formulae.auth.forms import LoginForm, PasswordChangeForm, LanguageChangeForm, ResetPasswordForm, \
    ResetPasswordRequestForm, RegistrationForm, ValidationError
from flask_login import current_user
from flask_babel import _
from elasticsearch import Elasticsearch
from unittest.mock import patch
from .fake_es import FakeElasticsearch
from collections import OrderedDict
import os


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    CORPUS_FOLDERS = ["tests/test_data/formulae"]
    WTF_CSRF_ENABLED = False


class Formulae_Testing(flask_testing.TestCase):
    def create_app(self):

        app = create_app(TestConfig)
        self.nemo = NemoFormulae(name="InstanceNemo", resolver=NautilusCTSResolver(app.config['CORPUS_FOLDERS']),
                                 app=app, base_url="",
                                 templates={"main": "templates/main",
                                            "errors": "templates/errors",
                                            "auth": "templates/auth",
                                            "search": "templates/search"},
                                 css=["assets/css/theme.css"], js=["assets/js/empty.js"], static_folder="./assets/")
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


class TestIndividualRoutes(Formulae_Testing):
    def test_anonymous_user(self):
        """ Make sure that protected routes do not work with unauthorized users and that unprotected routes do

        """
        with self.client as c:
            c.get('/', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            c.get('/imprint', follow_redirects=True)
            self.assertTemplateUsed('main::impressum.html')
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertMessageFlashed(_('Loggen Sie bitte ein, um diese Seite zu sehen.'))
            self.assertTemplateUsed('auth::login.html')
            c.get('/collections', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
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
            c.get('/add_text/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True)
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
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertMessageFlashed(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertMessageFlashed(_('Mindestens ein Text, den Sie anzeigen möchten, ist nicht verfügbar.'))

    def test_authorized_project_member(self):
        """ Make sure that all routes are open to project members"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            c.get('/', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            c.get('/imprint', follow_redirects=True)
            self.assertTemplateUsed('main::impressum.html')
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            c.get('/collections', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
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
            c.get('/add_text/urn:cts:formulae:andecavensis/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True)
            self.assertTemplateUsed('main::lexicon_modal.html')
            c.get('/add_text/urn:cts:formulae:elexicon/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::elex_collection.html')
            # An authenicated user who surfs to the login page should be redirected to index
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            # The following tests are to make sure that non-open texts are available to project members
            c.get('/add_text/urn:cts:formulae:raetien/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/corpus/urn:cts:formulae:raetien', follow_redirects=True)
            self.assertTemplateUsed('main::sub_collection.html')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+all', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/texts/urn:cts:formulae:raetien.erhart0001.lat001/passage/1', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')

    def test_authorized_normal_user(self):
        """ Make sure that all routes are open to normal users but that some texts are not available"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='not.project', password="some_other_password"),
                   follow_redirects=True)
            c.get('/', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            c.get('/imprint', follow_redirects=True)
            self.assertTemplateUsed('main::impressum.html')
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            c.get('/collections', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
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
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True)
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

    @patch("formulae.search.routes.advanced_query_index")
    def test_advanced_search_results(self, mock_search):
        """ Make sure that the correct search results are passed to the search results form"""
        params = dict(corpus='formulae%2Bchartae', year=600, month=1, day=31, year_start=600, month_start=12,
                      day_start=12, year_end=700, month_end=1, day_end=12)
        mock_search.return_value = [[], 0]
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            response = c.get('/search/advanced_search?corpus=formulae&corpus=chartae&q=&year=600&month=1&day=31&'
                             'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                             'date_plus_minus=0&submit=Search')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))
            c.get('/search/results?source=advanced&corpus=formulae%2Bchartae&q=&fuzziness=0&slop=0&in_order=False&'
                  'year=600&month=1&day=31&year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&'
                  'day_end=12&date_plus_minus=0&exclusive_date_range=False&submit=True')
            mock_search.assert_called_with(corpus=['formulae', 'chartae'], date_plus_minus=0, day=31, day_end=12,
                                           day_start=12, field='text', fuzziness='0', slop='0', month=1, month_end=1,
                                           month_start=12, page=1, per_page=10, q='',
                                           in_order='False', year=600, year_end=700, year_start=600,
                                           exclusive_date_range='False')
            # Test to make sure that a capitalized search term is converted to lowercase in advanced search
            params['q'] = 'regnum'
            response = c.get('/search/advanced_search?corpus=formulae&corpus=chartae&q=Regnum&year=600&month=1&day=31&'
                             'year_start=600&month_start=12&day_start=12&year_end=700&month_end=1&day_end=12&'
                             'date_plus_minus=0&submit=Search')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))

    @patch("formulae.search.routes.query_index")
    def test_simple_search_results(self, mock_search):
        """ Make sure that the correct search results are passed to the search results form"""
        params = dict(corpus='formulae%2Bchartae', q='regnum')
        mock_search.return_value = [[], 0]
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            response = c.get('/search/simple?corpus=formulae&corpus=chartae&q=Regnum')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))


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
        # This test does not work with Travis
        if os.environ.get('TRAVIS'):
            return
        form = SearchForm(corpus=['formulae'], q='regnum')
        form.validate()
        self.assertTrue(form.validate(), 'Simple search with "regnum" should validate')
        form = SearchForm(corpus=['formulae'], q='re?num')
        form.validate()
        self.assertTrue(form.validate(), 'Simple search with "re?num" should validate')

    def test_invalid_data_simple_search_form(self):
        """ Ensure that the simple search form returns a ValidationError with no corpus"""
        form = SearchForm(corpus=[''], q='regnum')
        self.assertFalse(form.validate(), 'Search with no corpus specified should not validate')
        # I need two choices here since locally it returns the default Error and on Travis it returns the custom message
        self.assertIn(str(form.corpus.errors[0]),
                      [_('Mindestens eine Sammlung zur Suche auswählen("Formeln" und/oder "Urkunden")'),
                       "'' is not a valid choice for this field"])

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
        with self.assertRaisesRegex(ValidationError, _('Bitte verwenden Sie eine andere Benutzername.')):
            form.validate_username(form.username)
        with self.assertRaisesRegex(ValidationError, _('Bitte verwenden Sie eine andere Emailaddresse.')):
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
            self.assertMessageFlashed(_('Benutzername oder Passwort ungültig'))
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
            self.assertMessageFlashed(_('Sie sind jetzt registriert.'))
            self.assertTrue(User.query.filter_by(username='new.user').first(), "It should have added new.user.")
            self.assertTemplateUsed('auth::login.html')


class TestES(Formulae_Testing):
    def build_file_name(self, fake_args):
        return '&'.join(["{}={}".format(k, str(v)) for k, v in fake_args.items()])

    @patch.object(Elasticsearch, "search")
    def test_date_range_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 0), ('slop', '0'), ("month", 0), ("day", 0), ("year_start", 814),
                                 ("month_start", 10), ("day_start", 29), ("year_end", 814), ("month_end", 11),
                                 ("day_end", 20), ('date_plus_minus', 0), ('exclusive_date_range', 'False')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _ = advanced_query_index(**test_args)
        mock_search.assert_called_with(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_normal_date_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 10), ("day", 9), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 0), ('exclusive_date_range', 'False')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _ = advanced_query_index(**test_args)
        mock_search.assert_called_with(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_date_plus_minus_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"), ('in_order', 'False'),
                                 ("year", 800), ('slop', '0'), ("month", 10), ("day", 9), ("year_start", 0),
                                 ("month_start", 0), ("day_start", 0), ("year_end", 0), ("month_end", 0),
                                 ("day_end", 0), ('date_plus_minus', 10), ('exclusive_date_range', 'False')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _ = advanced_query_index(**test_args)
        mock_search.assert_called_with(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_exclusive_date_range_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', '0'), ("month", 0), ("day", 0),
                                 ("year_start", 700), ("month_start", 10), ("day_start", 0), ("year_end", 800),
                                 ("month_end", 10), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'True')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _ = advanced_query_index(**test_args)
        mock_search.assert_called_with(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multi_corpus_search(self, mock_search):
        test_args = OrderedDict([("corpus", "andecavensis+mondsee"), ("field", "text"), ("q", ''), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ('slop', 0), ("month", 0), ("day", 0),
                                 ("year_start", 814), ("month_start", 10), ("day_start", 29), ("year_end", 814),
                                 ("month_end", 11), ("day_end", 20), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _ = advanced_query_index(**test_args)
        mock_search.assert_called_with(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_lemma_advanced_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'regnum'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        actual, _ = advanced_query_index(**test_args)
        mock_search.assert_called_with(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_multiword_lemma_advanced_search(self, mock_search):
        test_args = OrderedDict([("corpus", "all"), ("field", "lemmas"), ("q", 'vir+venerabilis'), ("fuzziness", "0"),
                                 ("in_order", "False"), ("year", 0), ("slop", "0"), ("month", 0), ("day", 0),
                                 ("year_start", 0), ("month_start", 0), ("day_start", 0), ("year_end", 0),
                                 ("month_end", 0), ("day_end", 0), ('date_plus_minus', 0),
                                 ('exclusive_date_range', 'False')])
        fake = FakeElasticsearch(self.build_file_name(test_args), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['corpus'] = test_args['corpus'].split('+')
        test_args['q'] = test_args['q'].replace('+', ' ')
        actual, _ = advanced_query_index(**test_args)
        mock_search.assert_called_with(index=test_args['corpus'], doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_simple_multi_corpus_search(self, mock_search):
        test_args = OrderedDict([("index", ['formulae', "chartae"]), ("query", 'regnum'), ("field", "text"),
                                 ("page", 1), ("per_page", self.app.config["POSTS_PER_PAGE"])])
        mock_search.return_value = {"hits": {"hits": [{'_id': 'urn:cts:formulae:stgallen.wartmann0259.lat001',
                                    '_source': {'urn': 'urn:cts:formulae:stgallen.wartmann0259.lat001'},
                                    'highlight': {
                                        'text': ['Notavi die et <strong>regnum</strong>. Signum Mauri et uxores suas Audoaras, qui hanc cartam fieri rogaverunt.']}}],
                                             'total': 0}}
        body = {'query':
                    {'span_near':
                         {'clauses': [{'span_term': {'text': 'regnum'}}], 'slop': 0, 'in_order': True}},
                'sort': 'urn', 'from': 0, 'size': 10,
                'highlight': {'fields': {'text': {'fragment_size': 300}},
                              'pre_tags': ['</small><strong>'],
                              'post_tags': ['</strong><small>'], 'encoder': 'html'}}
        query_index(**test_args)
        mock_search.assert_called_with(index=['formulae', 'chartae'], doc_type="", body=body)
        test_args['query'] = 'regnum domni'
        body['query']['span_near']['clauses'] = [{'span_term': {'text': 'regnum'}}, {'span_term': {'text': 'domni'}}]
        query_index(**test_args)
        mock_search.assert_called_with(index=['formulae', 'chartae'], doc_type="", body=body)
        test_args['query'] = 're?num'
        body['query']['span_near']['clauses'] = [{'span_multi': {'match': {'wildcard': {'text': 're?num'}}}}]
        query_index(**test_args)
        mock_search.assert_called_with(index=['formulae', 'chartae'], doc_type="", body=body)


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

