from flask import flash, url_for, request, redirect, current_app
from formulae.viewer import bp
from flask_babel import _
from json import load
from MyCapytain.resources.prototypes.cts.inventory import CtsWorkMetadata, CtsEditionMetadata
from MyCapytain.errors import UnknownCollection
from flask_babel import lazy_gettext as _l

'''
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
            manifest = url_for('viewer.static', filename=formulae["manifest"])
            if "codex" in formulae:
                codex=formulae["codex"]
                return current_app.config['nemo_app'].render(template='viewer::miradorviewer.html', codex=codex, objectId=objectId,
                                                         manifest=manifest, url=dict())
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
                flash(_('Es gibt kein Bild ') + view + _(' für diese Formel. Das erste Bild wird gezeigt.'))
                view = 0
                if "/images/formulae-1" in str(images[view]):
                    link_picture=current_app.IIIFserver + str(images[view])
                else:
                    link_picture=str(images[view])
                return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), url=dict(),folios=folios)
            images = formulae['images']
            folios = formulae['folios']
            codex = formulae['codex']
            #avoid error when the number of view is over the maximum
            if view > len(images)-1:
                flash(_('Es gibt nur ') + str(len(images)) + _(' Bilder für diese Formel. Das letzte Bild wird hier gezeigt.'))
                view = len(images)-1
                if "/images/formulae-1" in str(images[view]):
                    link_picture=current_app.IIIFserver +str(images[view])
                else:
                    link_picture=str(images[view])
                return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), codex=codex, folios=folios, url=dict())
            #avoid error when the number of view is under the mainimum
            elif view < 0:
                view = 0
                flash(_('Die Zählung der Bilder fängt immer mit 0. Das erste Bild wird hier gezeigt.'))
                if "/images/formulae-1" in str(images[view]):
                    link_picture = current_app.IIIFserver +str(images[view])
                else:
                    link_picture = str(images[view])
                return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), codex=codex, folios=folios, url=dict())

            #create the link if it's an image in local server or take the complet link
            if "/images/formulae-1" in str(images[view]):
                link_picture = current_app.IIIFserver +str(images[view])
            else:
                link_picture = str(images[view])

            return current_app.config['nemo_app'].render(template="viewer::newtabviewer.html", picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), codex=codex, folios=folios, url=dict()

    else:
        flash(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
        return current_app.config['nemo_app'].render(template='main::index.html', url=dict())
'''



