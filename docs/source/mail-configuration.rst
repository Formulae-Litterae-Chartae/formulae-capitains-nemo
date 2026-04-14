Mail configuration (SMTP via eclipso.de)
=======================================

For sending application emails (e.g. error notifications), the project uses a
standard SMTP setup via an external mail provider. In our current configuration,
we use :contentReference[oaicite:0]{index=0} as the SMTP backend.

This avoids running a local mail server while still allowing the Flask
application to send emails reliably.

Configuration via environment variables
---------------------------------------

The mail setup is configured via environment variables (e.g. in ``.env`` or
``docker-compose.yml``):

.. code-block:: bash

   ADMINS=<string of email addresses of admins separated by ;>
   MAIL_USERNAME=<string>
   MAIL_PASSWORD=<string>
   MAIL_SERVER=<string>
   MAIL_PORT=587

The individual variables have the following meaning:

``ADMINS``
    A semicolon-separated list of email addresses that should receive
    administrative notifications (e.g. error mails). The application parses
    this string into a list internally.

    Example::

        ADMINS=admin1@example.org;admin2@example.org

``MAIL_USERNAME``
    The SMTP login username. For eclipso this is typically identical to the
    mailbox address.

``MAIL_PASSWORD``
    The password for the SMTP account.

``MAIL_SERVER``
    The SMTP server hostname provided by the mail service.

``MAIL_PORT``
    The SMTP port. Port ``587`` with STARTTLS is recommended and used
    by default.

Notes on usage
--------------

- The sender address should normally match ``MAIL_USERNAME`` to avoid
  rejection by the SMTP server.
- The application uses TLS (STARTTLS) for transport encryption.
- When using a hosted mailbox provider like eclipso, SPF/DKIM handling is
  managed by the provider and does not need to be configured manually.

Admin recipients
----------------

The ``ADMINS`` variable is defined as a single string to simplify configuration
in container environments. It is split on ``;`` at runtime, e.g.:

.. code-block:: python

   admins = [addr.strip() for addr in ADMINS.split(";") if addr.strip()]

Make sure there are no trailing separators or whitespace issues, as malformed
addresses can lead to SMTP errors.

Testing the setup
----------------

A minimal test can be performed by triggering a simple mail send within the
application context. If correctly configured, the message should be accepted by
the SMTP server and delivered to the configured recipients.

If emails are not received:

- verify credentials (username/password)
- check spam/junk folders
- ensure the SMTP server and port are correct
- inspect application logs for SMTP errors

``SMTPRecipientsRefused`` errors often indicate malformed recipient addresses,
while connection or authentication errors usually point to incorrect server
settings.

.. note::

   Third-party SMTP providers such as :contentReference[oaicite:1]{index=1} or
   :contentReference[oaicite:2]{index=2} typically require proper domain
   authentication (SPF and DKIM) for reliable email delivery.

   When using institutional email addresses (e.g. university or company
   mailboxes), this often does not work in practice, because the domain is
   centrally managed and DNS records cannot be modified by individual users.

   In particular:

   - SPF records must explicitly authorize the SMTP provider
   - DKIM requires publishing provider-specific DNS records
   - both require administrative access to the domain’s DNS configuration

   Without these settings, messages may be rejected, soft-bounced, or silently
   discarded by receiving servers.

   Therefore, when working with institutional mail accounts, it is usually more
   reliable to use the provider’s own SMTP service instead of a third-party
   relay.

   Alternatively, a dedicated domain under your control can be used for
   application email sending.