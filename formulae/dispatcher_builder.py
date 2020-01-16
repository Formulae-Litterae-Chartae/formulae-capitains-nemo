from MyCapytain.resources.prototypes.capitains.collection import CapitainsCollectionMetadata
from MyCapytain.resolvers.utils import CollectionDispatcher
import re
from rdflib.namespace import DC

general_collection = CapitainsCollectionMetadata('base_collection')
formulae = CapitainsCollectionMetadata('formulae_collection', parent=general_collection)
formulae.metadata.add(DC.title, 'Formulae', 'ger')
formulae.metadata.add(DC.title, 'Formulae', 'eng')
formulae.metadata.add(DC.title, 'Formulae', 'fre')
chartae = CapitainsCollectionMetadata('other_collection', parent=general_collection)
chartae.metadata.add(DC.title, 'Andere Texte', 'ger')
chartae.metadata.add(DC.title, 'Other Texts', 'eng')
chartae.metadata.add(DC.title, 'Autres Textes', 'fre')
elexicon = CapitainsCollectionMetadata('lexicon_entries', parent=general_collection)
elexicon.metadata.add(DC.title, 'Lexikon', 'ger')
elexicon.metadata.add(DC.title, 'Lexicon', 'eng')
elexicon.metadata.add(DC.title, 'Lexique', 'fre')
organizer = CollectionDispatcher(general_collection, default_inventory_name='other_collection')


@organizer.inventory("formulae_collection")
def organize_formulae(collection, path=None, **kwargs):
    if re.search(r'andecavensis|markulf', collection.id):
        return True
    return False


@organizer.inventory("lexicon_entries")
def organize_elexicon(collection, path=None, **kwargs):
    if collection.id.startswith('urn:cts:formulae:elexicon'):
        return True
    return False