@bp.route("/<objectId>", methods=["GET"])
def addviewer(objectId):
    collection = current_app.config['nemo_app'].get_collection(objectId)
    if isinstance(collection, CtsWorkMetadata):
        editions = [t for t in collection.children.values() if isinstance(t, CtsEditionMetadata)]
        if len(editions) == 0:
            raise UnknownCollection('{}'.format(collection.get_label()) + _l(' hat keine Edition.'))
        objectId = str(editions[0].id)
    if current_app.config['nemo_app'].check_project_team() is True or objectId in current_app.config['nemo_app'].open_texts:
        template = {'manifest': 'viewer::miradorviewer.html'}
        formulae = current_app.picture_file[objectId]
        passage_data = ''
        if request.args.get('embedded', False):
            template = {'manifest': "viewer::multiviewermirador.html"}
            passage_data = current_app.config['nemo_app'].r_passage(objectId, '1')
        #this viewer work when the library or archiv give an IIIF API for the external usage of theirs books
        manifest = url_for('viewer.static', filename=formulae["manifest"])
        with open((current_app.IIIFmapping+"/"+formulae["manifest"]), "r") as f:
            title = load(f)
        codex = title["label"]
        return current_app.config['nemo_app'].render(template=template['manifest'], manifest=manifest
                                                     ,objectId=objectId, codex=codex, text=passage_data, url=dict())
    else:
        flash(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
        return current_app.config['nemo_app'].render(template='main::index.html', url=dict())
'''
        else:
            try:
                view = int(view)
            except:
                #exception when in the url view contains another character than number
                flash(_('Es gibt kein Bild ') + view + _(' für diese Formel. Das erste Bild wird gezeigt.'))
                images = formulae["images"]
                folios = formulae["folios"]
                codex = formulae['codex']
                view = 0
                current_folios = folios[view]
                link_picture = current_app.IIIFserver + str(images[view])
                return current_app.config['nemo_app'].render(template=template['local'], picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), text=passage_data,
                                                         url=dict(), codex=codex, current_folios=current_folios,folios=folios)
            images = formulae['images']
            folios = formulae['folios']
            town = formulae['town']
            codex = formulae['codex']

            #avoid error when the number of view is over the maximum
            if view > len(images) - 1:

                flash(_('Es gibt nur ') + str(len(images)) + _(' Bilder für diese Formel. Das letzte Bild wird hier gezeigt.'))
                view = len(images) - 1
                if "/images/formulae-1" in str(images[view]):
                    link_picture = current_app.IIIFserver + str(images[view])
                else:
                    link_picture = str(images[view])
                return current_app.config['nemo_app'].render(template=template['local'], picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), text=passage_data,
                                                         url=dict(), town=town, codex=codex, folios=folios)

            #avoid error when the number of view is under the mainimum
            elif view < 0:
                view=0
                flash(_('Die Zählung der Bilder fängt immer mit 0. Das erste Bild wird hier gezeigt.'))
                if "/images/formulae-1" in str(images[view]):
                    link_picture = current_app.IIIFserver + str(images[view])
                else:
                    link_picture = str(images[view])
                return current_app.config['nemo_app'].render(template=template['local'], picture=link_picture,
                                                             objectId=objectId, current_view=view, total_views=len(images),
                                                             text=passage_data,url=dict(), town=town,
                                                             codex=codex, folios=folios)

            current_folios = folios[view]
            #create the link if it's an image in local server or take the complet link
            if "/images/formulae-1" in str(images[view]):
                link_picture=current_app.IIIFserver +str(images[view])
            else:
                link_picture=str(images[view])
            return current_app.config['nemo_app'].render(template=template['local'], picture=link_picture, objectId=objectId,
                                                         current_view=view, total_views=len(images), text=passage_data,
                                                         url=dict(), town=town, codex=codex, current_folios=current_folios, folios=folios)
    else:

        flash(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
        return current_app.config['nemo_app'].render(template='main::index.html', url=dict())
'''

@bp.route("abz/<objectId>/<view>", methods=["GET"])
def test_3viewer(objectId, view):
    passage_data = current_app.config['nemo_app'].r_passage(objectId, '1')
    passage_data2 = current_app.config['nemo_app'].r_passage(objectId, '1')
    formulae = current_app.picture_file[objectId]
    print(formulae)
    manifest = url_for('viewer.static', filename=formulae["manifest"])
    with open((current_app.IIIFmapping+"/"+formulae["manifest"]), "r") as f:
        title = load(f)
    codex=title["label"]
    return current_app.config['nemo_app'].render(template='viewer::multiviewer3.html', manifest=manifest
                                                             ,objectId=objectId, codex=codex,
                                                      passage_data2=passage_data2, text=passage_data, url=dict())
'''
If you want to use that for the futur
@bp.route("/lexicon/<objectId>")
def r_lexicon(objectId, lang=None):
    """ Retrieve the eLexicon entry for a word
    :param objectId: Collection identifiers separated by '+'
    :type objectId: str
    :param lang: Lang in which to express main data
    :type lang: str
    :return: Template, collections metadata and Markup object representing the text
    :rtype: {str: Any}
    """
    m = re.search('/viewer/([^/]+)', request.referrer)
    subreference = "1"
    d = get_passage(objectId, subreference,lang=lang)
    d['template'] = 'main::lexicon_modal.html'
    d['prev_texts'] = m.group(1)
    d['prev_reffs'] = "all"
    return current_app.config['nemo_app'].render(**d, url=dict())
'''
