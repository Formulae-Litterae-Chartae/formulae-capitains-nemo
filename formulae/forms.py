from flask import request
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, ValidationError, Email, EqualTo
from .models import User

class LoginForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    remember_me = BooleanField(_l('Remember Me'))
    submit = SubmitField(_l('Sign In'))


class PasswordChangeForm(FlaskForm):
    old_password = PasswordField(_l("Old Password"), validators=[DataRequired()])
    password = PasswordField(_l("Password"), validators=[DataRequired()])
    password2 = PasswordField(_l("Repeat Password"), validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField(_l("Change Password"))


class SearchForm(FlaskForm):
    q = StringField(_l('Search'), validators=[DataRequired()])
    lemma_search = BooleanField(_l('Lemma'))
    fuzzy_search = BooleanField(_l('Fuzzy'))
    phrase_search = BooleanField(_l('Phrase'))

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'csrf_enabled' not in kwargs:
            kwargs['csrf_enabled'] = False
        super(SearchForm, self).__init__(*args, **kwargs)
