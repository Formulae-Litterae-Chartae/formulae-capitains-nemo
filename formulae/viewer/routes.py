from flask import flash, url_for, current_app
from formulae.viewer import bp
from flask_babel import _
from MyCapytain.resources.collections.capitains import XmlCapitainsReadableMetadata, XmlCapitainsCollectionMetadata
from MyCapytain.errors import UnknownCollection
from flask_babel import lazy_gettext as _l
import re


@bp.route("/<objectId>", methods=["GET"])
def fullscreenviewer(objectId):
    if "manifest" in objectId:
        objectId = re.sub(r'^manifest:', '', objectId)
    metadata = current_app.config['nemo_app'].get_collection(objectId)
    if isinstance(metadata, XmlCapitainsCollectionMetadata):
        transcriptions = [t for t in metadata.descendants.values() if isinstance(t, XmlCapitainsReadableMetadata) and 'transcription' in t.subtype]
        if len(transcriptions) == 0:
            raise UnknownCollection(str(metadata.get_label()) + _l(' hat keine Edition.'),
                                    objectId)
        objectId = str(transcriptions[0].id)
    if current_app.config['nemo_app'].check_project_team() is True or objectId in current_app.config['nemo_app'].open_texts:
        template = {'manifest': 'viewer::miradorviewer.html'}
        formulae = current_app.picture_file['manifest:' + objectId]
        #this viewer work when the library or archiv give an IIIF API for the external usage of theirs books
        manifest = url_for('viewer.static', filename=formulae["manifest"])
        return current_app.config['nemo_app'].render(template=template['manifest'], manifest=manifest,
                                                     objectId=objectId, url=dict())
    else:
        flash(_('Diese Formelsammlung ist noch nicht frei zugänglich.'))
        return current_app.config['nemo_app'].render(template='main::index.html', url=dict())

