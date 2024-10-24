from flask import request
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from flask_babel import _
from wtforms import StringField, BooleanField, SelectMultipleField, SelectField, SubmitField, HiddenField, RadioField
from wtforms.validators import ValidationError, DataRequired
from wtforms.fields import IntegerField
from wtforms.widgets import CheckboxInput
from collections import OrderedDict
from random import randint

FORM_PARTS = OrderedDict({
    "Invocatio": _l("Invocatio"),
    "Inscriptio": _l("Inscriptio"),
    "Intitulatio": _l("Intitulatio"),
    "Arenga": _l("Arenga"),
    "Publicatio": _l("Publicatio"),
    "Narratio": _l("Narratio"),
    "Dispositio": _l("Dispositio"),
    "Pertinenzformel": _l("Pertinenzformel"),
    "Poenformel": _l("Poenformel"),
    "Corroboratio": _l("Corroboratio"),
    "Stipulationsformel": _l("Stipulationsformel"),
    "Eschatokoll": _l("Eschatokoll")
})


def validate_optional_number_range(minimum: int = -1, maximum: int = -1, message: str = None):
    """ Allows the validation of integer fields with a required number range but that are also optional
        I could not get WTForms to invalidate an integer field where the value was not within the range if it had the
        Optional() validator. I think this must have seen this as an empty field and thus erased all previous validation
        results since it correctly invalidates invalid data when the Optional() validator is not included.
    """

    def _length(form, field):
        if field.data:
            if int(field.data) < minimum or maximum != -1 and int(field.data) > maximum:
                raise ValidationError(message or "Field value must between between %i and %i." % (minimum, maximum))

    return _length


class SearchForm(FlaskForm):
    q_1 = StringField(_l('Suche'), validators=[DataRequired()])
    corpus = SelectMultipleField(_l('Korpora'), choices=[('formulae', _l('Formeln')),
                                                         ('chartae', _l('Urkunden')),
                                                         ('elexicon', _l('Lexikon'))],
                                 option_widget=CheckboxInput()
                                 )
    lemma_search = BooleanField(_l('Lemma'))
    simple_search_id = HiddenField(validators=[validate_optional_number_range(1, 10000)], default=randint(1, 10000))

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'meta' not in kwargs:
            kwargs['meta'] = {'csrf': False}
        super(SearchForm, self).__init__(*args, **kwargs)


