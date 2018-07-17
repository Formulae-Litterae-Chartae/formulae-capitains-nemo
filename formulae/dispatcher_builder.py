from MyCapytain.resources.prototypes.cts.inventory import CtsTextInventoryCollection, CtsTextInventoryMetadata
from MyCapytain.resolvers.utils import CollectionDispatcher

general_collection = CtsTextInventoryCollection()
formulae = CtsTextInventoryMetadata('formulae_collection', parent=general_collection)
formulae.set_label('Formulae', 'lat')
chartae = CtsTextInventoryMetadata('chartae_collection', parent=general_collection)
chartae.set_label('Chartae', 'lat')
elexicon = CtsTextInventoryMetadata('eLexicon_entries', parent=general_collection)
elexicon.set_label('E-Lexikon', 'lat')
organizer = CollectionDispatcher(general_collection, default_inventory_name='chartae_collection')

@organizer.inventory("formulae_collection")
def organize_formulae(collection, path=None, **kwargs):
    if collection.id.startswith('urn:cts:formulae:andecavensis'):
        return True
    return False

@organizer.inventory("eLexicon_entries")
def organize_elexicon(collection, path=None, **kwargs):
    if collection.id.startswith('urn:cts:formulae:elexicon'):
        return True
    return False
