Traffic Management
#####################
We have had a situation, where the access times of our application where increased so much, that it became almost unusable for real users. To find the reason behind this behavior, we checked the access logs we saw a huge number of accesses to our website by bots. Since, the functionality of this application makes possible to compare multiple resources by joining them into one url with one or more '+', there is huge number of possible links (for :math:`n` resources they are :math:`n^k`, where k is number '+'+1).

Varnish 
********************
|varnish| Varnish Cache is a...


.. |varnish| image:: https://www.varnish-software.com/media/xs4hjt04/vs-logo-2020-140x60-1.svg
  :width: 50
  :alt: Varnish Cache logo


Changing the config
======================

#. If possible: Make a backup of the complete (virtual) machine. 
#. Make a local backup of the varnish config: :code:`cp /etc/varnish/default.vcl /etc/varnish/default.vcl.bak`
#. Change the date in the varnish file.
#. Write your changes to the varnish file.
#. Before applying any changes, please check the syntax of the file via :code:`varnishd -C -f /etc/varnish/default.vcl` (see this `blog post <https://cloudkul.com/knowledgebase/check-varnish-syntax>`_ ). 
#. After the syntax check seems ok: Reload the config via :code:`service varnish reload`.  (https://stackoverflow.com/a/46088507/7924573). 
#. Finally: Make a digital copy by copying the file into this repository (see below). 

This is the current varnish solution, which blocks are access from entities, who identify themselves as bots:


.. literalinclude:: ../../varnish/default.vcl
   :language: vcl
   :linenos:
   :caption: varnish/default.vcl



Restricting parallel resources
======================
Our initial approach was to define a Varnish-rule, that basically blocked all url-accesses, with a '+' and return a `404`. This vastly stabilized the application and made it useful again.  But with Google's: `Note that returning "no availability" codes for more than a few days will cause Google to permanently slow or stop crawling URLs on your site, so follow the additional next steps` (source: `Handle overcrawling of your site (emergencies) <https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget#emergencies>`_) in mind, we should change this behavior in the future: 

.. code-block:: python
   :linenos:
   :caption: Snippet from the OLD default.vcl including the first and most restrictive filtering rule. 


   if (req.url ~ "/texts/") {
      if (req.url ~ "\+.*\+.*") {
         return (synth(404, "Denied by request filtering configuration"));
      }
      return (pass);
   }


Cookies 
======================
"Varnish will, in the default configuration, not cache an object coming from the backend with a ‘Set-Cookie’ header present. Also, if the client sends a Cookie header, Varnish will bypass the cache and go directly to the backend." We therefore decided to remove some cookies:

Cache Control with max-age 
======================
"The 'Cache-Control' header instructs caches how to handle the content. Varnish cares about the max-age parameter and uses it to calculate the TTL for an object." - `cache-control  <https://vinyl-cache.org/docs/trunk/users-guide/increasing-your-hitrate.html#cache-control>`_. We therefore added a default max-age value in the config via `CACHE_MAX_AGE`:    


.. literalinclude:: ../../config.py
   :linenos:
   :lineno-start: 50
   :lines: 50
   :caption: config.py

This value is later used in the application to construct the header:

.. literalinclude:: ../../formulae/nemo.py
   :pyobject: NemoFormulae.after_request

Previously we had :code:`if re.search('/(lang|auth|texts)/', request.url): response.cache_control.no_cache = True`, which never caches our resources. Since we never refresh a resource more than daily in production this limit, this does not seem to be practical. I removed this clause and have now everything but the assets fall under the previously mentioned max-age. I don't see a problem in setting it to 24*60*60 seconds. The assets could even be older,  I guess.


Rate limit
======================
Planned:
- https://github.com/nand2/libvmod-throttle
- https://support.platform.sh/hc/en-us/community/posts/16439617864722-Rate-limit-connections-to-your-application-using-Varnish
- https://vinyl-cache.org/vmods/
- rate-limit is only in development-stage: 



Adding a custom Error message for 503 errors:
==============================================


1. Back up your current VCL
----------------------------------------------
.. code-block:: shell

    sudo cp /etc/varnish/default.vcl /etc/varnish/default.vcl.backup


