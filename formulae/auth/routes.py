from flask import flash, url_for, request, redirect, current_app
from flask_login import current_user, login_user, logout_user, login_required
from flask_babel import _, refresh
from werkzeug.urls import url_parse
from .forms import LoginForm, PasswordChangeForm, LanguageChangeForm, ResetPasswordRequestForm, ResetPasswordForm, \
    RegistrationForm, EmailChangeForm, AddSavedPageForm
from formulae.models import User, SavedPage
from .email import send_password_reset_email, send_email_reset_email
from formulae.auth import bp
from formulae import db


@bp.route('/login', methods=['GET', 'POST'])
def r_login():
    """ login form

    :return: template, page title, forms
    """
    if current_user.is_authenticated:
        flash(_('Sie sind schon eingeloggt.'))
        return redirect(url_for('auth.r_user'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash(_('Benutzername oder Passwort ist ungültig'))
            return redirect(url_for('auth.r_login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            return redirect(url_for('auth.r_user'))
        return redirect(next_page)
    return current_app.config['nemo_app'].render(template='auth::login.html', title=_('Einloggen'), forms=[form], purpose='login', url=dict())


@bp.route('/logout')
def r_logout() -> redirect:
    """ user logout

    :return: redirect to login page
    """
    logout_user()
    return redirect(url_for('auth.r_login'))


@bp.route('/user/<username>', methods=["GET", "POST"])
@bp.route('/user', methods=["GET", "POST"])
@login_required
def r_user(username: str = None):
    """ profile page for user. Initially used to change user information (e.g., password, email, etc.)

    :return: template, page title, forms
    """
    username = current_user.username
    password_form = PasswordChangeForm()
    if password_form.validate_on_submit():
        user = User.query.filter_by(username=username).first_or_404()
        if not user.check_password(password_form.old_password.data):
            flash(_("Das ist nicht Ihr aktuelles Passwort."))
            return redirect(url_for('auth.r_user'))
        user.set_password(password_form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(_("Sie haben Ihr Passwort erfolgreich geändert."))
        return redirect(url_for('auth.r_login'))
    language_form = LanguageChangeForm()
    if language_form.validate_on_submit():
        current_user.default_locale = language_form.new_locale.data
        db.session.commit()
        refresh()
        flash(_("Sie haben Ihre Benutzersprache erfolgreich geändert."))
        return redirect(url_for('auth.r_user'))
    email_form = EmailChangeForm()
    if email_form.validate_on_submit():
        send_email_reset_email(current_user, email_form.email.data)
        flash(_("Ein Link zur Bestätigung dieser Änderung wurde an Ihre neue Emailadresse zugeschickt"))
        return redirect(url_for('auth.r_user'))
    elif request.method == 'GET':
        language_form.new_locale.data = current_user.default_locale
    return current_app.config['nemo_app'].render(template="auth::login.html", title=_("Benutzerprofil ändern"),
                                                 forms=[password_form, language_form, email_form], username=username,
                                                 purpose='user', url=dict())


@bp.route("/reset_password/<token>", methods=["GET", "POST"])
def r_reset_password(token):
    """ Route for the actual resetting of the password

    :param token: the token that was previously sent to the user through the r_reset_password_request route
    :return: template, form
    """
    if current_user.is_authenticated:
        flash(_('Sie sind schon eingeloggt. Sie können Ihr Password hier ändern.'))
        return redirect(url_for('auth.r_user'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('InstanceNemo.r_index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash(_('Ihr Passwort wurde erfolgreich zurückgesetzt.'))
        return redirect(url_for('auth.r_login'))
    return current_app.config['nemo_app'].render(template='auth::reset_password.html', title=_('Passwort zurücksetzen'), form=form, url=dict())


@bp.route("/reset_password_request", methods=["GET", "POST"])
def r_reset_password_request():
    """ Route for password reset request

    """
    if current_user.is_authenticated:
        flash(_('Sie sind schon eingeloggt. Sie können Ihr Password hier ändern.'))
        return redirect(url_for('auth.r_user'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash(_('Die Anweisung zum Zurücksetzen Ihres Passworts wurde Ihnen per E-mail zugeschickt'))
        return redirect(url_for('auth.r_login'))
    return current_app.config['nemo_app'].render(template='auth::reset_password_request.html', title=_('Passwort zurücksetzen'), form=form, url=dict())


@bp.route("/reset_email/<token>", methods=["GET", "POST"])
@login_required
def r_reset_email(token):
    """ Route to confirm that the email should be reset
    I don't think I need an email reset route since this will be done on the User's user page.

    :param token: the token that was previously sent to the user through the r_reset_password_request route
    :return: template, form
    """
    try:
        user, old_email, new_email = User.verify_reset_email_token(token)
    except TypeError:
        flash(_('Der Token ist nicht gültig. Versuchen Sie es erneut.'))
        return redirect(url_for('auth.r_user'))
    if not user or user.id != current_user.id or current_user.email != old_email:
        flash(_('Ihre Emailaddresse wurde nicht geändert. Versuchen Sie es erneut.'))
        return redirect(url_for('auth.r_user'))
    else:
        user.email = new_email
        db.session.commit()
        flash(_('Ihr Email wurde erfolgreich geändert. Sie lautet jetzt') + ' {}.'.format(new_email))
        return redirect(url_for('auth.r_user'))


@bp.route("/register", methods=['GET', 'POST'])
def r_register():
    """ Route for new users to register for accounts

    :return: template, form
    """
    if current_user.is_authenticated:
        flash(_('Sie sind schon eingeloggt.'))
        return redirect(url_for('auth.r_user'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, default_locale=form.default_locale.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        current_user.default_locale = form.default_locale.data
        refresh()
        flash(_('Sie sind nun registriert.'))
        return redirect(url_for('auth.r_login'))
    return current_app.config['nemo_app'].render(template='auth::register.html', title=_('Anmelden'), form=form, url=dict())


@bp.route("/save_page", methods=['GET', 'POST'])
@login_required
def r_save_page():
    """ Route for users to save pages to their user account

    :return: template, form
    """
    user_id = current_user.id
    form = AddSavedPageForm()
    url = url_parse(request.referrer)
    if form.validate_on_submit():
        if url.netloc != url_parse(request.root_url).netloc:
            flash(_('Diese URL ist nicht Teil der Werkstatt.'))
            return redirect(url_for('InstanceNemo.r_index'))
        page = SavedPage(name=form.name.data or url.path, url='?'.join([url.path, url.query]), user_id=user_id)
        db.session.add(page)
        db.session.commit()
        flash(_('Seite gespeichert.'))
        return redirect(page.url)
    return current_app.config['nemo_app'].render(template='auth::save_page.html', title=_('Diese Seite speichern'), form=form, url=dict())


@bp.route("/saved_pages", methods=['GET'])
@login_required
def r_saved_pages():
    """ Route for users to retrieve the saved pages from their user account

    :return: template, form
    """
    page_list = [p for p in current_user.pages]
    return current_app.config['nemo_app'].render(template='auth::saved_pages.html', title=_('Gespeicherte Seiten'), pages=page_list, url=dict())




@bp.route("/remove_page/<page_id>", methods=['GET'])
@login_required
def r_remove_page(page_id):
    """ Route for users to retrieve the saved pages from their user account

    :return: template, form
    """
    page = SavedPage.query.get(int(page_id))
    db.session.delete(page)
    db.session.commit()
    flash(_('Seite nicht mehr gespeichert.'))
    return redirect(url_for('.r_saved_pages'))
