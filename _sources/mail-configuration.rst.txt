Mail configuration (SMTP via Mailjet and custom domain)
======================================================

For sending application emails (e.g. error notifications), the project uses a
standard SMTP setup via an external mail provider. After experimenting with
hosted mailbox providers such as :contentReference[oaicite:0]{index=0}, the current setup settled on
:contentReference[oaicite:1]{index=1} in combination with a dedicated domain
(`formulae.top`).

The domain was registered cheaply (well below 5€ per year) via
:contentReference[oaicite:2]{index=2} and is used exclusively for
application email sending. This turned out to be the most robust solution so far
and avoids a number of subtle issues that arise when trying to reuse existing
mailboxes for automated tasks.

Configuration via environment variables
---------------------------------------

The mail setup is configured via environment variables (e.g. in ``.env`` or
``docker-compose.yml``):

.. code-block:: bash

   ADMINS=<string of email addresses of admins separated by ;>
   MAIL_USERNAME=<string>
   MAIL_PASSWORD=<string>
   MAIL_SERVER="in-v3.mailjet.com"
   MAIL_PORT=587
   MAIL_DEFAULT_SENDER='noreply@formulae.top'

The individual variables have the following meaning:

``ADMINS``
    A semicolon-separated list of email addresses that should receive
    administrative notifications (e.g. error mails). The application parses
    this string into a list internally.

    Example::

        ADMINS=admin1@example.org;admin2@example.org

``MAIL_USERNAME``
    The SMTP login username provided by Mailjet. In practice this is not a
    mailbox address but an API key.

``MAIL_PASSWORD``
    The corresponding SMTP password (secret key).

``MAIL_SERVER``
    The SMTP server hostname. For Mailjet this is ``in-v3.mailjet.com``.

``MAIL_PORT``
    The SMTP port. Port ``587`` with STARTTLS is recommended and used
    by default.

``MAIL_DEFAULT_SENDER``
    The sender address used by the application. This should belong to the
    authenticated domain (here: ``formulae.top``).

Notes on usage
--------------

- The sender address should match the authenticated domain (e.g.
  ``noreply@formulae.top``).
- The application uses TLS (STARTTLS) for transport encryption.
- SPF and DKIM must be configured for the domain in order to achieve reliable
  delivery.
- Mailjet requires domain verification; the DNS setup (SPF/DKIM) is therefore
  not optional but part of the initial configuration.

Previous approaches and limitations
----------------------------------

Earlier attempts used hosted mailbox providers such as eclipso. While this works
in principle, it turned out to be unreliable in practice:

- repeated SMTP logins (e.g. during development or debugging) triggered account
  blocks surprisingly quickly
- rate limits were reached without much load
- automated application behavior was flagged as suspicious activity

In short, what works fine for human users does not necessarily translate well to
programmatic access.

Other providers such as Outlook.com were also considered, but rely on more
complex or interactive authentication mechanisms, which makes them awkward to
integrate into a simple Flask-based workflow.

Switching to a transactional provider combined with a dedicated domain solved
these issues cleanly. It requires a bit more initial setup (DNS configuration),
but behaves much more predictably afterwards.

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

   Third-party SMTP providers such as :contentReference[oaicite:3]{index=3} or
   :contentReference[oaicite:4]{index=4} require proper domain
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

   Using a dedicated domain under your control (as done here) is therefore the
   most robust solution for application email sending.

Outlook
-------

The current setup works well for the intended purpose (error reporting via
email), and for the time being there is no strong need to optimize further.

It is entirely possible that future changes (either in providers or in the
application architecture) will suggest a different approach. For now, however,
this configuration strikes a reasonable balance between reliability, simplicity,
and cost, and allows development effort to focus on more relevant aspects such
as improving the logging and error handling itself.