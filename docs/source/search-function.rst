Search function
#####################

How a Search Request Is Processed
=================================

This page follows three requests through
:py:func:`r_results` (route ``/search/results``) and
:py:func:`advanced_query_index`.

From the search form to the URL
-------------------------------

The simple-search form (``simple-search-form``) submits by GET to
``search.r_simple_search`` (``/search/simple``), not to the results
page. The form is created for every request in ``before_request``
(``g.search_form = SearchForm()``). ``r_simple_search`` converts the form
data and redirects to ``/search/results``:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Form field
     - Conversion
   * - ``q_1``
     - Lowercased.
   * - ``simple_search_id``
     - Renamed to ``search_id``.
   * - ``search_field``
     - Renamed to ``search_field_1`` (default ``text``).
   * - ``lemma_search``
     - Removed from the data. If it is ``y``, ``True`` or ``True``
       (boolean), ``search_field_1`` is set to ``lemmas``. The parameter
       itself does not appear in the redirected URL.
   * - ``corpus``
     - List joined with ``+``. ``url_for`` encodes the ``+`` as ``%2B``.

Special cases:

* If the form is invalid because of ``q_1``, a message is flashed
  ("the simple search only works with one search word") and an empty
  ``204`` response is returned, so the page does not change.
* If no corpus is selected, a message is flashed and the user is
  redirected with ``corpus=formulae+chartae``.
* The redirect always uses ``source=simple`` and ``sort=urn``. All
  remaining form fields are passed on as URL parameters.

Example 1: simple text search
-----------------------------

This is the kind of URL produced by ``r_simple_search`` for a normal
search.

.. code-block:: text

   https://tools.formulae.uni-hamburg.de/dev/search/results
       ?source=simple
       &corpus=formulae
       &sort=urn
       &q_1=advocatus
       &search_id=1398
       &search_field_1=text

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Parameter
     - Value
     - Purpose
   * - ``source``
     - ``simple``
     - Required. Without it the user is redirected to the index page.
   * - ``corpus``
     - ``formulae``
     - Collections to search. Several can be joined with ``+``.
   * - ``sort``
     - ``urn``
     - Sort order of the results.
   * - ``q_1``
     - ``advocatus``
     - First search query. Further queries use ``q_2``, ``q_3``, ...
   * - ``search_field_1``
     - ``text``
     - Field searched by ``q_1``. Per-query options use the suffix ``_<n>``.
   * - ``search_id``
     - ``1398``
     - Passed unchanged to the search function. If it is empty, no
       ``search_progress_...`` ID is used.

Processing steps
~~~~~~~~~~~~~~~~

1. Parameter check
^^^^^^^^^^^^^^^^^^

If ``source`` is missing, the user is redirected to
``InstanceNemo.r_index``.

2. Resolving the corpus
^^^^^^^^^^^^^^^^^^^^^^^

The ``corpus`` value is split on ``+`` and then on spaces. The result
decides which collections are listed:

.. list-table::
   :header-rows: 1

   * - ``corpus``
     - Collections in ``corps``
   * - contains ``elexicon``
     - ``elexicon`` only
   * - ``all``, ``formulae+chartae``, empty, ``form_lit_chart``
     - ``formulae_collection`` plus (sorted) ``other_collection``
   * - ``formulae``
     - ``formulae_collection``
   * - ``chartae``
     - ``other_collection`` (sorted)
   * - anything else
     - the given IDs, used as they are

The members of each group are defined in the Capitains metadata files
under ``data/``. For ``corpus=formulae``, the members of
hyperlink: `formulae-corpora/data/formulae_collection/__capitains__.xml <https://github.com/Formulae-Litterae-Chartae/formulae-corpora/blob/master/data/formulae_collection/__capitains__.xml>`_ are used:

.. code-block:: xml

   <collection identifier="urn:cts:formulae:andecavensis"
               path="../andecavensis/__capitains__.xml"/>
   <collection identifier="urn:cts:formulae:auvergne"
               path="../auvergne/__capitains__.xml"/>
   <!-- ... -->

The last segment of each URN (``andecavensis``, ``auvergne``, ...)
becomes an entry in ``corps``.

Every ID in ``corps`` is mapped through ``CORP_MAP['form_lit_chart-<id>']``
to build ``g.corpora``. If an ID is missing, a ``KeyError`` is logged.
Collections listed in ``ES_EXCLUDE_COLLECTIONS`` are then dropped as a
temporary workaround; if that setting is empty, the error is re-raised.

