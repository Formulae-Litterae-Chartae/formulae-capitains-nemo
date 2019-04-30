from flask_babel import _
from flask import current_app


def e_not_found_error(error):
    response = "<h4>{}</h4>".format(_('Die gesuchte URL wurde nicht gefunden'))
    return r_display_error(404, response)


def e_internal_error(error):
    from formulae import db
    response = "<h4>{}</h4><p>{}</p>".format(_('Ein unerwarteter Fehler ist aufgetreten'),
                                             _('Der Administrator wurde benachrichtigt. Bitte entschuldigen Sie die Unannehmlichkeiten!'))
    db.session.rollback()
    return r_display_error(error_code=500, error_message=response)


def e_unknown_collection_error(error):
    # And unknown subreference is caught by the NemoFormulae.r_passage route
    #if 'sub_reff' in error.args:
    #    code = "UnknownReference"
    #else:
    code = "UnknownCollection"
    response = error.args[0].strip("\"'").split()[0]
    return r_display_error(error_code=code, error_message=response)


def r_display_error(error_code, error_message):
    """ Error display form

    :param error_code: the error type
    :param error_message: the message from the error
    :return:
    """
    index_anchor = '<a href="/">{}</a>'.format(_('Zurück zur Startseite'))
    if error_code == "UnknownCollection":
        # The UnknownReference error is caught be the NemoFormulae.r_passage route.
        #if error_code == "UnknownReference":
        #    return current_app.config['nemo_app'].render(**{"template": 'errors::unknown_reference.html', 'message': error_message,
        #                          'parent': ':'.join(error_message.split(':')[:-1]), 'url': dict()}), 404
        #else:
        return current_app.config['nemo_app'].render(**{"template": 'errors::unknown_collection.html', 'message': error_message,
                                  'parent': '.'.join(error_message.split('.')[:-1]), 'url': dict()}), 404
    if error_code in (500, 404):
        return "{}<p>{}</p>".format(error_message, index_anchor), error_code
