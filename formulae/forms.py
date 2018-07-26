from flask import request
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import StringField, BooleanField, SelectMultipleField, DecimalField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange


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
    q = StringField(_l('Search'))  # query string is not necessary here since someone might want to search on other criteria
    corpus = SelectMultipleField(_l('Choose a Corpus'))
    year = DecimalField(_l('Year'), places=0, validators=[NumberRange(min=500, max=1000,
                                                          message=_l('The year must be between 500 and 1000'))])
    month = SelectField(_l('Month'), choices=[_l('Jan'), _l('Feb'), _l('Mar'), _l('Apr'), _l('May'), _l('Jun'),
                                              _l('Jul'), _l('Aug'), _l('Sep'), _l('Oct'), _l('Nov'), _l('Dec')])
    day = DecimalField(_l('Day'), places=0, validators=[NumberRange(min=1, max=31,
                                                                    message=_l('Day must be between 1 and 31'))])
    century = SelectMultipleField(_l('Century'), choices=[_l('4th'), _l('5th'), _l('6th'), _l('7th'), _l('8th'),
                                                          _l('9th'), _l('10th'), _l('11th')])
    century_part = SelectMultipleField(_l('Century Part'), choices=[_l('First Half (00-49)'), _l('Last Half (50-99)'),
                                                                    _l('First Quarter (00-24)'),
                                                                    _l('Second Quarter (25-49)'),
                                                                    _l('Third Quarter (50-74)'),
                                                                    _l('Fourth Quarter (75-99)')])
    formulae = BooleanField('Formulae')
    chartae = BooleanField('Chartae')
    litterae = BooleanField('Litterae')
    submit = SubmitField(_l('Search'))
