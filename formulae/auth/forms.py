from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from formulae.models import User


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
    title = _l("Benutzersprache Ändern")
    new_locale = RadioField(choices=[('de', 'Deutsch'), ('en', 'English'), ('fr', 'Français')],
                            validators=[DataRequired()])
    submit = SubmitField(_l("Sprache ändern"))


class ResetPasswordRequestForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    submit = SubmitField(_l('Email zum Zurücksetzen Ihres Passworts anfordern'))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l('Neues Passwort'), validators=[DataRequired()])
    password2 = PasswordField(_l('Neues Passwort wiederholen'), validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('Passwort zurücksetzen'))


class RegistrationForm(FlaskForm):
    username = StringField(_l('Benutzername'), validators=[DataRequired()])
    email = StringField(_l('Email'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Passwort'), validators=[DataRequired()])
    password2 = PasswordField(_l('Passwort wiederholen'), validators=[DataRequired(), EqualTo('password')])
    default_locale = RadioField(_l('Benutzersprache'), choices=[('de', 'Deutsch'), ('en', 'English'), ('fr', 'Français')],
                                validators=[DataRequired()], default='de')
    submit = SubmitField(_l('Anmelden'))

    def validate_username(self, username: StringField):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError(_l('Bitte wählen Sie einen anderen Benutzername.'))

    def validate_email(self, email: StringField):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError(_l('Bitte wählen Sie eine andere Emailaddresse.'))