.. note::

   These files identify *collections*, not individual formulae.
   Individual texts are defined in each sub-collection's own
   ``__capitains__.xml``.

.. important::

   The expanded list ``corps`` is used only for ``g.corpora`` and the
   stored search arguments. The search itself receives the *unexpanded*
   ``corpus`` list (for example ``['formulae']``) and passes it directly
   as the ``index`` argument of the Elasticsearch calls in
   :py:func:`advanced_query_index`. If ``corpus`` is empty or ``all``, it
   is replaced by ``['form_lit_chart']``. The values ``formulae``,
   ``chartae`` and ``form_lit_chart`` therefore have to exist as
   Elasticsearch aliases.

.. note::

   ``formulae``, ``chartae`` and ``form_lit_chart`` are Elasticsearch
   aliases created by ``rebuild_elasticsearch_from_xml.py``. The script:

   * builds ``coll_type.json`` by walking
     ``data/display_formulae/__capitains__.xml`` (every text group found
     is mapped to ``formulae``),
   * indexes each text into a versioned index ``form_lit_chart-<id>_vN``,
   * puts three aliases on it: ``<id>``, the type from ``coll_type``
     (``formulae``, ``elexicon`` or, as a fallback, ``chartae``) and
     ``form_lit_chart``.

   A collection missing from ``coll_type`` silently becomes part of
   ``chartae``. The index must be rebuilt after changes to the Capitains
   files. ``CORP_MAP`` and ``corpus_agg`` only affect the displayed
   corpus list and the aggregation buckets, not which indices are
   searched.

1. Building the query dictionary
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A copy of the request arguments is passed through ``build_search_args``,
which translates short or legacy parameter names into the numbered form
that the rest of the code expects:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Incoming argument
     - Result
   * - ``corpus`` missing
     - ``'all'``. This does not affect ``r_results``, which reads
       ``corpus`` from the request before this function runs.
   * - ``bool_operator`` missing
     - ``'must'``
   * - ``q``
     - ``q_1`` (lowercased)
   * - ``search_field``, ``fuzziness``, ``in_order``, ``slop``
     - the same name with the suffix ``_1``
   * - ``lemma_search`` is ``y``, ``True`` or ``True`` (boolean)
     - ``search_field_1 = 'lemmas'``. This overrides ``search_field``.
   * - ``regest_q``
     - second query: ``q_2`` (lowercased) with ``search_field_2 = 'regest'``
   * - ``exclude_q``
     - ``exclude_q_1`` (lowercased)
   * - ``regex_search``
     - ``regex_search_1`` as the string ``'True'`` or ``'False'``
   * - ``proper_name``
     - ``proper_name_1``; a list is joined with ``+``
   * - any key containing ``regex_search`` or ``in_order``
     - normalised to the strings ``'True'`` or ``'False'``
   * - ``corpus``, ``special_days`` given as lists
     - joined with ``+``

Every key starting with ``q_`` then becomes one entry in ``query_dict``.
The query text is lowercased, and each option is read from
``<option>_<n>`` or falls back to a default:

.. list-table::
   :header-rows: 1

   * - Option
     - Default
   * - ``in_order``
     - ``'False'``
   * - ``regex_search``
     - ``False`` (boolean)
   * - ``proper_name``
     - ``''``
   * - ``slop``
     - ``0``
   * - ``fuzziness``
     - ``0``
   * - ``search_field``
     - ``'text'``
   * - ``exclude_q``
     - ``''``

For the example this gives:

.. code-block:: python

   {'q_1': {'q': 'advocatus', 'in_order': 'False', 'regex_search': False,
            'proper_name': '', 'slop': 0, 'fuzziness': 0,
            'search_field': 'text', 'exclude_q': ''}}

.. note::

   The default for ``regex_search`` is the boolean ``False``, whereas
   ``build_search_args`` produces the strings ``'True'`` and ``'False'``
   and ``advanced_query_index`` compares against these strings. See the
   wildcard warning in example 2.

4. Running the search
^^^^^^^^^^^^^^^^^^^^^

