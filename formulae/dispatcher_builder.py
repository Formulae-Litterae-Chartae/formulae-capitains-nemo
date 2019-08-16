from MyCapytain.resources.prototypes.cts.inventory import CtsTextInventoryCollection, CtsTextInventoryMetadata
from MyCapytain.resolvers.utils import CollectionDispatcher
import re

general_collection = CtsTextInventoryCollection()
formulae = CtsTextInventoryMetadata('formulae_collection', parent=general_collection)
formulae.set_label('Formulae', 'ger')
formulae.set_label('Formulae', 'eng')
formulae.set_label('Formulae', 'fre')
chartae = CtsTextInventoryMetadata('other_collection', parent=general_collection)
chartae.set_label('Andere Texte', 'ger')
chartae.set_label('Other Texts', 'eng')
chartae.set_label('Autres Textes', 'fre')
elexicon = CtsTextInventoryMetadata('lexicon_entries', parent=general_collection)
elexicon.set_label('Lexikon', 'ger')
elexicon.set_label('Lexicon', 'eng')
elexicon.set_label('Lexique', 'fre')
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
