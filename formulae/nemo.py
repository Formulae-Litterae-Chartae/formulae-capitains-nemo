from flask import flash, url_for, Markup, request, g, session, render_template
from flask_login import current_user, login_user, logout_user, login_required
from flask_babel import _, refresh
from werkzeug.utils import redirect
from werkzeug.urls import url_parse
from flask_nemo import Nemo
from MyCapytain.common.constants import Mimetypes
from MyCapytain.resources.prototypes.cts.inventory import CtsWorkMetadata, CtsEditionMetadata
from MyCapytain.errors import UnknownCollection
from math import ceil
from .app import db, resolver
from .forms import LoginForm, PasswordChangeForm, SearchForm, LanguageChangeForm, ResetPasswordRequestForm, ResetPasswordForm
from lxml import etree
from .models import User
from .search import query_index
from .email import send_password_reset_email
from .errors.handlers import e_internal_error, e_not_found_error, e_unknown_collection_error


class NemoFormulae(Nemo):

    ROUTES = [
        ("/", "r_index", ["GET"]),
        ("/collections", "r_collections", ["GET"]),
        ("/collections/<objectId>", "r_collection", ["GET"]),
        ("/text/<objectId>/references", "r_references", ["GET"]),
        ("/texts/<objectIds>/passage/<subreferences>", "r_multipassage", ["GET"]),
        ("/login", "r_login", ["GET", "POST"]),
        ("/logout", "r_logout", ["GET"]),
        ("/user/<username>", "r_user", ["GET", "POST"]),
        ("/add_text/<objectIds>/<reffs>", "r_add_text_collections", ["GET"]),
        ("/add_text/<objectId>/<objectIds>/<reffs>", "r_add_text_collection", ["GET"]),
        ("/search", "r_search", ["GET"]),
        ("/lexicon/<objectId>", "r_lexicon", ["GET"]),
        ("/lang", "r_set_language", ["GET", "POST"]),
        ("/reset_password_request", "r_reset_password_request", ["GET", "POST"]),
        ("/reset_password/<token>", "r_reset_password", ["GET", "POST"])
    ]
    SEMANTIC_ROUTES = [
        "r_collection", "r_references", "r_multipassage"
    ]

    FILTERS = [
        "f_formatting_passage_reference",
        "f_i18n_iso",
        "f_order_resource_by_lang",
        "f_hierarchical_passages",
        "f_is_str",
        "f_i18n_citation_type",
        "f_slugify",
        "f_make_members"
    ]

    CACHED = [
        # Routes
        "r_index", "r_collection", "r_collections", "r_references", "r_assets", "r_multipassage",
        # Controllers
        "get_inventory", "get_collection", "get_reffs", "get_passage", "get_siblings",
        # Translater
        "semantic", "make_coins", "expose_ancestors_or_children", "make_members", "transform",
        # Business logic
        # "view_maker", "route", #"render",
    ]

    PROTECTED = [
        "r_index", "r_collections", "r_collection", "r_references", "r_multipassage", "r_user", "r_search"
    ]

    OPEN_COLLECTIONS = []

    def __init__(self, *args, **kwargs):
        if "pdf_folder" in kwargs:
            self.pdf_folder = kwargs["pdf_folder"]
            del kwargs["pdf_folder"]
        super(NemoFormulae, self).__init__(*args, **kwargs)
        self.app.jinja_env.filters["remove_from_list"] = self.f_remove_from_list
        self.app.jinja_env.filters["join_list_values"] = self.f_join_list_values
        self.app.jinja_env.filters["replace_indexed_item"] = self.f_replace_indexed_item
        self.app.register_error_handler(404, e_not_found_error)
        self.app.register_error_handler(500, e_internal_error)
        self.app.before_request(self.before_request)

    def create_blueprint(self):
        """ Enhance original blueprint creation with error handling

        :rtype: flask.Blueprint
        """
        blueprint = super(NemoFormulae, self).create_blueprint()
        blueprint.register_error_handler(UnknownCollection, e_unknown_collection_error)
        # blueprint.register_error_handler(500, self.e_internal_error)
        # blueprint.register_error_handler(404, self.e_not_found_error)
        return blueprint

    def f_remove_from_list(self, l, i):
        """ remove item "i" from list "l"

        :param l: the list
        :param i: the item
        :return: the list without the item
        """
        l.remove(i)
        return l

    def f_join_list_values(self, l, s):
        """ join the values of "l" user the separator "s"

        :param l: the list of values
        :param s: the separator
        :return: a string of the values joined by the separator
        """
        return s.join(l).strip(s)

    def f_replace_indexed_item(self, l, i, v):
        """

        :param l: the list of values
        :param i: the index to be replace
        :param v: the value with which the indexed value will be replaced
        :return: new list
        """
        l[i] = v
        return l

    def r_set_language(self, code):
        """ Sets the seseion's language code which will be used for all requests

        :param code: The 2-letter language code
        :type code: str
        """
        session['locale'] = code
        refresh()

    def before_request(self):
        if current_user.is_authenticated:
            g.search_form = SearchForm()

    def view_maker(self, name, instance=None):
        """ Create a view

        :param name: Name of the route function to use for the view.
        :type name: str
        :return: Route function which makes use of Nemo context (such as menu informations)
        :rtype: function
        """
        # Avoid copy-pasta and breaking upon Nemo inside code changes by reusing the original view_maker function
        # Super will go to the parent class and you will use it's "view_maker" function
        route = super(NemoFormulae, self).view_maker(name, instance)
        if name in self.PROTECTED:
            route = login_required(route)
        return route

    def r_add_text_collections(self, objectIds, reffs, lang=None):
        """ Retrieve the top collections of the inventory

        :param lang: Lang in which to express main data
        :type lang: str
        :return: Collections information and template
        :rtype: {str: Any}
        """
        collection = self.resolver.getMetadata()
        return {
            "template": "main::collection.html",
            "current_label": collection.get_label(lang),
            "collections": {
                "members": self.make_members(collection, lang=lang)
            },
            "prev_texts": objectIds,
            "prev_reffs": reffs
        }

    def r_add_text_collection(self, objectId, objectIds, reffs, lang=None):
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template and collections contained in given collection
        :rtype: {str: Any}
        """
        collection = self.resolver.getMetadata(objectId)
        return {
            "template": "main::collection.html",
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                },
                "members": self.make_members(collection, lang=lang),
                "parents": self.make_parents(collection, lang=lang)
            },
            "prev_texts": objectIds,
            "prev_reffs": reffs
        }

    def get_first_passage(self, objectId):
        """ Provides a redirect to the first passage of given objectId

        :param objectId: Collection identifier
        :type objectId: str
        :return: Redirection to the first passage of given text
        """
        collection, reffs = self.get_reffs(objectId=objectId, export_collection=True)
        first, _ = reffs[0]
        return str(first)

    def r_passage(self, objectId, subreference, lang=None):
        """ Retrieve the text of the passage

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :param subreference: Reference identifier
        :type subreference: str
        :return: Template, collections metadata and Markup object representing the text
        :rtype: {str: Any}
        """
        pdf_path = ''
        collection = self.get_collection(objectId)
        if isinstance(collection, CtsWorkMetadata):
            editions = [t for t in collection.children.values() if isinstance(t, CtsEditionMetadata)]
            if len(editions) == 0:
                raise UnknownCollection(_("This work has no default edition"))
            return redirect(url_for(".r_passage", objectId=str(editions[0].id), subreference=subreference))
        text = self.get_passage(objectId=objectId, subreference=subreference)
        passage = self.transform(text, text.export(Mimetypes.PYTHON.ETREE), objectId)
        if 'notes' in self._transform:
            notes = self.extract_notes(passage)
        else:
            notes = ''
        prev, next = self.get_siblings(objectId, subreference, text)
        if current_user.project_team is False and str(text.get_creator(lang)) not in self.OPEN_COLLECTIONS:
            pdf_path = self.pdf_folder + objectId.split(':')[-1] + '.pdf'
        return {
            "template": "main::text.html",
            "objectId": objectId,
            "subreference": subreference,
            "collections": {
                "current": {
                    "label": collection.get_label(lang),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                    "author": text.get_creator(lang),
                    "title": text.get_title(lang),
                    "description": text.get_description(lang),
                    "citation": collection.citation,
                    "coins": self.make_coins(collection, text, subreference, lang=lang)
                },
                "parents": self.make_parents(collection, lang=lang)
            },
            "text_passage": Markup(passage),
            "notes": Markup(notes),
            "prev": prev,
            "next": next,
            "pdf_path": pdf_path
        }

    def r_multipassage(self, objectIds, subreferences, lang=None):
        """ Retrieve the text of the passage

        :param objectIds: Collection identifiers separated by '+'
        :type objectIds: str
        :param lang: Lang in which to express main data
        :type lang: str
        :param subreferences: Reference identifiers separated by '+'
        :type subreferences: str
        :return: Template, collections metadata and Markup object representing the text
        :rtype: {str: Any}
        """
        ids = objectIds.split('+')
        passage_data = {'template': 'main::multipassage.html', 'objects': []}
        subrefers = subreferences.split('+')
        for i, id in enumerate(ids):
            if subrefers[i] == "first":
                subref = resolver.getReffs(textId=id)[0]
            else:
                subref = subrefers[i]
            d = self.r_passage(id, subref, lang=lang)
            del d['template']
            passage_data['objects'].append(d)
        return passage_data

    def r_lexicon(self, objectId, lang=None):
        """ Retrieve the eLexicon entry for a word

        :param objectId: Collection identifiers separated by '+'
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template, collections metadata and Markup object representing the text
        :rtype: {str: Any}
        """
        subreference = "1"
        d = self.r_passage(objectId, subreference, lang=lang)
        d['template'] = 'main::lexicon_modal.html'
        return d

    def r_login(self):
        """ login form

        :return: template, page title, forms
        :rtype: {str: Any}
        """
        if current_user.is_authenticated:
            return redirect(url_for('.r_index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user is None or not user.check_password(form.password.data):
                flash(_('Invalid username or password'))
                return redirect(url_for('.r_login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                return redirect(url_for('.r_index'))
            return redirect(next_page)
        return {'template': 'main::login.html', 'title': _('Sign In'), 'forms': [form], 'purpose': 'login'}

    def r_logout(self):
        """ user logout

        :return: redirect to login page
        """
        logout_user()
        return redirect(url_for('.r_login'))

    def r_user(self, username):
        """ profile page for user. Initially used to change user information (e.g., password, email, etc.)

        :return: template, page title, forms
        :rtype: {str: Any}
        """
        password_form = PasswordChangeForm()
        if password_form.validate_on_submit():
            user = User.query.filter_by(username=username).first_or_404()
            if not user.check_password(password_form.old_password.data):
                flash(_("This is not your existing password."))
                return redirect(url_for('.r_user'))
            user.set_password(password_form.password.data)
            db.session.add(user)
            db.session.commit()
            flash(_("You have successfully changed your password."))
            return redirect(url_for('.r_login'))
        language_form = LanguageChangeForm()
        if language_form.validate_on_submit():
            current_user.default_locale = language_form.new_locale.data
            db.session.commit()
            flash(_("You have successfully changed your default language."))
            return redirect(url_for('.r_user', username=username))
        elif request.method == 'GET':
            language_form.new_locale.data = current_user.default_locale
        return {'template': "main::login.html", "title": _("Edit Profile"),
                "forms": [password_form, language_form], "username": username, 'purpose': 'user'}

    def r_search(self):
        if not g.search_form.validate():
            return redirect(url_for('.r_index'))
        page = request.args.get('page', 1, type=int)
        if request.args.get('fuzzy_search'):
            fuzziness = 'y'
        else:
            fuzziness = 'n'
        if request.args.get('lemma_search') == 'y':
            field = 'lemmas'
        else:
            field = 'text'
        # Unlike in the Flask Megatutorial, I need to specifically pass the field name (here 'text') and instead
        # of 'current_app.config', I can use self.app since that will always be the current_app instance
        # The index value is ignored for the simple search since all indices are searched
        posts, total = query_index('formulae', field, g.search_form.q.data, page, self.app.config['POSTS_PER_PAGE'],
                                   fuzziness, request.args.get('phrase_search'))
        first_url = url_for('.r_search', q=g.search_form.q.data,
                           lemma_search=request.args.get('lemma_search'),
                           page=1,
                           fuzzy_search=request.args.get('fuzzy_search'),
                           phrase_search=request.args.get('phrase_search')) \
            if page > 1 else None
        next_url = url_for('.r_search', q=g.search_form.q.data,
                           lemma_search=request.args.get('lemma_search'),
                           page=page + 1,
                           fuzzy_search=request.args.get('fuzzy_search'),
                           phrase_search=request.args.get('phrase_search')) \
            if total > page * self.app.config['POSTS_PER_PAGE'] else None
        prev_url = url_for('.r_search', q=g.search_form.q.data,
                           lemma_search=request.args.get('lemma_search'),
                           page=page - 1,  fuzzy_search=request.args.get('fuzzy_search'),
                           phrase_search=request.args.get('phrase_search')) \
            if page > 1 else None
        total_pages = int(ceil(total / self.app.config['POSTS_PER_PAGE']))
        page_urls = []
        if total_pages > 12:
            page_urls.append((1, url_for('.r_search', q=g.search_form.q.data,
                               lemma_search=request.args.get('lemma_search'),
                               page=1,  fuzzy_search=request.args.get('fuzzy_search'),
                               phrase_search=request.args.get('phrase_search'))))
            # page_num will be at most 12 members long. This should allow searches with many results to be displayed better.
            for page_num in range(max(page - 5, 2), min(page + 5, total_pages)):
                page_urls.append((page_num, url_for('.r_search', q=g.search_form.q.data,
                               lemma_search=request.args.get('lemma_search'),
                               page=page_num,  fuzzy_search=request.args.get('fuzzy_search'),
                               phrase_search=request.args.get('phrase_search'))))
            page_urls.append((total_pages, url_for('.r_search', q=g.search_form.q.data,
                               lemma_search=request.args.get('lemma_search'),
                               page=total_pages,  fuzzy_search=request.args.get('fuzzy_search'),
                               phrase_search=request.args.get('phrase_search'))))
        else:
            for page_num in range(1, total_pages + 1):
                page_urls.append((page_num, url_for('.r_search', q=g.search_form.q.data,
                               lemma_search=request.args.get('lemma_search'),
                               page=page_num,  fuzzy_search=request.args.get('fuzzy_search'),
                               phrase_search=request.args.get('phrase_search'))))
        last_url = url_for('.r_search', q=g.search_form.q.data,
                           lemma_search=request.args.get('lemma_search'),
                           page=total_pages,  fuzzy_search=request.args.get('fuzzy_search'),
                           phrase_search=request.args.get('phrase_search')) \
            if total > page * self.app.config['POSTS_PER_PAGE'] else None
        return {'template': 'main::search.html', 'title': _('Search'), 'posts': posts,
                'next_url': next_url, 'prev_url': prev_url, 'page_urls': page_urls,
                "first_url": first_url, "last_url": last_url, "current_page": page,
                "search_string": g.search_form.q.data}

    def extract_notes(self, text):
        """ Constructs a dictionary that contains all notes with their ids. This will allow the notes to be
        rendered anywhere on the page and not only where they occur in the text.

        :param text: the string to be transformed
        :return: dict('note_id': 'note_content')
        """
        with open(self._transform['notes']) as f:
            xslt = etree.XSLT(etree.parse(f))
        return str(xslt(etree.fromstring(text)))

    def r_reset_password_request(self):
        """ Route for password reset request

        """
        if current_user.is_authenticated:
            return redirect(url_for('.r_index'))
        form = ResetPasswordRequestForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                send_password_reset_email(user)
            flash(_('Check your email for the instructions to reset your password'))
            return redirect(url_for('.r_login'))
        return {'template': 'main::reset_password_request.html', 'title': _('Reset Password'), 'form': form}

    def r_reset_password(self, token):
        """ Route for the actual resetting of the password

        :param token: the token that was previously sent to the user through the r_reset_password_request route
        :return: template, form
        """
        if current_user.is_authenticated:
            return redirect(url_for('.r_index'))
        user = User.verify_reset_password_token(token)
        if not user:
            return redirect(url_for('.r_index'))
        form = ResetPasswordForm()
        if form.validate_on_submit():
            user.set_password(form.password.data)
            db.session.commit()
            flash(_('Your password has been reset.'))
            return redirect(url_for('.r_login'))
        return {'template': 'main::reset_password.html', 'title': _('Reset Your Password'), 'form': form}
