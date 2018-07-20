from flask_babel import _


def e_not_found_error(error):
    response = "<h4>{}</h4>".format(_('The URL you were looking for was not found'))
    return r_display_error(404, response)


def e_internal_error(error):
    response = "<h4>{}</h4><p>{}</p>".format(_('An unexpected error has occurred'),
                                             _('The administrator has been notified. Sorry for the inconvenience!'))
    return r_display_error(error_code=500, error_message=response)


def e_unknown_collection_error(error):
    response = error.args[0].strip("\"'").split()[0]
    return r_display_error(error_code="UnknownCollection", error_message=response)


def r_display_error(error_code, error_message):
    """ Error display form

    :param error_code: the error type
    :param error_message: the message from the error
    :return:
    """
    from formulae.app import nemo
    index_anchor = '<a href="/">{}</a>'.format(_('Back to Home'))
    if error_code == "UnknownCollection":
        return nemo.render(**{"template": 'main::unknown_collection.html', 'message': error_message,
                'parent': '.'.join(error_message.split('.')[:-1]), 'url': dict()}), 404
    if error_code in (500, 404):
        return "{}<p>{}</p>".format(error_message, index_anchor), error_code
