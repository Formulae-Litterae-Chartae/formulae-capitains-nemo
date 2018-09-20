from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, EqualTo


class LoginForm(FlaskForm):
    username = StringField(_l('Benutzername'), validators=[DataRequired()])
    password = PasswordField(_l('Passwort'), validators=[DataRequired()])
    remember_me = BooleanField(_l('Eingeloggt bleiben'))
    submit = SubmitField(_l('Einloggen'))


class PasswordChangeForm(FlaskForm):
    title = _l('Passwort ändern')
    old_password = PasswordField(_l("Altes Passwort"), validators=[DataRequired()])
    password = PasswordField(_l("Passwort"), validators=[DataRequired()])
    password2 = PasswordField(_l("Passwort wiederholen"), validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField(_l("Passwort ändern"))


class LanguageChangeForm(FlaskForm):
    title = _l("Defaultsprache Ändern")
    new_locale = RadioField(choices=[('de', 'Deutsch'), ('en', 'English'), ('fr', 'Français')],
                            validators=[DataRequired()])
    submit = SubmitField(_l("Sprache Ändern"))


class ResetPasswordRequestForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    submit = SubmitField(_l('Email zum Zurücksetzen Ihres Passworts anfordern'))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l('Neues Passwort'), validators=[DataRequired()])
    password2 = PasswordField(_l('Neues Passwort wiederholen'), validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('Passwort zurücksetzen'))
