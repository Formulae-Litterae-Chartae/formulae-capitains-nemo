****************************************
Varnish
****************************************

==============================================
Adding a custom Error message for 503 errors:
==============================================

----------------------------------------------
1. Back up your current VCL
----------------------------------------------
.. code-block:: shell

    sudo cp /etc/varnish/default.vcl /etc/varnish/default.vcl.backup

----------------------------------------------
2. Add a temporary broken backend
----------------------------------------------
Keep your normal backend:

.. code-block:: python
   :linenos:

    backend default {
        .host = "127.0.0.1";
        .port = "8000";
    }

Then add the temporary test backend:

.. code-block:: python
   :linenos:

    # Temporary backend to test vcl_backend_error. Remove after 2026-06-30.
    backend broken_test {
        .host = "127.0.0.1";
        .port = "8888";
    }

This assumes nothing is listening on ``127.0.0.1:8888``.

Check that with:

.. code-block:: shell

    sudo ss -ltnp | grep ':8888'

No output is good.

----------------------------------------------
1. Add the temporary test route in vcl_recv
----------------------------------------------
If your app is reached under /dev, use:

.. code-block:: python
   :linenos:

    sub vcl_recv {
        # Temporary URL to test vcl_backend_error. Remove after 2026-06-30.
        if (req.url == "/dev/__test_503") {
            set req.backend_hint = broken_test;
            return (pass);
        }

        # existing logic...
    }


If your app is reached under /, use:

.. code-block:: python
   :linenos:

    sub vcl_recv {
        # Temporary URL to test vcl_backend_error. Remove after 2026-06-30.
        if (req.url == "/dev/__test_503") {
            set req.backend_hint = broken_test;
            return (pass);
        }

        # existing logic...
    }

----------------------------------------------
4. Add the custom vcl_backend_error
----------------------------------------------
Add this outside the other sub blocks:

.. code-block:: html
   :linenos:

    sub vcl_backend_error {
        set beresp.status = 503;
        set beresp.reason = "Service temporarily unavailable";
        set beresp.http.Content-Type = "text/html; charset=utf-8";
        set beresp.http.Retry-After = "300";

        synthetic({"
    <!doctype html>
    <html lang='en'>
    <head>
    <meta charset='utf-8'>
    <title>Service unavailable</title>
    </head>
    <body>
    <h1>Service unavailable</h1>
    <p>The Formulae application is temporarily unavailable.</p>
    <p>Project website: <a href='https://formulae.awhamburg.de/'>formulae.awhamburg.de</a></p>
    </body>
    </html>
    "});

        return (deliver);
    }


----------------------------------------------
5. Check the VCL
----------------------------------------------
Use the less noisy check:

.. code-block:: shell

    sudo varnishd -C -f /etc/varnish/default.vcl > /dev/null && echo "VCL OK" || echo "VCL ERROR"

If you see: ``VCL OK`` the file compiles successfully.

----------------------------------------------
6. Reload Varnish
----------------------------------------------

.. code-block:: shell

    sudo systemctl reload varnish

----------------------------------------------
7. Test locally on the Varnish port
----------------------------------------------
Since your Varnish listens on 127.0.0.1:8080, test:

.. code-block:: shell

    curl -i http://127.0.0.1:8080/dev/__test_503 -H "Host: your-domain.example"

Expected result:

.. code-block:: shell

    HTTP/1.1 503 Service temporarily unavailable
    Server: Varnish
    Content-Type: text/html; charset=utf-8
    Retry-After: 300
    Via: 1.1 varnish (Varnish/6.6)

----------------------------------------------
7. Test through the public URL
----------------------------------------------
Use the public path including /dev: ``https://your-domain.example/dev/__test_503`` 

You should see the same custom 503 page.

----------------------------------------------
8.  Clean up after testing
----------------------------------------------
Remove the temporary test backend:

.. code-block:: python
   :linenos:

    backend broken_test {
        .host = "127.0.0.1";
        .port = "8888";
    }

Remove the temporary route from vcl_recv:

.. code-block:: python
   :linenos:

    if (req.url ~ "^/dev/__test_503($|[?])") {
        set req.backend_hint = broken_test;
        return (pass);
    }

Keep this permanently:

.. code-block:: python
   :linenos:

    sub vcl_backend_error {
        ...
    }

That is the actual custom 503 page used when the real backend on 127.0.0.1:8000 is unavailable.