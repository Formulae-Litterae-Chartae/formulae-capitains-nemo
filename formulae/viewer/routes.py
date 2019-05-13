from flask import flash, url_for, request, redirect, current_app, render_template
from formulae.viewer import bp
from flask_babel import _
from formulae.viewer.Viewer import get_passage
import re
from json import load
from urllib import request
from MyCapytain.resources.prototypes.cts.inventory import CtsWorkMetadata, CtsEditionMetadata
from MyCapytain.errors import UnknownCollection
from flask_babel import lazy_gettext as _l

@bp.route("/<objectId>/<view>", methods=["GET"])
def new_tab(objectId, view):
    """
    :param objectId: Collection identifier
    :type objectId: str
    :param view: Number of the view for image in Loris
    :type view: int
    :return:
    """
    #test if the user have the access to the text or not
    if current_app.config['nemo_app'].check_project_team() is True or objectId in current_app.config['nemo_app'].open_texts:

        formulae=current_app.picture_file[objectId]

        #this viewer work when the library or archiv give an IIIF API for the external usage of theirs books
        if "manifest" in formulae:
            if "codex" in formulae:
                codex=formulae["codex"]
                manifest = url_for('viewer.static', filename=formulae["manifest"])
                return current_app.config['nemo_app'].render(template='viewer::miradorviewer.html', codex=codex, objectId=objectId,
                                                         manifest=manifest, url=dict())
            else:
                manifest = url_for('viewer.static', filename=formulae["manifest"])
                with open((current_app.IIIFmapping+"/"+formulae["manifest"]), "r") as f:
                    title = load(f)
                codex=title["label"]
                return current_app.config['nemo_app'].render(template='viewer::miradorviewer.html', manifest=manifest
                                                             ,objectId=objectId, codex=codex, url=dict())

        else:
            try:
                view = int(view)
            except:
                #exception when in the url view contains another character than number
                images = formulae['images']
                folios = formulae['folios']
                view=0
                flash( _('There is not an images for this formula. Showing the first page.'))
                if "/images/formulae-1" in str(images[view]):
                    link_picture=current_app.IIIFserver +str(images[view])
                else:
                    link_picture=str(images[view])
                return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), url=dict(),folios=folios)
            images = formulae['images']
            folios = formulae['folios']
            town = formulae['town']
            codex = formulae['codex']

            #avoid error when the number of view is over the maximum
            if view > len(images)-1:


                flash( _('There are not {} images for this formula. Showing the last page image instead.'.format(view+1)))
                view = len(images)-1
                if "/images/formulae-1" in str(images[view]):
                    link_picture=current_app.IIIFserver +str(images[view])
                else:
                    link_picture=str(images[view])
                return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), codex=codex, folios=folios, url=dict())

            #avoid error when the number of view is under the mainimum
            elif view<0:


                view=0
                flash( _('There are not {} images for this formula. Showing the first page image instead.'.format(view)))
                if "/images/formulae-1" in str(images[view]):
                    link_picture=current_app.IIIFserver +str(images[view])
                else:
                    link_picture=str(images[view])
                return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), codex=codex, folios=folios, url=dict())

            #create the link if it's an image in local server or take the complet link
            if "/images/formulae-1" in str(images[view]):
                link_picture=current_app.IIIFserver +str(images[view])
            else:
                link_picture=str(images[view])

            return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), codex=codex, folios=folios, url=dict())

    else:
        flash( _('This corpus is on copyright, please choose another text'))
        return current_app.config['nemo_app'].render(template='main::index.html', url=dict())


