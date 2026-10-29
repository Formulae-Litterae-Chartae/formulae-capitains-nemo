Application modes and the ``SERVER_TYPE`` switch
===============================================

The application distinguishes between different runtime modes via the
``SERVER_TYPE`` environment variable. While this may look like a small
configuration detail at first, it has become a central switch that controls a
number of behaviors that should differ between development and production.

In practice, this variable acts as a coarse-grained feature toggle for anything
that is either:

- potentially disruptive during development
- security-relevant
- or simply unnecessary outside a production context

Configuration
-------------

The variable is defined in the environment (e.g. ``.env`` or
``docker-compose.yml``):

.. code-block:: bash

   SERVER_TYPE="production"

Typical values are:

- ``dev`` (default / local development)
- ``production`` (deployed environment)

Other values (e.g. ``staging``) can be introduced if needed, but are not
currently used.

Error handling and email notifications
-------------------------------------

One of the primary uses of ``SERVER_TYPE`` is to control global error handling.

In production mode, a global exception handler is registered:

.. code-block:: python

   if app.config['SERVER_TYPE'] == "production":
       app.register_error_handler(Exception, e_internal_error)

This ensures that all uncaught exceptions are:

- logged centrally
- processed uniformly
- and (depending on configuration) forwarded via email

During development, this handler is intentionally **not** registered. This is
important because Flask’s built-in debugger provides a much more useful
interface for inspecting errors interactively. Overriding it with a generic
error page would make debugging unnecessarily difficult.

In other words:

- in ``dev`` → prefer visibility and interactivity
- in ``production`` → prefer stability and controlled failure handling

Interaction with mail configuration
----------------------------------

The mail configuration described in :doc:`mail-configuration` is primarily
intended for production use. While it can technically be enabled in development,
this is usually not desirable.

In earlier iterations, enabling email notifications during development led to:

- repeated SMTP login attempts
- rate limiting or temporary blocking by providers
- confusing duplicate notifications

By tying error handling to ``SERVER_TYPE``, email notifications are implicitly
limited to production environments, where they are actually useful.

Access restrictions for unauthenticated users
--------------------------------------------

Another behavior controlled by ``SERVER_TYPE`` is access to resource-intensive
functionality.

The variable ``MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER`` defines how many
texts can be combined in a single request. This is particularly relevant for
routes that allow combining multiple resources via ``+`` in the URL.

In development, this limit is typically relaxed:

- easier testing
- no authentication required

In production, it is usually restricted:

.. code-block:: bash

   SERVER_TYPE="production"
   MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER=1

This reduces the risk of:

- excessive server load
- abuse via automated requests
- accidental denial-of-service scenarios

The logic is implemented in the application layer (see
``NemoFormulae.r_multipassage``), and complements the Varnish-based filtering
described in :doc:`traffic-management`.

Design considerations
--------------------

Using a single variable to control multiple aspects of the application is a
deliberate trade-off.

Advantages:

- simple mental model (``dev`` vs ``production``)
- easy to configure in container environments
- consistent behavior across features

Disadvantages:

- coarse-grained control (all-or-nothing switching)
- implicit coupling between otherwise unrelated features

For the current scope of the project, the simplicity outweighs the drawbacks.
If the application grows further, it may become desirable to split this into
more fine-grained feature flags.

Outlook
-------

At the moment, ``SERVER_TYPE`` provides a pragmatic way to separate development
and production concerns without introducing additional configuration overhead.

Future improvements might include:

- introducing a dedicated ``staging`` mode
- separating mail, error handling, and access control into independent toggles
- or integrating more structured configuration management

For now, however, this approach has proven to be robust enough and keeps the
configuration surface manageable.