1. Add a temporary broken backend
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
        <p>Sorry, this website is temporarily unavailable.</p>
        <p>Please, consider using the instance operated by the Akademie der Wissenschaften Hamburg: <a href='https://formulae.awhamburg.de/'>formulae.awhamburg.de</a></p>
        <p>Please, visit the project website for more information: <a href='https://www.formulae.uni-hamburg.de/'>formulae.uni-hamburg.de</a></p>
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

robots.txt
#####################
We use a `robots.txt <../../assets/robots.txt>`_  file to disallow all bots to crawl sites containing a "+". To achieve this we used the robots.txt wildcard expression "*". It is not known whether all bots accept this form of wildcard annotation. 

If you intend to make changes to the robots.txt, consider checking it's functionality before hand via online tools such as the: `robots.txt Testing & Validation Tool <https://tamethebots.com/tools/robotstxt-checker>`_ 


.. literalinclude:: ../../assets/robots.txt
   :linenos:
   :caption: robots.txt

This reduce the accesses by over 50% within one day (10k-20k 404s per hour on 09.10.24 vs 300-6k 404s per hour on 10.10.24). The most prominent of the remaining crawlers on 10.10.24 are AcademicBotRTU and YandexBot, these remained until the 15.10.24, on which I added explicit rules to block them. Since, Google needs at most `24-36 hours <https://support.google.com/webmasters/thread/70176854/how-long-does-it-take-for-google-bot-to-take-into-effect-new-robots-txt-file?hl=en>`_  to check the new robots.txt, I expect other crawlers to have the same frequency. 

Why add :code:`crawl-delay`?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Well, Googlebot and Yandex wont use it. So, it wont cause any harm and is mostly just ignored. https://support.google.com/webmasters/thread/251817470/putting-crawl-delay-in-robots-txt-file-is-good?hl=en. But some do recognize it, so I have added the arbitrary limit of 30 seconds. Which is for instance recognize by the AcademicBotRTU.

Why add :code:`%2B`?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Because it is the  `Percent-encoding <https://en.wikipedia.org/wiki/Percent-encoding>`_ equivalent for '+'.


Which "good" bots frequently crawled our website?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table:: crawler-list
   :widths: 25 25 25
   :header-rows: 1
   
   * - name 
     - url
     - remarks
   * - AcademicBotRTU 
     - https://academicbot.rtu.lv/ 
     - academic
   * - YandexBot
     -  
     - search engine
   * - GoogleBot 
     - 
     - search engine
   * - BingBot 
     - 
     - search engine
   * - Baiduspider
     - https://www.baidu.com/search/robots_english.html
     - search engine   
   * - Nexus 5X Build/MMB29P
     - https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers?hl=de#googlebot-smartphone 
     - search engine
   * - CCBot
     - ???
     - ???   
   * - Nexus 5X Build/MMB29P
     - https://developers.facebook.com/docs/sharing/webmasters/web-crawlers
     - search engine
  
  


What if a crawler ignores `robots.txt`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
https://blog.archive.org/2017/04/17/robots-txt-meant-for-search-engines-dont-work-well-for-web-archives/

nginx
#####################


flask
#####################
In the previous section, the varnish-way of limiting access was introduced. In addition to that, there is a mechanism for controlling all access on the application side. Controlled by the `MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER` environment variable, which is then used by the `r_multipassager_multipassage`-method. So, if you have a risen number of 504 errors it could help to reduce this parameter. 

Per default it is set to 'dev', so authentication is not required. If you want to activate the authentication required-process, please set it to 'production':

1. Create or modify the `.env`-file in the root directory. 
   1. `cd formulae-capitains-nemo`
   2. `nano .env` 
   
2. With the following variables:
.. code-block:: python

  SERVER_TYPE = "production"
  MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER = 1 

3. Reload the application, in order for the variables to take effect 




.. literalinclude:: ../../config.py
   :linenos:
   :caption: Config.py
   :emphasize-lines: 44-49
   :pyobject: Config


.. literalinclude:: ../../formulae/nemo.py
   :linenos:
   :caption: r_multipassage()
   :emphasize-lines: 9-14
   :pyobject: NemoFormulae.r_multipassage