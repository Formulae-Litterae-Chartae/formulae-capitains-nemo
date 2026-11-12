.. _lem-to-lem:

Lemma mapping files
===================

Three JSON files are generated from the lemmatised corpus. They are
produced together by one script from the output of Pyrrha, the tool
used for lemmatisation:

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - File
     - Maps
     - Used for
   * - ``lem_to_lem.json``
     - variant lemma to a list of primary lemmas
     - extra clauses in lemma searches (``advanced_query_index``, see
       example 3)
   * - ``inflected_to_lem.json``
     - inflected form to a list of lemmas
     - the lemma columns on the result page after a text search
       (``inflected_to_lemma_mapping``, step 6)
   * - ``lemma_list.json``
     - sorted list of all lemmas
     - [TO BE VERIFIED: where the application uses it, for example
       for suggestions in the search form]

The files do not change the content of the Elasticsearch index. The
``lemmatized`` field of each text is produced elsewhere. Changing a
mapping therefore changes which lemmas are *searched* or *displayed*,
but not which lemmas a text *has*.

Source data: the Pyrrha output
------------------------------

The script reads TSV files exported from Pyrrha. Each file has the
columns ``form``, ``lemma``, ``POS`` and ``morph``.

* The first line of every file (the header) is skipped.
* A line that starts with ``**`` marks the start of a new text. The name
  after the asterisks is used for the per-text files in ``results/``.
* Every other line is one token with its annotation.

Lemma notation
~~~~~~~~~~~~~~

The ``lemma`` column can contain more than one lemma. The script splits
it into a **primary lemma** and **variant lemmas**:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Lemma column
     - Primary lemma
     - Entries added to ``lem_to_lem.json``
   * - ``a``
     - ``a``
     - none
   * - ``a/b/c``
     - ``a``
     - ``b -> a``, ``c -> a``
   * - ``a=b+c``
     - ``a``
     - ``b -> a``, ``c -> a``
   * - ``a/b=c+d``
     - ``a``
     - ``b -> a``, ``c -> a``, ``d -> a``
   * - ``a-b+c``
     - ``a``
     - ``b -> a``, ``c -> a``

* The first lemma before a ``/`` is always the primary lemma.
* The ``=`` rule is checked first. A lemma column that contains ``-``
  but no ``=`` is read as ``primary-components``. Any lemma containing
  a hyphen is therefore split at the hyphen.
* Components after ``=`` or ``-`` are separated by ``+``. Each
  component may itself contain ``/`` alternatives, and all of them
  become variants of the primary lemma.
* A lemma that equals the primary lemma never gets an entry.
* [TO BE COMPLETED by the lemmatisation team: the editorial meaning of
  ``/``, ``=`` and ``-`` in the Pyrrha annotation.]

Before parsing, each line is lowercased and ``$`` is removed. Tokens
without any word character (punctuation) are skipped.

Illustration (constructed lines, not taken from the corpus): the
annotations ``vicaria/vicarius`` and ``vigerius/vicarius`` produce

.. code-block:: json

   "vicarius": ["vicaria", "vigerius"]

Running the script
------------------

.. code-block:: bash

   python3 ~/git/scripts/corpus_transformation_scripts/lemmatization/create_lem_to_lem_json.py \
       ~/git/Lemmatization/pyrrha_output/formeln-fsb.tsv \
       ~/git/Lemmatization/pyrrha_output

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Argument
     - Meaning
   * - 1 (required)
     - Either a single ``.tsv`` file or a directory. For a file, only
       that file is read, the output prefix is the path without the
       extension and without ``formeln-`` (here
       ``.../pyrrha_output/fsb``), and the ``results`` folder is created
       next to it. For a directory, all ``*.tsv`` files in it are read,
       the prefix is ``<directory>/all_files`` and ``results`` is
       created inside it.
   * - 2 (optional)
     - Destination folder for the three main files (``lem_to_lem.json``,
       ``inflected_to_lem.json``, ``lemma_list.json``) and for
       ``Formulae+Urkunden.csv``. If it is omitted, the main files are
       written next to the input under the names in the table below.

.. warning::

   With the command above only ``formeln-fsb.tsv`` is read, so the
   generated files contain only the data of that file. To cover all
   corpora, pass the directory as the first argument.
   [TO BE VERIFIED: which input is intended for the production files.]

What the script does
~~~~~~~~~~~~~~~~~~~~

For every token line the script:

1. keeps the original lemma column (case and ``$`` unchanged) as the
   *full lemma*,
2. lowercases the line, removes ``$`` and skips punctuation,
3. determines the primary lemma and the variants (see the notation
   above),
4. adds ``variant -> primary lemma`` to ``lem_to_lem_mapping``,
5. adds ``inflected form -> primary lemma`` to
   ``inflected_to_lem_mapping``,
6. adds ``inflected form -> full lemma`` to
   ``inflected_to_full_lem_mapping``, and to the formulae or charters
   variant of it, depending on whether the path of the TSV file
   contains ``formeln``,
7. adds the lemmas to the set ``all_lems``, except those that contain
   ``!`` or ``?`` and the German placeholder lemmas
   (``personenname``, ``ortsname``, ``volksstamm``, ``monatsname``,
   ``tagesbezeichnung``, ``platzhalter``).

At the end all sets are converted to lists and written as JSON with
sorted keys, tab indentation and unescaped non-ASCII characters. Only
the keys are sorted. The order inside the lists comes from sets and is
therefore arbitrary and can change between runs.