class AdvancedSearchForm(SearchForm):
    q_1 = StringField(_l('Suche'), default='')  # query string is not DataRequired here since someone might want to search on other criteria
    regex_search_1 = BooleanField(_l('RegEx'))
    fuzziness_1 = SelectField(_l("Unschärfegrad"),
                            choices=[("0", '0'), ("1", "1"), ("2", '2'), ('AUTO', _('AUTO'))],
                            default="0")
    slop_1 = IntegerField(_l("Suchradius"), default=0)
    in_order_1 = BooleanField(_l('Wortreihenfolge?'))
    search_field_1 = SelectField(_l("Suchfeld"), choices=[("text", _('Text')),
                                                        ("lemmas", _('Lemmata')),
                                                        ("regest", _('Regest'))],
                               default='text')

    #formulaic_parts_1 = SelectMultipleField(_l('Urkundenbestandteile durchsuchen'), choices=[(k, v) for k, v in FORM_PARTS.items()])
    proper_name_1 = SelectMultipleField(_l('Eigennamensuche'),  choices=[('personenname', _l('Personenname')),
                                                                       ('ortsname', _l('Ortsname'))])

    exclude_q_1 = StringField(_l('Ausschlusskriterium'))
    q_2 = StringField(_l('Suche'), default='')  # query string is not DataRequired here since someone might want to search on other criteria
    regex_search_2 = BooleanField(_l('RegEx'))
    fuzziness_2 = SelectField(_l("Unschärfegrad"),
                            choices=[("0", '0'), ("1", "1"), ("2", '2'), ('AUTO', _('AUTO'))],
                            default="0")
    slop_2 = IntegerField(_l("Suchradius"), default=0)
    in_order_2 = BooleanField(_l('Wortreihenfolge?'))
    search_field_2 = SelectField(_l("Suchfeld"), choices=[("text", _('Text')),
                                                        ("lemmas", _('Lemmata')),
                                                        ("regest", _('Regest'))],
                               default='text')

    # formulaic_parts_2 = SelectMultipleField(_l('Urkundenbestandteile durchsuchen'), choices=[(k, v) for k, v in FORM_PARTS.items()])
    proper_name_2 = SelectMultipleField(_l('Eigennamensuche'),  choices=[('personenname', _l('Personenname')),
                                                                       ('ortsname', _l('Ortsname'))])

    exclude_q_2 = StringField(_l('Ausschlusskriterium'))
    q_3 = StringField(_l('Suche'), default='')  # query string is not DataRequired here since someone might want to search on other criteria
    regex_search_3 = BooleanField(_l('RegEx'))
    fuzziness_3 = SelectField(_l("Unschärfegrad"),
                            choices=[("0", '0'), ("1", "1"), ("2", '2'), ('AUTO', _('AUTO'))],
                            default="0")
    slop_3 = IntegerField(_l("Suchradius"), default=0)
    in_order_3 = BooleanField(_l('Wortreihenfolge?'))
    search_field_3 = SelectField(_l("Suchfeld"), choices=[("text", _('Text')),
                                                        ("lemmas", _('Lemmata')),
                                                        ("regest", _('Regest'))],
                               default='text')

    # formulaic_parts_3 = SelectMultipleField(_l('Urkundenbestandteile durchsuchen'), choices=[(k, v) for k, v in FORM_PARTS.items()])
    proper_name_3 = SelectMultipleField(_l('Eigennamensuche'),  choices=[('personenname', _l('Personenname')),
                                                                       ('ortsname', _l('Ortsname'))])

    exclude_q_3 = StringField(_l('Ausschlusskriterium'))
    q_4 = StringField(_l('Suche'), default='')  # query string is not DataRequired here since someone might want to search on other criteria
    regex_search_4 = BooleanField(_l('RegEx'))
    fuzziness_4 = SelectField(_l("Unschärfegrad"),
                            choices=[("0", '0'), ("1", "1"), ("2", '2'), ('AUTO', _('AUTO'))],
                            default="0")
    slop_4 = IntegerField(_l("Suchradius"), default=0)
    in_order_4 = BooleanField(_l('Wortreihenfolge?'))
    search_field_4 = SelectField(_l("Suchfeld"), choices=[("text", _('Text')),
                                                        ("lemmas", _('Lemmata')),
                                                        ("regest", _('Regest'))],
                               default='text')

    # formulaic_parts_4 = SelectMultipleField(_l('Urkundenbestandteile durchsuchen'), choices=[(k, v) for k, v in FORM_PARTS.items()])
    proper_name_4 = SelectMultipleField(_l('Eigennamensuche'),  choices=[('personenname', _l('Personenname')),
                                                                       ('ortsname', _l('Ortsname'))])

    exclude_q_4 = StringField(_l('Ausschlusskriterium'))
    corpus = SelectMultipleField(_l('Korpora'), choices=[('all', _l('Alle')), ('chartae', _l('Urkunden')),
                                                                         ('formulae', _l('Formeln')),
                                                         ('elexicon', _l('Lexikon'))])
    year = StringField(_l('Jahr'), validators=[validate_optional_number_range(minimum=500, maximum=1000,
                                                                              message=_l('Die Jahreszahl muss zwischen 500 und 1000 liegen'))],
                       default="")
    month = SelectField(_l('Monat'), choices=[(0, '...'), (1, _l('Jan')), (2, _l('Feb')), (3, _l('Mär')),
                                              (4, _l('Apr')), (5, _l('Mai')), (6, _l('Jun')),
                                              (7, _l('Jul')), (8, _l('Aug')), (9, _l('Sep')),
                                              (10, _l('Okt')), (11, _l('Nov')), (12, _l('Dez'))],
                        default=0, coerce=int)
    day = StringField(_l('Tag'), validators=[validate_optional_number_range(minimum=1, maximum=31,
                                                                            message=_l('Das Datum muss zwischen 1 und 31 liegen'))],
                      default="")
    year_start = StringField(_l('Jahr'), validators=[validate_optional_number_range(minimum=500, maximum=1000,
                                                                                    message=_l('Die Jahreszahl muss zwischen 500 und 1000 liegen'))],
                             default="")
    month_start = SelectField(_l('Monat'), choices=[(0, '...'), (1, _l('Jan')), (2, _l('Feb')), (3, _l('Mär')),
                                              (4, _l('Apr')), (5, _l('Mai')), (6, _l('Jun')),
                                              (7, _l('Jul')), (8, _l('Aug')), (9, _l('Sep')),
                                              (10, _l('Okt')), (11, _l('Nov')), (12, _l('Dez'))],
                              default=0, coerce=int)
    day_start = StringField(_l('Tag'),
                            validators=[validate_optional_number_range(minimum=1, maximum=31,
                                                                       message=_l('Das Datum muss zwischen 1 und 31 liegen'))],
                            default="")
    year_end = StringField(_l('Jahr'),
                           validators=[validate_optional_number_range(minimum=500, maximum=1000,
                                                                      message=_l('Die Jahreszahl muss zwischen 500 und 1000 liegen'))],
                           default="")
    month_end = SelectField(_l('Monat'), choices=[(0, '...'), (1, _l('Jan')), (2, _l('Feb')), (3, _l('Mär')),
                                              (4, _l('Apr')), (5, _l('Mai')), (6, _l('Jun')),
                                              (7, _l('Jul')), (8, _l('Aug')), (9, _l('Sep')),
                                              (10, _l('Okt')), (11, _l('Nov')), (12, _l('Dez'))],
                            default=0, coerce=int)
    day_end = StringField(_l('Tag'), validators=[validate_optional_number_range(minimum=1, maximum=31,
                                                                                message=_l('Das Datum muss zwischen 1 und 31 liegen'))],
                          default="")
    date_plus_minus = IntegerField(_l('Datum Plus-Minus'),
                                   validators=[validate_optional_number_range(minimum=0, maximum=100,
                                                                              message=_l('Plus-Minus muss zwischen 0 und 100 Jahren liegen'))],
                                   default=0)
    exclusive_date_range = BooleanField(_l('Exklusiv'))
    composition_place = StringField(_l('Ausstellungsort'))
    special_days = SelectMultipleField(_l('Nach bestimmten Tagen suchen'), choices=[('', ''),
                                                                                    ('Easter', _l('Ostern')),
                                                                                    ('Lent', _l('Fastenzeit')),
                                                                                    ('Pentecost', _l('Pfingsten')),
                                                                                    ('Sunday', _l('So')),
                                                                                    ('Monday', _l('Mo')),
                                                                                    ('Tuesday', _l('Di')),
                                                                                    ('Wednesday', _l('Mi')),
                                                                                    ('Thursday', _l('Do')),
                                                                                    ('Friday', _l('Fr')),
                                                                                    ('Saturday', _l('Sa'))])
    forgeries = RadioField(_l("Fälschungen"),
                           choices=[("", ""),
                                    ("include", _l('alle Dokumente')),
                                    ("exclude", _l('ohne Fälschungen')),
                                    ('only', _l('nur Fälschungen'))],
                           default="include")
    bool_operator = SelectField(_("Boolesche Operator"),
                                choices=[('must', _('UND')), ('should', _('ODER')), ('must_not', 'NICHT')],
                                default='must')
    search_id = HiddenField(validators=[validate_optional_number_range(1, 10000)], default=randint(1, 10000))
    submit = SubmitField(_l('Suche Durchführen'), id="advancedSearchSubmit")
