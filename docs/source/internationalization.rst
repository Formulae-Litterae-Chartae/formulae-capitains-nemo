Internationalization
====================
- We use flask-babel for the Internationalization
- I recommed to use [poedit](https://poedit.net/)
- - We followed the instructions on: https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xiii-i18n-and-l10n
- How to apply the changes:

.. code-block:: shell

    source ~/envs/bin/activate
    pybabel compile -d ./translations
    compiling catalog ./translations/en/LC_MESSAGES/messages.po to ./translations/en/LC_MESSAGES/messages.mo
    compiling catalog ./translations/fr/LC_MESSAGES/messages.po to ./translations/fr/LC_MESSAGES/messages.mo
