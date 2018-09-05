from flask import url_for, Markup, g, session
from flask_login import current_user, login_required
from flask_babel import _, refresh, get_locale, lazy_gettext
from werkzeug.utils import redirect
from flask_nemo import Nemo
from MyCapytain.common.constants import Mimetypes
from MyCapytain.resources.prototypes.cts.inventory import CtsWorkMetadata, CtsEditionMetadata
from MyCapytain.errors import UnknownCollection
from formulae.search.forms import SearchForm
from lxml import etree
from .errors.handlers import e_internal_error, e_not_found_error, e_unknown_collection_error
import re


class NemoFormulae(Nemo):

    ROUTES = [
        ("/", "r_index", ["GET"]),
        ("/collections", "r_collections", ["GET"]),
        ("/collections/<objectId>", "r_collection", ["GET"]),
        ("/corpus/<objectId>", "r_corpus", ["GET"]),
        ("/text/<objectId>/references", "r_references", ["GET"]),
        ("/texts/<objectIds>/passage/<subreferences>", "r_multipassage", ["GET"]),
        ("/add_collections/<objectIds>/<reffs>", "r_add_text_collections", ["GET"]),
        ("/add_collection/<objectId>/<objectIds>/<reffs>", "r_add_text_collection", ["GET"]),
        ("/add_text/<objectId>/<objectIds>/<reffs>", "r_add_text_corpus", ["GET"]),
        ("/lexicon/<objectId>", "r_lexicon", ["GET"]),
        ("/lang", "r_set_language", ["GET", "POST"]),
        ("/sub_elements/<coll>/<objectIds>/<reffs>", "r_add_sub_elements", ["GET"]),
        ("/sub_elements/<coll>", "r_get_sub_elements", ["GET"])
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
        "r_index", "r_collections", "r_collection", "r_references", "r_multipassage", "r_lexicon",
        "r_add_text_collections", "r_add_text_collection", "r_corpus", "r_add_text_corpus"
    ]

    OPEN_COLLECTIONS = []

    LANGUAGE_MAPPING = {"lat": lazy_gettext('Latin'), "deu": lazy_gettext("German"), "fre": lazy_gettext("French"),
                        "eng": lazy_gettext("English")}

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

    def get_locale(self):
        """ Retrieve the best matching locale using request headers

        .. note:: Probably one of the thing to enhance quickly.

        :rtype: str
        """
        best_match = str(get_locale())
        lang = self.__default_lang__
        if best_match == "de":
            lang = "ger"
        elif best_match == "fr":
            lang = "fre"
        elif best_match == "en":
            lang = "eng"
        return lang

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

    def r_collection(self, objectId, lang=None):
        data = super(NemoFormulae, self).r_collection(objectId, lang=lang)
        members = data['collections']['members']
        if len(members) == 1:
            return redirect(url_for('.r_corpus', objectId=members[0]['id'], lang=lang))
        data['template'] = "main::sub_collections.html"
        return data

    def r_corpus(self, objectId, lang=None):
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template and collections contained in given collection
        :rtype: {str: Any}
        """
        collection = self.resolver.getMetadata(objectId)
        r = {}
        for m in list(self.resolver.getMetadata(collection.id).readableDescendants):
            if "salzburg" in m.id:
                par = '-'.join(m.parent.id.split('-')[1:])
                template = "main::sub_collection.html"
                metadata = (m.id, self.LANGUAGE_MAPPING[m.lang])
            elif "elexicon" in m.id:
                par = m.parent.id.split('.')[-1][0].capitalize()
                template = "main::elex_collection.html"
                metadata = (m.id, m.parent.id.split('.')[-1], self.LANGUAGE_MAPPING[m.lang])
            else:
                par = int(re.sub(r'.*?(\d+)', r'\1', m.parent.id))
                template = "main::sub_collection.html"
                metadata = (m.id, self.LANGUAGE_MAPPING[m.lang])
            if par in r.keys():
                r[par]["versions"].append(metadata)
            else:
                r[par] = {"short_regest": str(m.get_description()).split(':')[0],
                          "regest": ':'.join(str(m.get_description()).split(':')[1:]) or str(m.get_description()),
                          "versions": [metadata]}
        for k, v in r.items():
            r[k]['versions'] = sorted(v['versions'], reverse=True)
        return {
            "template": template,
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                },
                "readable": r,
                "parents": self.make_parents(collection, lang=lang)
            }
        }

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
        """ Route to browse a top-level collection and add another text to the view

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template and collections contained in given collection
        :rtype: {str: Any}
        """
        collection = self.resolver.getMetadata(objectId)
        members = self.make_members(collection, lang=lang)
        if len(members) == 1:
            return redirect(url_for('.r_add_text_corpus', objectId=members[0]['id'],
                                    objectIds=objectIds, reffs=reffs, lang=lang))
        return {
            "template": "main::sub_collections.html",
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                },
                "members": members,
                "parents": self.make_parents(collection, lang=lang)
            },
            "prev_texts": objectIds,
            "prev_reffs": reffs
        }

    def r_add_text_corpus(self, objectId, objectIds, reffs, lang=None):
        """ Route to browse collections and add another text to the view

        :param objectId: Collection identifier
        :type objectId: str
        :param lang: Lang in which to express main data
        :type lang: str
        :return: Template and collections contained in given collection
        :rtype: {str: Any}
        """
        collection = self.resolver.getMetadata(objectId)
        r = {}
        for m in list(self.resolver.getMetadata(collection.id).readableDescendants):
            if "salzburg" in m.id:
                par = '-'.join(m.parent.id.split('-')[1:])
                template = "main::sub_collection.html"
                metadata = (m.id, self.LANGUAGE_MAPPING[m.lang])
            elif "elexicon" in m.id:
                par = m.parent.id.split('.')[-1][0].capitalize()
                template = "main::elex_collection.html"
                metadata = (m.id, m.parent.id.split('.')[-1], self.LANGUAGE_MAPPING[m.lang])
            else:
                par = int(re.sub(r'.*?(\d+)', r'\1', m.parent.id))
                template = "main::sub_collection.html"
                metadata = (m.id, self.LANGUAGE_MAPPING[m.lang])
            if par in r.keys():
                r[par]["versions"].append(metadata)
            else:
                r[par] = {"short_regest": str(m.get_description()).split(':')[0],
                          "regest": ':'.join(str(m.get_description()).split(':')[1:]) or str(m.get_description()),
                          "versions": [metadata]}
        for k, v in r.items():
            r[k]['versions'] = sorted(v['versions'], reverse=True)
        return {
            "template": template,
            "collections": {
                "current": {
                    "label": str(collection.get_label(lang)),
                    "id": collection.id,
                    "model": str(collection.model),
                    "type": str(collection.type),
                },
                "readable": r,
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
        # if current_user.project_team is False and str(text.get_creator(lang)) not in self.OPEN_COLLECTIONS:
        #     pdf_path = self.pdf_folder + objectId.split(':')[-1] + '.pdf'
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

    def r_multipassage(self, objectIds, subreferences, translations=None, lang=None):
        """ Retrieve the text of the passage

        :param objectIds: Collection identifiers separated by '+'
        :type objectIds: str
        :param lang: Lang in which to express main data
        :type lang: str
        :param subreferences: Reference identifiers separated by '+'
        :type subreferences: str
        :param translations: A list of the other editions of this work
        :type translations: [str]
        :return: Template, collections metadata and Markup object representing the text
        :rtype: {str: Any}
        """
        ids = objectIds.split('+')
        passage_data = {'template': 'main::multipassage.html', 'objects': [], "translation": translations}
        subrefers = subreferences.split('+')
        for i, id in enumerate(ids):
            if subrefers[i] == "first":
                subref = self.resolver.getReffs(textId=id)[0]
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

    def extract_notes(self, text):
        """ Constructs a dictionary that contains all notes with their ids. This will allow the notes to be
        rendered anywhere on the page and not only where they occur in the text.

        :param text: the string to be transformed
        :return: dict('note_id': 'note_content')
        """
        with open(self._transform['notes']) as f:
            xslt = etree.XSLT(etree.parse(f))
        return str(xslt(etree.fromstring(text)))

    def r_add_sub_elements(self, coll, objectIds, reffs, lang=None):
        """ A convenience function to return all sub-corpora in all collections

        :return: dictionary with all the collections as keys and a list of the corpora in the collection as values
        """
        texts = self.r_add_text_collection(coll, objectIds, reffs, lang=lang)
        texts["template"] = 'main::sub_element_snippet.html'
        return texts

    def r_get_sub_elements(self, coll, objectIds='', reffs='', lang=None):
        """ A convenience function to return all sub-corpora in all collections

        :return: dictionary with all the collections as keys and a list of the corpora in the collection as values
        """
        texts = self.r_add_text_collection(coll, objectIds, reffs, lang=lang)
        texts["template"] = 'main::sub_element_snippet.html'
        return texts
