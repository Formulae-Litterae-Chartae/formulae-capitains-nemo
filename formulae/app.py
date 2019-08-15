from werkzeug.contrib.cache import FileSystemCache
from capitains_nautilus.cts.resolver import NautilusCTSResolver
from capitains_nautilus.flask_ext import FlaskNautilus
from . import create_app
from .nemo import NemoFormulae
from .dispatcher_builder import organizer

flask_app = create_app()
resolver = NautilusCTSResolver(flask_app.config['CORPUS_FOLDERS'],
                               dispatcher=organizer,
                               # cache=FileSystemCache(flask_app.config['CACHE_DIRECTORY'])
                               )
# nautilus_api = FlaskNautilus(prefix="/api", resolver=resolver, app=flask_app)

nemo = NemoFormulae(
    name="InstanceNemo",
    app=flask_app,
    resolver=resolver,
    base_url="",
    css=["assets/css/theme.css"],
    js=["assets/js/empty.js"],
    static_folder="./assets/",
    transform={"default": "components/epidoc.xsl",
               "notes": "components/extract_notes.xsl",
               "elex_notes": "components/extract_elex_notes.xsl"},
    templates={"main": "templates/main",
               "errors": "templates/errors",
               "auth": "templates/auth",
               "search": "templates/search",
               "viewer": "templates/viewer"},
    pdf_folder="pdf_folder/"
)

flask_app.config['nemo_app'] = nemo
