from config import Config
from capitains_nautilus.cts.resolver import NautilusCTSResolver
from formulae import create_app, db
from formulae.nemo import NemoFormulae
from formulae.models import User
import flask_testing
from formulae.search.forms import AdvancedSearchForm
from formulae.auth.forms import LoginForm, PasswordChangeForm, LanguageChangeForm, ResetPasswordForm, \
    ResetPasswordRequestForm
from flask_login import current_user


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
        # print(self.app.url_map)
        user = User.query.filter_by(username="project.member").first()
        with self.client as c:
            c.get('/', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/collections', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/collections/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/text/urn:cts:formulae:stgallen.wartmann0001.lat001/references', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+first', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/add_text/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/add_text/urn:cts:formulae:andecavensis.form001/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/search', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True)
            self.assertMessageFlashed('Please log in to access this page.')
            self.assertTemplateUsed('auth::login.html')

    def test_authorized_user(self):
        """ Make sure that all routes are open to authorized users"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            c.get('/', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')
            c.get('/auth/user/project.member', follow_redirects=True)
            self.assertTemplateUsed('auth::login.html')
            c.get('/collections', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/collections/urn:cts:formulae:stgallen', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            # r_references does not work right now.
            # c.get('/text/urn:cts:formulae:stgallen.wartmann0001.lat001/references', follow_redirects=True)
            # self.assertTemplateUsed('main::references.html')
            c.get('/texts/urn:cts:formulae:stgallen.wartmann0001.lat001+urn:cts:formulae:andecavensis.form001.lat001/passage/1+first', follow_redirects=True)
            self.assertTemplateUsed('main::multipassage.html')
            c.get('/add_text/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/add_text/urn:cts:formulae:andecavensis.form001/urn:cts:formulae:stgallen.wartmann0001.lat001/1', follow_redirects=True)
            self.assertTemplateUsed('main::collection.html')
            c.get('/lexicon/urn:cts:formulae:elexicon.abbas_abbatissa.deu001', follow_redirects=True)
            self.assertTemplateUsed('main::lexicon_modal.html')
            # An authenicated user who surfs to the login page should be redirected to index
            c.get('/auth/login', follow_redirects=True)
            self.assertTemplateUsed('main::index.html')


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

    def test_validate_invalid_advanced_search_form(self):
        """ Ensure that a form with invalid data does not validate"""
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


class TestAuth(Formulae_Testing):
    def test_correct_login(self):
        """ Ensure that login works with correct credentials"""
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
            self.assertMessageFlashed('Invalid username or password')
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