The remaining arguments (dates, ``forgeries``, ``bool_operator``, ...)
and ``query_dict`` are passed to ``advanced_query_index``. Date fields
default to ``0``, ``per_page`` is fixed at 10000, ``forgeries`` defaults
to ``include`` and ``bool_operator`` to ``must``. The function returns
the hits, the total count, the aggregations and the previous-search
information.

For ``source=simple``, a ``regest`` clause is added to every query. The
query terms must match either the selected search field or the regest
of a text, so simple searches also find texts through their summaries.
The ``regest`` field is highlighted as well.

If several queries are present (for example ``q_1`` and a second query
created from ``regest_q``), each is run separately. The results are then
combined according to ``bool_operator``: ``must`` keeps the hits shared
by all queries, ``must_not`` removes the hits of later queries from the
first, and ``should`` keeps all hits.

5. Storing the search for later pages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Unless ``old_search=True``, the request arguments are saved in
``g.previous_search_args`` (``corpus`` is replaced by the expanded list
of collection IDs) and the aggregations in ``g.previous_aggregations``.

6. Lemma lookup
^^^^^^^^^^^^^^^

For every query whose ``search_field`` is not ``lemmas``, each token is
looked up in ``inflected_to_lemma_mapping``. Tokens containing ``?`` or
``*`` are first expanded against the highlighted words. A query appears
in ``searched_lems`` only if all of its tokens have at least one lemma;
``max_cols`` is the largest token count among them.

7. Rendering
^^^^^^^^^^^^

The template ``search::search.html`` is rendered with the hits, total,
aggregations, ``searched_lems`` and ``max_cols``.

Example 2: lemma search in several corpora
------------------------------------------

.. code-block:: text

   https://tools.formulae.uni-hamburg.de/dev/search/results
       ?source=simple
       &corpus=formulae%2Bchartae
       &sort=urn
       &q=advocatus
       &lemma_search=True

.. list-table::
   :header-rows: 1
   :widths: 20 25 55

   * - Parameter
     - Value
     - Purpose
   * - ``source``
     - ``simple``
     - As in example 1.
   * - ``corpus``
     - ``formulae%2Bchartae``
     - ``%2B`` is a URL-encoded ``+``. It is what ``url_for`` produces
       in ``r_simple_search``. Flask decodes it, so the route sees
       ``formulae+chartae``.
   * - ``sort``
     - ``urn``
     - As in example 1.
   * - ``q``
     - ``advocatus``
     - Short form of ``q_1``. Translated by ``build_search_args``.
   * - ``lemma_search``
     - ``True``
     - Search the ``lemmas`` field instead of ``text``. Translated by
       ``build_search_args`` to ``search_field_1=lemmas``.

.. note::

   ``r_results`` and ``advanced_query_index`` never read ``q`` or
   ``lemma_search`` directly. ``build_search_args`` translates them (see
   step 3). A search started from the simple-search form does not
   produce this URL: ``r_simple_search`` already removes ``lemma_search``
   and sends ``q_1`` and ``search_field_1=lemmas`` instead. URLs with
   ``q`` and ``lemma_search`` are therefore accepted only as a
   convenience for hand-made or older links.

   The tooltip of the checkbox (``id="simple-lemma-checkbox"``) states
   that lemma search is only possible for Latin formulae texts.

Differences from example 1
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Corpus.** ``formulae+chartae`` is split on ``+`` into
``['formulae', 'chartae']``. This exact list is one of the "all
collections" cases, so ``corps`` contains the members of
``formulae_collection`` followed by the sorted members of
``other_collection``. The search itself receives the unexpanded list
and passes it as ``index=['formulae', 'chartae']`` to Elasticsearch,
which searches both aliases.

.. warning::

   The comparison is order-sensitive. ``chartae+formulae`` does not
   match the special case and is treated as a list of collection IDs,
   which do not exist in ``CORP_MAP``.

**No search ID.** ``search_id`` is empty, so no ``search_progress_...``
ID is used.

**Query.** Because ``search_field`` is ``lemmas``, ``advanced_query_index``
behaves differently:

* ``fuzziness`` is forced to ``'0'``.
* The u/v, i/j and w/uu normalisation applied to ``text`` searches is
  skipped.
* If the searched lemma is a key of ``nemo_app.lem_to_lem_mapping``,
  each related lemma is added as an extra clause (see example 3).
