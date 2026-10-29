Lemmatization marker in the navigation
======================================

While working on the navigation bar, I ran into the question where the little asterisk (``*``) next to some corpora actually comes from. It turns out that this is not defined in the template itself, but entirely driven by the collection metadata.

Where the information comes from
--------------------------------

The relevant piece is in the collection’s ``__capitains__.xml`` file. For example:

.. code-block:: xml

   <structured-metadata>
     <bib:AbbreviatedTitle>Auvergne</bib:AbbreviatedTitle>
     <bib:Annotations>Lemmas</bib:Annotations>
     <dct:isPartOf>urn:cts:formulae:p14</dct:isPartOf>
   </structured-metadata>

The important line here is:

.. code-block:: xml

   <bib:Annotations>Lemmas</bib:Annotations>

If this value is set to ``Lemmas``, the corpus is treated as lemmatized.

How this is handled in the backend
---------------------------------

In ``nemo.py``, this metadata is read and turned into a simple boolean:

.. code-block:: python

   for m in data['collections']['members']:
       m['lemmatized'] = str(
           self.resolver.getMetadata(m['id']).metadata.get_single(self.BIBO.Annotations)
       ) == 'Lemmas'

So effectively:

* metadata says ``Lemmas`` → ``lemmatized = True``
* anything else → ``lemmatized = False``

This flag is then passed on to the template.

What the template does with it
-----------------------------

In ``navbar.html`` the flag controls whether the asterisk is visible:

.. code-block:: html+jinja

   <span
       data-toggle="tooltip"
       {% if not coll['lemmatized'] %} class="invisible"{% endif %}
       title="{{ _('Dieses Korpus ist lemmatisiert') }}"
   >* </span>

So:

* if ``coll['lemmatized']`` is true → the ``*`` is shown
* if not → it is hidden via the ``invisible`` class

The tooltip text is:

::

   Dieses Korpus ist lemmatisiert


In practice
-----------

If a corpus should show up as lemmatized in the navigation, the only thing that needs to be set is:

.. code-block:: xml

   <bib:Annotations>Lemmas</bib:Annotations>

in its ``__capitains__.xml``.

Everything else (boolean flag, UI marker, tooltip) follows from that.