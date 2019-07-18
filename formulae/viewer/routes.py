from flask import flash, url_for, current_app
from formulae.viewer import bp
from flask_babel import _
from MyCapytain.resources.prototypes.cts.inventory import CtsWorkMetadata, CtsEditionMetadata
from MyCapytain.errors import UnknownCollection
from flask_babel import lazy_gettext as _l
import re


@bp.route("/<objectId>", methods=["GET"])
def fullscreenviewer(objectId):
    if "manifest" in objectId:
        objectId = re.sub(r'^manifest:', '', objectId)
    collection = current_app.config['nemo_app'].get_collection(objectId)
    if isinstance(collection, CtsWorkMetadata):
        editions = [t for t in collection.children.values() if isinstance(t, CtsEditionMetadata)]
        if len(editions) == 0:
            raise UnknownCollection('{}'.format(collection.get_label()) + _l(' hat keine Edition.'))
        objectId = str(editions[0].id)
    if current_app.config['nemo_app'].check_project_team() is True or objectId in current_app.config['nemo_app'].open_texts:
        template = {'manifest': 'viewer::miradorviewer.html'}
        formulae = current_app.picture_file['manifest:' + current_app.config['nemo_app'].resolver.getMetadata(objectId).parent.id]
        #this viewer work when the library or archiv give an IIIF API for the external usage of theirs books
        manifest = url_for('viewer.static', filename=formulae["manifest"])
        return current_app.config['nemo_app'].render(template=template['manifest'], manifest=manifest,
                                                     objectId=objectId, url=dict())
    else:
        flash(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
        return current_app.config['nemo_app'].render(template='main::index.html', url=dict())