* The ``lemmas`` field is added to the highlighted fields.
* ``?`` and ``*`` are meant to be rejected with a flash message and an
  empty result, unless ``regex_search`` is ``'True'``.

.. warning::

   The wildcard rejection only works if ``regex_search`` is the string
   ``'False'``. ``build_search_args`` sets that string only when a
   ``regex_search`` parameter is present in the request. Otherwise
   ``r_results`` uses the boolean ``False``, the comparison fails, and
   wildcards on ``lemmas`` are processed as ordinary wildcard (regexp)
   queries instead of being rejected.
   [TO BE VERIFIED: test with ``q=advoc*&lemma_search=True``.]

**Lemma lookup (step 6)** is skipped for queries on ``lemmas``, so
``searched_lems`` stays empty and ``max_cols`` is ``0``. The template
therefore shows no inflected-form-to-lemma columns.

**Highlighting.** For every search that has a query,
``lem_highlight_to_text`` combines the highlighted fields and returns
the text the user sees. For lemma searches, the highlights in ``lemmas``
are transferred to the text this way.

Example 3: a result that does not contain the searched word
-----------------------------------------------------------

.. code-block:: text

   https://werkstatt.formulae.uni-hamburg.de/search/results
       ?source=simple
       &corpus=formulae%2Bchartae
       &sort=urn
       &q=vicarius
       &lemma_search=True

This URL is built like example 2 (see there for the parameters), only
with ``q=vicarius``. It illustrates a case that can look like an error:
the results include **Bourges C 13**
(``urn:cts:formulae:bourges.form_c_013.lat001``), although the text
never contains the word ``vicarius``.

What the indexed document contains
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Field
     - Contains ``vicarius``?
     - Relevant content
   * - ``lemmatized`` (searched field ``lemmas``)
     - no
     - ``vicaria`` three times (``in vicaria ille_platzhalter``, ...)
   * - ``inflected`` (field ``text``)
     - no
     - the spellings ``vigarias`` and ``vigaria``
   * - ``regest``
     - no
     - "Hochzeitsgabe verschiedener Güter ..."

Why the text is still found
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. ``build_search_args`` turns ``q`` and ``lemma_search=True`` into
   ``q_1=vicarius`` and ``search_field_1=lemmas`` (see step 3).
2. In ``advanced_query_index``, the searched term is looked up in
   ``nemo_app.lem_to_lem_mapping``, which is loaded from
   ``lem_to_lem.json``. For ``vicarius`` the file contains:

   .. code-block:: json

      "vicarius": [
          "vigerius",
          "vicaria"
      ],

3. One exact-match clause is created for ``vicarius`` itself and one
   for each related lemma, that is ``vigerius`` and ``vicaria``. A text
   matches if it contains any of them. Because ``fuzziness`` is forced
   to ``0`` for lemma searches, each clause is an exact match.
4. Bourges C 13 contains ``vicaria`` in its ``lemmas`` field, so it
   matches the third clause.

The mapping is applied to the searched term only, and only if that term
is a key of ``lem_to_lem_mapping``.

.. note::

   The ``regest`` clause that is added for ``source=simple`` is not the
   reason for this hit. It uses the searched word as typed and does not
   apply the mapping, and the regest of Bourges C 13 does not contain
   ``vicarius``.

.. note::

   The mapping is not necessarily symmetric. A search for ``vicaria``
   uses the list under the key ``vicaria``, if there is one, and finds
   texts with ``vicarius`` only if that list contains it. This means the
   results can depend on which variant the user types.
   [TO BE VERIFIED: check the ``vicaria`` entry in ``lem_to_lem.json``.]

What the user sees
~~~~~~~~~~~~~~~~~~

The highlights are made in ``lemmas``, and ``lem_highlight_to_text``
transfers them to the inflected text. The user should therefore see the
spellings ``vigarias`` and ``vigaria`` highlighted, even though neither
looks like ``vicarius``. [TO BE VERIFIED in the result page.]

Finding out why a text was returned
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Open the text's Elasticsearch document and check the field that was
   searched (``lemmas`` for a lemma search, ``text`` otherwise).
2. Look up the searched term in ``lem_to_lem.json``. Every lemma
   listed there is searched as well.
3. If the cause is still unclear, inspect the request bodies built in
   ``advanced_query_index`` (the list ``searched_templates``) and the
   ``highlight`` part of the hit.


lem_to_lem.json
=================================
