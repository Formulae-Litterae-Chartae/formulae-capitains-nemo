Internationalization
====================
- We use flask-babel for the Internationalization
- I recommend to use [poedit](https://poedit.net/)
- - We followed the instructions on: https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xiii-i18n-and-l10n


Include new internationalized text snippets:
--------------------
Add a snippet similar to this `<p><b>{{ _('Hinweis:') }}</b></p>` in any of the html-files under /templates.
.. code-block:: shell
    $ source ~/envs/bin/activate
    (envs) $ pybabel compile -d translations
    (envs) $ pybabel extract -F babel.cfg -k _l -o messages.pot .
    (envs) $ pybabel update -i messages.pot -d translations 
    (envs) $ pybabel compile -d ./translations

How to update existing existing text blocks:
--------------------

.. code-block:: shell
    source ~/envs/bin/activate
    pybabel compile -d ./translations

should result in this terminal output:
.. code-block:: shell
    compiling catalog ./translations/en/LC_MESSAGES/messages.po to ./translations/en/LC_MESSAGES/messages.mo
    compiling catalog ./translations/fr/LC_MESSAGES/messages.po to ./translations/fr/LC_MESSAGES/messages.mo
