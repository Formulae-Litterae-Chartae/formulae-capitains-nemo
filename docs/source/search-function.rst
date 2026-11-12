Search function
#####################

How a Search Request Is Processed
=================================

This page follows one request through
:py:func:`r_results` (route ``/search/results``).

Example request
---------------

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
     - Passed unchanged to the search function.

Processing steps
----------------

1. Parameter check
~~~~~~~~~~~~~~~~~~

If ``source`` is missing, the user is redirected to
``InstanceNemo.r_index``.

2. Resolving the corpus
~~~~~~~~~~~~~~~~~~~~~~~

The collections that make up each corpus group are defined in the
Capitains metadata files under ``data/``. For ``corpus=formulae``, the
members of ``data/formulae_collection/__capitains__.xml`` are used:

.. code-block:: xml

   <collection identifier="urn:cts:formulae:andecavensis"
               path="../andecavensis/__capitains__.xml"/>
   <collection identifier="urn:cts:formulae:auvergne"
               path="../auvergne/__capitains__.xml"/>
   <!-- ... -->

The last segment of each URN (``andecavensis``, ``auvergne``, ...)
becomes an entry in ``corps``. Adding or removing a ``<collection>``
element in this file therefore changes what ``corpus=formulae``
searches, but the new ID must also exist in ``CORP_MAP`` (see
``Search.py``), otherwise the ``KeyError`` handling described below
applies.

.. note::

   These files identify *collections*, not individual formulae.
   Individual texts are defined in each sub-collection's own
   ``__capitains__.xml``.

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
   corpus list and the aggregation buckets, not which indices are searched.

3. Building the query dictionary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All request arguments pass through ``build_search_args``. Every key
starting with ``q_`` becomes one entry in ``query_dict``. The query text
is lowercased, and each option is read from ``<option>_<n>`` or falls
back to a default:

.. list-table::
   :header-rows: 1

   * - Option
     - Default
   * - ``in_order``
     - ``'False'``
   * - ``regex_search``
     - ``False``
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

4. Running the search
~~~~~~~~~~~~~~~~~~~~~

The remaining arguments (dates, ``forgeries``, ``bool_operator``, ...)
and ``query_dict`` are passed to ``advanced_query_index``. Date fields
default to ``0``, ``per_page`` is fixed at 10000, ``forgeries`` defaults
to ``include`` and ``bool_operator`` to ``must``. The function returns
the hits, the total count, the aggregations and the previous-search
information.

5. Storing the search for later pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unless ``old_search=True``, the request arguments are saved in
``g.previous_search_args`` (``corpus`` is replaced by the expanded list
of collection IDs) and the aggregations in ``g.previous_aggregations``.

6. Lemma lookup
~~~~~~~~~~~~~~~

For every query whose ``search_field`` is not ``lemmas``, each token is
looked up in ``inflected_to_lemma_mapping``. Tokens containing ``?`` or
``*`` are first expanded against the highlighted words. A query appears
in ``searched_lems`` only if all of its tokens have at least one lemma;
``max_cols`` is the largest token count among them.

7. Rendering
~~~~~~~~~~~~

The template ``search::search.html`` is rendered with the hits, total,
aggregations, ``searched_lems`` and ``max_cols``.