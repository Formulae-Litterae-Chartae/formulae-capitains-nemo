from flask import request
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from flask_babel import _
from wtforms import StringField, BooleanField, SelectMultipleField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, ValidationError
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
            if field.data < min or max != -1 and field.data > max:
                raise ValidationError(message)

    return _length


class SearchForm(FlaskForm):
    q = StringField(_l('Search'), validators=[DataRequired()])
    lemma_search = BooleanField(_l('Lemma'))
    fuzzy_search = BooleanField(_l('Fuzzy'))
    phrase_search = BooleanField(_l('Phrase'))

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'csrf_enabled' not in kwargs:
            kwargs['csrf_enabled'] = False
        super(SearchForm, self).__init__(*args, **kwargs)


class AdvancedSearchForm(SearchForm):
    q = StringField(_l('Search'))  # query string is not DataRequired here since someone might want to search on other criteria
    corpus = SelectMultipleField(_l('Search Specific Corpora'))
    year = IntegerField(_l('Year'), validators=[validate_optional_number_range(min=500, max=1000,
                                                                               message=_('The year must be between 500 and 1000'))],
                        default=0)
    month = SelectField(_l('Month'), choices=[('none', '...'), ('01', _l('Jan')), ('02', _l('Feb')), ('03', _l('Mar')),
                                              ('04', _l('Apr')), ('05', _l('May')), ('06', _l('Jun')),
                                              ('07', _l('Jul')), ('08', _l('Aug')), ('09', _l('Sep')),
                                              ('10', _l('Oct')), ('11', _l('Nov')), ('12', _l('Dec'))], default='none')
    day = IntegerField(_l('Day'), validators=[validate_optional_number_range(min=1, max=31,
                                                                             message=_('Day must be between 1 and 31'))],
                       default=0)
    year_start = IntegerField(_l('Year'), validators=[validate_optional_number_range(min=500, max=1000,
                                                                               message=_('The year must be between 500 and 1000'))],
                        default=0)
    month_start = SelectField(_l('Month'), choices=[('none', '...'), ('01', _l('Jan')), ('02', _l('Feb')), ('03', _l('Mar')),
                                              ('04', _l('Apr')), ('05', _l('May')), ('06', _l('Jun')),
                                              ('07', _l('Jul')), ('08', _l('Aug')), ('09', _l('Sep')),
                                              ('10', _l('Oct')), ('11', _l('Nov')), ('12', _l('Dec'))], default='none')
    day_start = IntegerField(_l('Day'), validators=[validate_optional_number_range(min=1, max=31,
                                                                             message=_('Day must be between 1 and 31'))],
                       default=0)
    year_end = IntegerField(_l('Year'), validators=[validate_optional_number_range(min=500, max=1000,
                                                                               message=_('The year must be between 500 and 1000'))],
                        default=0)
    month_end = SelectField(_l('Month'), choices=[('none', '...'), ('01', _l('Jan')), ('02', _l('Feb')), ('03', _l('Mar')),
                                              ('04', _l('Apr')), ('05', _l('May')), ('06', _l('Jun')),
                                              ('07', _l('Jul')), ('08', _l('Aug')), ('09', _l('Sep')),
                                              ('10', _l('Oct')), ('11', _l('Nov')), ('12', _l('Dec'))], default='none')
    day_end = IntegerField(_l('Day'), validators=[validate_optional_number_range(min=1, max=31,
                                                                             message=_('Day must be between 1 and 31'))],
                       default=0)
    """century = SelectMultipleField(_l('Century'), choices=[('300-399', _l('4th')), ('400-499', _l('5th')),
                                                          ('500-599', _l('6th')), ('600-699', _l('7th')),
                                                          ('700-799', _l('8th')), ('800-899', _l('9th')),
                                                          ('900-999', _l('10th')), ('1000-1099', _l('11th'))])
    century_part = SelectMultipleField(_l('Century Part'), choices=[('0-49', _l('First Half (00-49)')),
                                                                    ('50-99', _l('Last Half (50-99)')),
                                                                    ('0-24', _l('First Quarter (00-24)')),
                                                                    ('25-49', _l('Second Quarter (25-49)')),
                                                                    ('50-74', _l('Third Quarter (50-74)')),
                                                                    ('75-99', _l('Fourth Quarter (75-99)'))])"""
    formulae = BooleanField('Formulae')
    chartae = BooleanField('Chartae')
    litterae = BooleanField('Litterae')
    submit = SubmitField(_l('Search'))
