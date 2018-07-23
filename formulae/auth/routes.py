from flask import flash, url_for, request
from flask_login import current_user, login_user, logout_user, login_required
from flask_babel import _
from werkzeug.utils import redirect
from werkzeug.urls import url_parse
from .forms import LoginForm, PasswordChangeForm, LanguageChangeForm, ResetPasswordRequestForm, ResetPasswordForm
from formulae.models import User
from .email import send_password_reset_email
from formulae.auth import bp
from formulae.app import db


@bp.route('/login', methods=['GET', 'POST'])
def r_login():
    """ login form

    :return: template, page title, forms
    :rtype: {str: Any}
    """
    from formulae.app import nemo
    if current_user.is_authenticated:
        return redirect(url_for('InstanceNemo.r_index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash(_('Invalid username or password'))
            return redirect(url_for('auth.r_login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            return redirect(url_for('InstanceNemo.r_index'))
        return redirect(next_page)
    return nemo.render(template='auth::login.html', title=_('Sign In'), forms=[form], purpose='login', url=dict())


@bp.route('/logout')
def r_logout():
    """ user logout

    :return: redirect to login page
    """
    logout_user()
    return redirect(url_for('auth.r_login'))


@bp.route('/user/<username>', methods=["GET", "POST"])
@login_required
def r_user(username):
    """ profile page for user. Initially used to change user information (e.g., password, email, etc.)

    :return: template, page title, forms
    :rtype: {str: Any}
    """
    from formulae.app import nemo
    password_form = PasswordChangeForm()
    if password_form.validate_on_submit():
        user = User.query.filter_by(username=username).first_or_404()
        if not user.check_password(password_form.old_password.data):
            flash(_("This is not your existing password."))
            return redirect(url_for('auth.r_user'))
        user.set_password(password_form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(_("You have successfully changed your password."))
        return redirect(url_for('auth.r_login'))
    language_form = LanguageChangeForm()
    if language_form.validate_on_submit():
        current_user.default_locale = language_form.new_locale.data
        db.session.commit()
        flash(_("You have successfully changed your default language."))
        return redirect(url_for('auth.r_user', username=username))
    elif request.method == 'GET':
        language_form.new_locale.data = current_user.default_locale
    return nemo.render(template="auth::login.html", title=_("Edit Profile"),
                       forms=[password_form, language_form], username=username, purpose='user', url=dict())


@bp.route("/reset_password_request", methods=["GET", "POST"])
def r_reset_password_request():
    """ Route for password reset request

    """
    from formulae.app import nemo
    if current_user.is_authenticated:
        return redirect(url_for('InstanceNemo.r_index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash(_('Check your email for the instructions to reset your password'))
        return redirect(url_for('auth.r_login'))
    return nemo.render(template='auth::reset_password_request.html', title=_('Reset Password'), form=form, url=dict())


@bp.route("/reset_password/<token>", methods=["GET", "POST"])
def r_reset_password(token):
    """ Route for the actual resetting of the password

    :param token: the token that was previously sent to the user through the r_reset_password_request route
    :return: template, form
    """
    from formulae.app import nemo
    if current_user.is_authenticated:
        return redirect(url_for('InstanceNemo.r_index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('InstanceNemo.r_index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash(_('Your password has been reset.'))
        return redirect(url_for('auth.r_login'))
    return nemo.render(template='auth::reset_password.html', title=_('Reset Your Password'), form=form, url=dict())
