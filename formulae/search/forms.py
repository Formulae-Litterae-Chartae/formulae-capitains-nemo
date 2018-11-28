from flask import request
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from flask_babel import _
from wtforms import StringField, BooleanField, SelectMultipleField, SelectField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from wtforms.fields.html5 import IntegerRangeField
from wtforms.widgets import CheckboxInput


def validate_optional_number_range(min=-1, max=-1, message=None):
    """ Allows the validation of integer fields with a required number range but that are also optional
        I could not get WTForms to invalidate an integer field where the value was not within the range if it had the
        Optional() validator. I think this must have seen this as an empty field and thus erased all previous validation
        results since it correctly invalidates invalid data when the Optional() validator is not included.
    """
    if not message:
        message = "Field value must between between %i and %i." % (min, max)

    def _length(form, field):
        if field.data:
            if int(field.data) < min or max != -1 and int(field.data) > max:
                raise ValidationError(message)

    return _length


def validate_multiword_not_wildcard(form, field):
    """ This validates that a multiword search query does not also contain a wildcard character (? or *)

    :param query: the text of the query
    :return:
    """
    field = str(field.data)
    if ' ' in field and ('*' in field or '?' in field):
        raise ValidationError(_l('Suchanfragen mit mehreren Wörtern dürfen keine "Wildcard"-Zeichen enthalten (d.h. "?" oder "*")'))


class SearchForm(FlaskForm):
    q = StringField(_l('Suche'), validators=[DataRequired()])
    corpus = SelectMultipleField(_l('Corpora'), choices=[('formulae', _l('Formeln')), ('chartae', _l('Urkunden'))],
                                 option_widget=CheckboxInput(),
                                 validators=[DataRequired(
                                     message=_l('Sie müssen mindestens eine Sammlung für die Suche auswählen ("Formeln" und/oder "Urkunden")'))]
                                 )

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'csrf_enabled' not in kwargs:
            kwargs['csrf_enabled'] = False
        super(SearchForm, self).__init__(*args, **kwargs)


class AdvancedSearchForm(SearchForm):
    q = StringField(_l('Suche'))  # query string is not DataRequired here since someone might want to search on other criteria
    lemma_search = BooleanField(_l('Lemma'))
    fuzziness = SelectField(_l("Unschärfegrad"),
                            choices=[("0", '0'), ("1", "1"), ("2", '2'), ('AUTO', _('AUTO'))],
                            default="0")
    slop = IntegerRangeField(_l("Suchradius"),
                             validators=[validate_optional_number_range(min=0, max=100,
                                                                        message=_('Der Suchradius muss zwischen 0 und 100 liegen'))],
                             default=0)
    in_order = BooleanField(_l('Wortreihenfolge beachten?'))
    corpus = SelectMultipleField(_l('Corpora'), choices=[('all', _l('Alle')), ('chartae', _l('Urkunden')),
                                                                         ('formulae', _l('Formeln'))])
    year = StringField(_l('Jahr'), validators=[validate_optional_number_range(min=500, max=1000,
                                                                              message=_('Die Jahreszahl muss zwischen 500 und 1000 liegen'))],
                       default="")
    month = SelectField(_l('Monat'), choices=[(0, '...'), (1, _l('Jan')), (2, _l('Feb')), (3, _l('Mär')),
                                              (4, _l('Apr')), (5, _l('Mai')), (6, _l('Jun')),
                                              (7, _l('Jul')), (8, _l('Aug')), (9, _l('Sep')),
                                              (10, _l('Okt')), (11, _l('Nov')), (12, _l('Dez'))],
                        default=0, coerce=int)
    day = StringField(_l('Tag'), validators=[validate_optional_number_range(min=1, max=31,
                                                                            message=_('Das Datum muss zwischen 1 und 31 liegen'))],
                      default="")
    year_start = StringField(_l('Jahr'), validators=[validate_optional_number_range(min=500, max=1000,
                                                                                    message=_('Die Jahreszahl muss zwischen 500 und 1000 liegen'))],
                             default="")
    month_start = SelectField(_l('Monat'), choices=[(0, '...'), (1, _l('Jan')), (2, _l('Feb')), (3, _l('Mär')),
                                              (4, _l('Apr')), (5, _l('Mai')), (6, _l('Jun')),
                                              (7, _l('Jul')), (8, _l('Aug')), (9, _l('Sep')),
                                              (10, _l('Okt')), (11, _l('Nov')), (12, _l('Dez'))],
                              default=0, coerce=int)
    day_start = StringField(_l('Tag'),
                            validators=[validate_optional_number_range(min=1, max=31,
                                                                       message=_('Das Datum muss zwischen 1 und 31 liegen'))],
                            default="")
    year_end = StringField(_l('Jahr'),
                           validators=[validate_optional_number_range(min=500, max=1000,
                                                                      message=_('Die Jahreszahl muss zwischen 500 und 1000 liegen'))],
                           default="")
    month_end = SelectField(_l('Monat'), choices=[(0, '...'), (1, _l('Jan')), (2, _l('Feb')), (3, _l('Mär')),
                                              (4, _l('Apr')), (5, _l('Mai')), (6, _l('Jun')),
                                              (7, _l('Jul')), (8, _l('Aug')), (9, _l('Sep')),
                                              (10, _l('Okt')), (11, _l('Nov')), (12, _l('Dez'))],
                            default=0, coerce=int)
    day_end = StringField(_l('Tag'), validators=[validate_optional_number_range(min=1, max=31,
                                                                                message=_('Das Datum muss zwischen 1 und 31 liegen'))],
                          default="")
    date_plus_minus = IntegerRangeField(_l('Datum Plus-Minus'),
                                        validators=[validate_optional_number_range(min=0, max=100,
                                                                                  message=_('Plus-Minus muss zwischen 0 und 100 Jahren liegen'))],
                                        default=0)
    exclusive_date_range = BooleanField(_l('Exklusiv'))
    composition_place = StringField(_l('Ausstellungsort'))
    submit = SubmitField(_l('Suche'))