@bp.route("embedded/<objectId>/<view>", methods=["GET"])
def addviewer(objectId, view):

    if current_app.config['nemo_app'].check_project_team() is True or objectId in current_app.config['nemo_app'].open_texts:

        #information need for loris or
        collection = current_app.config['nemo_app'].get_collection(objectId)
        if isinstance(collection, CtsWorkMetadata):
            editions = [t for t in collection.children.values() if isinstance(t, CtsEditionMetadata)]
            if len(editions) == 0:
                raise UnknownCollection('{}'.format(collection.get_label()) + _l(' hat keine Edition.'))
            objectId = str(editions[0].id)
        formulae = current_app.picture_file[objectId]
        passage_data = get_passage(objectId, '1')


        #this viewer work when the library or archiv give an IIIF API for the external usage of theirs books
        if "manifest" in formulae:
            if "codex" in formulae:
                codex=formulae["codex"]
                manifest = url_for('viewer.static', filename=formulae["manifest"])
                return current_app.config['nemo_app'].render(template='viewer::multiviewermirador.html', manifest=manifest
                                                             ,objectId=objectId, codex=codex, passage_data=passage_data, url=dict())
            else:
                manifest = url_for('viewer.static', filename=formulae["manifest"])
                with open((current_app.IIIFmapping+"/"+formulae["manifest"]), "r") as f:
                    title = load(f)
                codex=title["label"]
                return current_app.config['nemo_app'].render(template='viewer::multiviewermirador.html', manifest=manifest
                                                             ,objectId=objectId, codex=codex, passage_data=passage_data, url=dict())
        else:
            try:
                view = int(view)
            except:
                #exception when in the url view contains another character than number
                view=0
                images = formulae["images"]
                folios = formulae["folios"]
                town = formulae['town']
                codex = formulae['codex']
                current_folios = folios[view]
                flash( _('There is not an images for this formula. Showing the first page.'))
                link_picture=current_app.IIIFserver +str(images[view])
                return current_app.config['nemo_app'].render(template='viewer::multiviewer.html', picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), passage_data=passage_data,
                                                         url=dict(), town=town, codex=codex, current_folios=current_folios,folios=folios)
            images = formulae['images']
            folios = formulae['folios']
            town = formulae['town']
            codex = formulae['codex']

            #avoid error when the number of view is over the maximum
            if view > len(images)-1:

                flash( _('There are not {} images for this formula. Showing the last page image instead.'.format(view)))
                view = len(images)-1
                if "/images/formulae-1" in str(images[view]):
                    link_picture=current_app.IIIFserver +str(images[view])
                else:
                    link_picture=str(images[view])
                return current_app.config['nemo_app'].render(template='viewer::multiviewer.html', picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), passage_data=passage_data,
                                                         url=dict(), town=town, codex=codex, folios=folios)

            #avoid error when the number of view is under the mainimum
            elif view<0:
                view=0
                flash( _('There are not {} images for this formula. Showing the first page image instead.'.format(view)))
                if "/images/formulae-1" in str(images[view]):
                    link_picture=current_app.IIIFserver +str(images[view])
                else:
                    link_picture=str(images[view])
                return current_app.config['nemo_app'].render(template='viewer::multiviewer.html', picture=link_picture,
                                                             objectId=objectId, current_view=view, total_views=len(images),
                                                             passage_data=passage_data,url=dict(), town=town,
                                                             codex=codex, folios=folios)

            current_folios = folios[view]

            #create the link if it's an image in local server or take the complet link
            if "/images/formulae-1" in str(images[view]):
                link_picture=current_app.IIIFserver +str(images[view])
            else:
                link_picture=str(images[view])

            return current_app.config['nemo_app'].render(template='viewer::multiviewer.html', picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), passage_data=passage_data,
                                                         url=dict(), town=town, codex=codex, current_folios=current_folios, folios=folios)
    else:
        flash( _('This corpus is on copyright, please choose another text'))
        return current_app.config['nemo_app'].render(template='main::index.html', url=dict())

@bp.route("abz/<objectId>/<view>", methods=["GET"])
def test_3viewer(objectId, view):
    passage_data = get_passage(objectId, '1')
    passage_data2 = get_passage(objectId, '1')
    formulae = current_app.picture_file[objectId]
    print(formulae)
    manifest = url_for('viewer.static', filename=formulae["manifest"])
    with open((current_app.IIIFmapping+"/"+formulae["manifest"]), "r") as f:
        title = load(f)
    codex=title["label"]
    return current_app.config['nemo_app'].render(template='viewer::multiviewer3.html', manifest=manifest
                                                             ,objectId=objectId, codex=codex,
                                                            passage_data2=passage_data2, passage_data=passage_data, url=dict())
