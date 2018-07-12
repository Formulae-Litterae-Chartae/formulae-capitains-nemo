from formulae.app import resolver, nautilus_api
from capitains_nautilus.manager import FlaskNautilusManager

manager = FlaskNautilusManager(resolver, nautilus_api)

if __name__ == "__main__":
    manager()
