from flask_babel import _


def e_not_found_error(error):
    response = "<h4>{}</h4>".format(_('Die gesuchte URL wurde nicht gefunden'))
    return r_display_error(404, response)


def e_internal_error(error):
    from formulae import db
    response = "<h4>{}</h4><p>{}</p>".format(_('Ein unerwarteter Fehler ist aufgetreten'),
                                             _('Der Administrator wurde benachrichtigt. Entschuldigen Sie die Unannehmlichkeiten!'))
    db.session.rollback()
    return r_display_error(error_code=500, error_message=response)


def e_unknown_collection_error(error):
    if 'sub_reff' in error.args:
        code = "UnknownReference"
    else:
        code = "UnknownCollection"
    response = error.args[0].strip("\"'").split()[0]
    return r_display_error(error_code=code, error_message=response)


def r_display_error(error_code, error_message):
    """ Error display form

    :param error_code: the error type
    :param error_message: the message from the error
    :return:
    """
    from formulae.app import nemo
    index_anchor = '<a href="/">{}</a>'.format(_('Zurück zur Startseite'))
    if error_code in ["UnknownCollection", "UnknownReference"]:
        if error_code == "UnknownReference":
            return nemo.render(**{"template": 'errors::unknown_reference.html', 'message': error_message,
                                  'parent': ':'.join(error_message.split(':')[:-1]), 'url': dict()}), 404
        else:
            return nemo.render(**{"template": 'errors::unknown_collection.html', 'message': error_message,
                                  'parent': '.'.join(error_message.split('.')[:-1]), 'url': dict()}), 404
    if error_code in (500, 404):
        return "{}<p>{}</p>".format(error_message, index_anchor), error_code
