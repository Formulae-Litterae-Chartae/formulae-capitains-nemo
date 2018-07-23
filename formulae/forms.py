from flask import request
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import StringField, BooleanField
from wtforms.validators import DataRequired


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
