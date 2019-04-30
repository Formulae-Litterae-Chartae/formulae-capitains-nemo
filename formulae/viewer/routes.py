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

    if current_app.config['nemo_app'].check_project_team() is True or objectId in current_app.config['nemo_app'].open_texts:

        images=current_app.picture_file[objectId]
        for picture in images:

            if "manifest" in picture:

                manifest = url_for('viewer.static', filename=picture["manifest"])

                return current_app.config['nemo_app'].render(template='viewer::miradorviewer.html', objectId=objectId,
                                                             manifest=manifest, url=dict())

            else:
                try:
                    view = int(view)
                except:
                    images = picture['images']
                    view=0
                    flash( _('There is not an images for this formula. Showing the first page.'))
                    link_picture=current_app.IIIFserver +str(images[view])
                    return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                             current_view=view, total_views=len(images), url=dict())
                images = picture['images']

                if view > len(images)-1:


                    flash( _('There are not {} images for this formula. Showing the last page image instead.'.format(view)))
                    view = len(images)-1
                    link_picture=current_app.IIIFserver+ str(images[view])
                    return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                             current_view=view, total_views=len(images) ,url=dict())
                elif view<0:


                    view=0
                    flash( _('There are not {} images for this formula. Showing the first page image instead.'.format(view)))
                    link_picture=current_app.IIIFserver +str(images[view])
                    return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                             current_view=view, total_views=len(images) ,url=dict())



                link_picture=current_app.IIIFserver +str(images[view])

                return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                             current_view=view, total_views=len(images) ,url=dict())

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
                raise UnknownCollection('{}'.format(collection.get_label()) + _l(' wurde nicht gefunden.'))
            objectId = str(editions[0].id)
        formulae = current_app.picture_file[objectId]
        passage_data = get_passage(objectId, '1')


        for picture in formulae:

            if "manifest" in picture:

                manifest = url_for('viewer.static', filename=picture["manifest"])
                return current_app.config['nemo_app'].render(template='viewer::multiviewermirador.html', manifest=manifest
                                                             ,objectId=objectId ,passage_data=passage_data ,url=dict())

            else:
                try:
                    view = int(view)
                except:
                    view=0
                    images = picture['images']
                    folios = picture['folios']
                    town = picture['town']
                    codex = picture['codex']
                    current_folios = folios[view]
                    flash( _('There is not an images for this formula. Showing the first page.'))
                    link_picture=current_app.IIIFserver +str(images[view])
                    return current_app.config['nemo_app'].render(template='viewer::multiviewer.html', picture=link_picture, objectId=objectId,
                                                             current_view=view, total_views=len(images), passage_data=passage_data,
                                                             url=dict(), town=town, codex=codex, current_folios=current_folios)
                images = picture['images']
                folios = picture['folios']
                town = picture['town']
                codex = picture['codex']




                if view > len(images)-1:

                    flash( _('There are not {} images for this formula. Showing the last page image instead.'.format(view)))
                    view = len(images)-1
                    link_picture=current_app.IIIFserver+ str(images[view])
                    return current_app.config['nemo_app'].render(template='viewer::multiviewer.html', picture=link_picture, objectId=objectId,
                                                             current_view=view, total_views=len(images), passage_data=passage_data,
                                                             url=dict(), town=town, codex=codex)
                elif view<0:
                    view=0
                    flash( _('There are not {} images for this formula. Showing the first page image instead.'.format(view)))
                    link_picture=current_app.IIIFserver +str(images[view])
                    return current_app.config['nemo_app'].render(template='viewer::multiviewer.html', picture=link_picture, objectId=objectId,
                                                             current_view=view, total_views=len(images), passage_data=passage_data,
                                                             url=dict(), town=town, codex=codex)

                current_folios = folios[view]
                link_picture = current_app.IIIFserver + str(images[view])


                return current_app.config['nemo_app'].render(template='viewer::multiviewer.html', picture=link_picture, objectId=objectId,
                                                             current_view=view, total_views=len(images), passage_data=passage_data,
                                                             url=dict(), town=town, codex=codex, current_folios=current_folios)
    else:
        flash( _('This corpus is on copyright, please choose another text'))
        return current_app.config['nemo_app'].render(template='main::index.html', url=dict())