Output files
~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 24 24 52

   * - File (with destination folder)
     - File (without destination folder)
     - Content
   * - ``lem_to_lem.json``
     - ``<prefix>_lem_to_lem_mapping.json``
     - variant lemma to list of primary lemmas
   * - ``inflected_to_lem.json``
     - ``<prefix>_inflected_to_full_lem_mapping.json``
     - inflected form to the full lemma annotations as written in
       Pyrrha (see below)
   * - ``lemma_list.json``
     - ``<prefix>_lemma_list.json``
     - sorted list of all lemmas
   * - ``<prefix>_inflected_to_lem_mapping.json``
     - the same
     - inflected form to list of primary lemmas. Always written next to
       the input, never to the destination folder.
   * - ``<prefix>_inflected_to_full_lem_mapping_formulae.json`` and
       ``..._charters.json``
     - the same
     - as the full-lemma mapping, split by whether the path of the TSV
       file contains ``formeln``. Always written next to the input.
   * - ``Formulae+Urkunden.csv``
     - same name, in the current directory
     - all lines of the input files in one file
   * - ``results/<text>.txt``
     - the same
     - one file per text with the columns inflected form, primary lemma
       and display lemma

.. note::

   The names of the outputs are easy to confuse. The file called
   ``inflected_to_lem.json`` contains the **full** annotations. The
   mapping to the **primary** lemmas is ``<prefix>_inflected_to_lem_mapping.json``.
   [TO BE VERIFIED: the ``inflected_to_lem.json`` used by the application
   (``formulae-corpora/inflected_to_lem.json``) should be checked for
   values containing ``/``, ``=`` or ``-``. If there are none, it holds
   primary lemmas or was generated by a different version of the
   script, and this table must be corrected.]

The three files in detail
-------------------------

``lem_to_lem.json``
~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
       "vicarius": [
           "vigerius",
           "vicaria"
       ]
   }

* **Key:** a variant lemma (lowercase).
* **Value:** the primary lemmas that this variant was annotated with.
* **Direction:** the mapping goes from variant to primary lemma only.
  A primary lemma has a key only if it also occurs as a variant in
  another annotation. ``vicaria`` is a primary lemma and has no key, so
  a lemma search for ``vicaria`` finds only ``vicaria``, whereas a
  search for ``vicarius`` finds ``vicarius``, ``vigerius`` and
  ``vicaria``.
* **No filtering:** the ``!``, ``?`` and placeholder filters of
  ``lemma_list.json`` do not apply, so such lemmas can appear here.

*Use in the search.* ``nemo_app.lem_to_lem_mapping`` is read in
``advanced_query_index``:

* For a lemma search, the searched term is looked up. If it is a key,
  one exact-match clause is added for the term and one for each listed
  lemma (see example 3).
* For a proper-name search, ``lem_to_lem_mapping[term]`` is read
  without a default, so a name that is not a key may raise a
  ``KeyError``. [TO BE VERIFIED: depends on how the mapping is loaded.]

[TO BE COMPLETED: where and when ``lem_to_lem.json`` is loaded, and
whether a new version needs a restart of the application.]

``inflected_to_lem.json``
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
       "vicaria": [
           "vicarius",
           "vicaria"
       ]
   }

* **Key:** an inflected form as it occurs in the tokens (lowercase).
* **Value:** the lemma annotations that this form received in the
  Pyrrha files. According to the script, these are the *full* lemma
  columns, taken before lowercasing and before ``$`` is removed.
* The example says that the form ``vicaria`` was annotated as
  ``vicarius`` in some places and as ``vicaria`` in others. This
  inconsistency is probably why ``lem_to_lem.json`` contains
  ``vicarius -> vicaria``.

*Loading.* ``make_inflected_to_lem_mapping`` reads every file listed in
the configuration setting ``INFLECTED_LEM_JSONS`` (currently
``.../inflected_to_lem.json``) and merges them into one dictionary
``inflected_to_lemma_mapping``. For a form that occurs in several
files, the lemma lists are combined as a set, which removes duplicates
and loses the order. An invalid JSON file is skipped with a logged
warning. A missing file raises ``FileNotFoundError``.

*Use in the search.* In ``r_results`` (step 6), each token of a text
search is looked up in this mapping to fill the lemma columns of the
result page. The mapping does **not** change which texts are found. The
lookup uses the typed token as the key, which works because ``q_1`` is
lowercased earlier.

``lemma_list.json``
~~~~~~~~~~~~~~~~~~~

A sorted JSON list of all lemmas found in the input: all primary lemmas
and all variant lemmas.

* Lemmas containing ``!`` or ``?`` are left out.
* The German placeholder lemmas are left out (see above).
* In the ``a-b+c`` notation the primary lemma ``a`` is not added by
  itself. It appears in the list only if it occurs elsewhere.

[TO BE VERIFIED: where the application reads ``lemma_list.json``.]

Updating the files
------------------

1. Correct the annotations in the Pyrrha output (the TSV files). Do not
   edit the generated JSON files by hand, because the next run
   overwrites them.
2. Run the script (see above) and write the files to the destination
   folder.
3. Copy ``lem_to_lem.json``, ``inflected_to_lem.json`` and
   ``lemma_list.json`` to the place the application reads them from
   (``formulae-corpora``). [TO BE VERIFIED: copy procedure and whether
   the application must be restarted.]
4. If the *primary* lemma of a token changed, the texts must be
   exported and indexed again, because the ``lemmatized`` field in
   Elasticsearch is not produced by this script (see
   ``rebuild_elasticsearch_from_xml.py``).

Finding the annotation behind an entry
--------------------------------------

To see why ``lem_to_lem.json`` contains an entry, search the Pyrrha
files for the variant:

.. code-block:: bash

   grep -i vicarius ~/git/Lemmatization/pyrrha_output/*.tsv

The matching lines show the annotation (``lemma`` column) that created
the entry, for example a primary lemma followed by ``/vicarius``.