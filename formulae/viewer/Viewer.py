from flask import flash, url_for, request, redirect, current_app, render_template, Markup
from formulae.viewer import bp
from flask_babel import lazy_gettext as _l
from MyCapytain.common.constants import Mimetypes
from MyCapytain.resources.prototypes.cts.inventory import CtsWorkMetadata, CtsEditionMetadata
from MyCapytain.errors import UnknownCollection
from rdflib.namespace import DCTERMS, DC
from datetime import date

def get_passage(objectId, subreference, lang=None):
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
    collection = current_app.config['nemo_app'].get_collection(objectId)
    if isinstance(collection, CtsWorkMetadata):
        editions = [t for t in collection.children.values() if isinstance(t, CtsEditionMetadata)]
        if len(editions) == 0:
            raise UnknownCollection('{}.{}'.format(collection.get_label(lang), subreference) + _l(' wurde nicht gefunden.'))
        objectId = str(editions[0].id)
        collection = current_app.config['nemo_app'].get_collection(objectId)
    try:
        text = current_app.config['nemo_app'].get_passage(objectId=objectId, subreference=subreference)
    except IndexError:
        new_subref = current_app.config['nemo_app'].get_reffs(objectId)[0][0]
        text = current_app.config['nemo_app'].get_passage(objectId=objectId, subreference=new_subref)
        flash('{}.{}'.format(collection.get_label(lang), subreference) + _l(' wurde nicht gefunden. Der ganze Text wird angezeigt.'))
        subreference = new_subref
    passage = current_app.config['nemo_app'].transform(text, text.export(Mimetypes.PYTHON.ETREE), objectId)
    metadata = current_app.config['nemo_app'].resolver.getMetadata(objectId=objectId)
    if 'notes' in current_app.config['nemo_app']._transform:
        notes = current_app.config['nemo_app'].extract_notes(passage)
    else:
        notes = ''
    prev, next = current_app.config['nemo_app'].get_siblings(objectId, subreference, text)
    return {
        "objectId": objectId,
        "subreference": subreference,
        "collections": {
            "current": {
                "label": collection.get_label(lang),
                "id": collection.id,
                "model": str(collection.model),
                "type": str(collection.type),
                "author": str(metadata.metadata.get_single(DC.creator, lang=None)) or text.get_creator(lang),
                "title": text.get_title(lang),
                "description": text.get_description(lang),
                "citation": collection.citation,
                # "coins": current_app.config['nemo_app'].make_coins(collection, text, subreference, lang=lang),
                "pubdate": str(metadata.metadata.get_single(DCTERMS.created, lang=None)),
                "publang": str(metadata.metadata.get_single(DC.language, lang=None)),
                "publisher": str(metadata.metadata.get_single(DC.publisher, lang=None)),
                'lang': collection.lang
            },
            "parents": current_app.config['nemo_app'].make_parents(collection, lang=lang)
        },
        "text_passage": Markup(passage),
        "notes": Markup(notes),
        "prev": prev,
        "next": next,
        "open_regest": objectId not in current_app.config['nemo_app'].half_open_texts,
        "show_notes": objectId in current_app.config['nemo_app'].OPEN_NOTES,
        "urldate": "{:04}-{:02}-{:02}".format(date.today().year, date.today().month, date.today().day)
    }


def get_lexicon(objectId, subreference, lang=None):

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

    collection = current_app.config['nemo_app'].get_collection(objectId)
    if isinstance(collection, CtsWorkMetadata):
        editions = [t for t in collection.children.values() if isinstance(t, CtsEditionMetadata)]
        if len(editions) == 0:
            raise UnknownCollection('{}.{}'.format(collection.get_label(lang), subreference) + _l(' wurde nicht gefunden.'))
        objectId = str(editions[0].id)
        collection = current_app.config['nemo_app'].get_collection(objectId)
    try:
        text = current_app.config['nemo_app'].get_passage(objectId=objectId, subreference=subreference)
    except IndexError:
        new_subref = current_app.config['nemo_app'].get_reffs(objectId)[0][0]
        text = current_app.config['nemo_app'].get_passage(objectId=objectId, subreference=new_subref)
        flash('{}.{}'.format(collection.get_label(lang), subreference) + _l(' wurde nicht gefunden. Der ganze Text wird angezeigt.'))
        subreference = new_subref
    passage = current_app.config['nemo_app'].transform(text, text.export(Mimetypes.PYTHON.ETREE), objectId)
    metadata = current_app.config['nemo_app'].resolver.getMetadata(objectId=objectId)
    if 'notes' in current_app.config['nemo_app']._transform:
        notes = current_app.config['nemo_app'].extract_notes(passage)
    else:
        notes = ''
    prev, next = current_app.config['nemo_app'].get_siblings(objectId, subreference, text)
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
                "author": str(metadata.metadata.get_single(DC.creator, lang=None)) or text.get_creator(lang),
                "title": text.get_title(lang),
                "description": text.get_description(lang),
                "citation": collection.citation,
                #"coins": current_app.config['nemo_app'].make_coins(collection, text, subreference, lang=lang),
                "pubdate": str(metadata.metadata.get_single(DCTERMS.created, lang=None)),
                "publang": str(metadata.metadata.get_single(DC.language, lang=None)),
                "publisher": str(metadata.metadata.get_single(DC.publisher, lang=None)),
                'lang': collection.lang
            },
            "parents": current_app.config['nemo_app'].make_parents(collection, lang=lang)
        },
        "text_passage": Markup(passage),
        "notes": Markup(notes),
        "prev": prev,
        "next": next,
        "open_regest": objectId not in current_app.config['nemo_app'].half_open_texts,
        "show_notes": objectId in current_app.config['nemo_app'].OPEN_NOTES,
        "urldate": "{:04}-{:02}-{:02}".format(date.today().year, date.today().month, date.today().day)
    }
