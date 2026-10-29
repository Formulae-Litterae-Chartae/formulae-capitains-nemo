Navigation bar
====================

How to add an entry to the menu / navigation bar:

1. Add an entry to templates/main/navbar.html:

.. code-block:: html



    <li class="nav-item">
        <a class="nav-link active" href="{{url_for('InstanceNemo.r_collection', objectId='lexicon_entries', )}}">{{ _('Lexikon') }}</a>
    </li>

1. Optional: Add an entry to templates/main/index.html:

.. code-block:: html
   :linenos:



    <div class="col">
        <h5 class="text-center"><a class="internal-link"
                href="{{ url_for('InstanceNemo.r_collection', objectId='lexicon_entries') }}">{{
                _('Zum E-Lexikon') }}</a></h5>
    </div>




