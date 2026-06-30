from flask_babel import _
from flask import current_app
from werkzeug.exceptions import Unauthorized
from flask import request

def e_not_found_error(error):
    response = "<h4>{}</h4>".format(_('Die gesuchte URL wurde nicht gefunden'))
    return r_display_error(404, response,
                           objectId=error.args[1] if len(error.args) == 2 else '')


def e_internal_error(error):
    from formulae import db
    from flask import current_app

    current_app.logger.error(
        "Unhandled internal server error",
        exc_info=(type(error), error, error.__traceback__)
    )

    response = "<h4>{}</h4><p>{}</p>".format(
        _('Ein unerwarteter Fehler ist aufgetreten'),
        _('Der Administrator wurde benachrichtigt. Bitte entschuldigen Sie die Unannehmlichkeiten!')
    )
    db.session.rollback()
    return r_display_error(error_code=500, error_message=response)


def e_unknown_collection_error(error):
    code = "UnknownCollection"
    response = error.args[0].strip("\"'")
    return r_display_error(error_code=code, error_message=response,
                           objectId=error.args[1] if len(error.args) == 2 else '')

def e_not_authorized_error(error: Unauthorized):
    return current_app.config['nemo_app'].render(**{"template": 'errors::401.html'
                                                    ,'url': dict(), 
                                                    'referrer':request.referrer
                                                    }), 401


def r_display_error(error_code, error_message, **kwargs):
    """ Error display form

    :param error_code: the error type
    :param error_message: the message from the error
    :return:
    """
    index_anchor = '<a href="/">{}</a>'.format(_('Zurück zur Startseite'))
    if error_code == "UnknownCollection":
        print('objectId:', kwargs['objectId'])
        return current_app.config['nemo_app'].render(**{"template": 'errors::unknown_collection.html', 'message': error_message,
                                  'parent': kwargs['objectId'], 'url': dict()}), 404
    if error_code in (500, 404):
        return "{}<p>{}</p>".format(error_message, index_anchor), error_code
