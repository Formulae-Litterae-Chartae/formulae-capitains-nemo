Traffic management
====================
We have had a situation, where the access times of our application where increased so much, that it became almost unusable for real users. To find the reason behind this behavior, we checked the access logs we saw a huge number of accesses to our website by bots. Since, the functionality of this application makes possible to compare multiple resources by joining them into one url with one or more '+', there is huge number of possible links (for :math:`n` resources they are :math:`n^k`, where k is number '+'+1).

Varnish 
#####################
|varnish| Varnish Cache is a...


.. |varnish| image:: https://www.varnish-software.com/media/xs4hjt04/vs-logo-2020-140x60-1.svg
  :width: 50
  :alt: Alternative text


Before making any changes, please check the syntax of the file via :code:`varnishd -C -f /etc/varnish/default.vcl` (see this `blog post <https://cloudkul.com/knowledgebase/check-varnish-syntax>`_ ). 

After changes: `service varnish reload`.  (https://stackoverflow.com/a/46088507/7924573). This is the current varnish solutions, which blocks are access from entities, who identify themselves as bots:





.. code-block:: python
   :linenos:
   :caption: Current version of default.vcl


    #
    # This is an example VCL file for Varnish.
    #
    # It does not do anything by default, delegating control to the
    # builtin VCL. The builtin VCL is called when there is no explicit
    # return statement.
    #
    # See the VCL chapters in the Users Guide at https://www.varnish-cache.org/docs/
    # and https://www.varnish-cache.org/trac/wiki/VCLExamples for more examples.

    # Marker to tell the VCL compiler that this VCL has been adapted to the
    # new 4.0 format.
    vcl 4.0;

    # Default backend definition. This points to the gunicorn server.
    backend default {
        .host = "127.0.0.1";
        .port = "8000";
    }

    sub vcl_recv {
        # Happens before we check if we have this in cache already.
        #
        # Typically you clean up the request here, removing cookies you don't need,
        # rewriting the request, etc.

        # remove the Matomo tracking cookie
        if (req.url ~ "urn:cts:formulae:pancarte_noir_internal") {
            return (synth(404, "Denied by request filtering configuration"));
        }
        if (req.http.user-agent ~ "Bot") {
            if (req.url ~ "\+" || req.url ~ "%2B") {
                return (synth(404, "Denied by request filtering configuration"));
            }
            return (pass);
        }
        if (req.http.user-agent ~ "bot") {
            if (req.url ~ "\+" || req.url ~ "%2B") {
                return (synth(404, "Denied by request filtering configuration"));
            }
            return (pass);
        }
        if (req.http.user-agent ~ "Bytespider") {
            if (req.url ~ "\+" || req.url ~ "%2B") {
                return (synth(404, "Denied by request filtering configuration"));
            }
            return (pass);
        }
        if (req.http.referer ~ "google") {
            if (req.url ~ "\+" || req.url ~ "%2B") {
                return (synth(404, "Denied by request filtering configuration"));
            }
            return (pass);
        }
        if (req.url ~ "/texts/") {
            #if (req.url ~ "\+.*\+.*") {
            #    return (synth(404, "Denied by request filtering configuration"));
            #}
            return (pass);
        }
        set req.http.Cookie = regsuball(req.http.Cookie, "(^|;\s*)(_[_a-z0-9\.]+)=[^;]*", "");
        set req.http.Cookie = regsub(req.http.Cookie, "^;\s*", "");
        # save the cookies before the built-in vcl_recv (allows caching of pages with cookies)
        set req.http.Cookie-Backup = req.http.Cookie;
        unset req.http.Cookie;
        # To deal with the Authorization header I should probably do the same thing I did with the Cookie header above
        # I.e., put is in an Authorization-Backup header, then restore this to the Authorization header in vcl_hash
        # I will then need to get the backend to send a Vary header that says the response should be varied according to Authorization
        # See https://stackoverflow.com/questions/35119283/best-pratice-for-varnish-cache-content-with-authorization-header for some guidance
    }

    sub vcl_backend_response {
        # Happens after we have read the response headers from the backend.
        #
        # Here you clean the response headers, removing silly Set-Cookie headers
        # and other mistakes your backend does.

        # I think I should move the Set-Cookie header into a temporary header and then reset it again in vcl_deliver
        #set beresp.http.Set-Cookie-Backup = beresp.http.Set-Cookie;
        #unset beresp.http.Set-Cookie;
    }

    sub vcl_deliver {
        # Happens when we have all the pieces we need, and are about to send the
        # response to the client.
        #
        # You can do accounting or modifying the final object here.
        
        # Reset the Set-Cookie header
        #set resp.http.Set-Cookie = resp.http.Set-Cookie-Backup;
        #unset resp.http.Set-Cookie-Backup;
    }

    sub vcl_hash {
        if (req.http.Cookie-Backup) {
            # restore the cookies before the lookup if any. This should allow auth cookies to affect results
            # may need to add an HTTP Vary header on the backend to send either project or non-project pages
            set req.http.Cookie = req.http.Cookie-Backup;
            unset req.http.Cookie-Backup;
        }
    }



Restricting parallel resources
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"Varnish will, in the default configuration, not cache an object coming from the backend with a ‘Set-Cookie’ header present. Also, if the client sends a Cookie header, Varnish will bypass the cache and go directly to the backend." We therefore decided to remove some cookies:

Cache Control with max-age 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"The 'Cache-Control' header instructs caches how to handle the content. Varnish cares about the max-age parameter and uses it to calculate the TTL for an object." - `cache-control  <https://vinyl-cache.org/docs/trunk/users-guide/increasing-your-hitrate.html#cache-control>`_. We therefore added a default max-age value in the config:    


.. literalinclude:: ../../config.py
   :linenos:
   :lineno-start: 40
   :lines: 40
   :caption: config.py

This value is later used in the application to construct the header:

.. literalinclude:: ../../formulae/nemo.py
   :pyobject: NemoFormulae.after_request

Previously we had :code:`if re.search('/(lang|auth|texts)/', request.url): response.cache_control.no_cache = True`, which never caches our resources. Since we never refresh a resource more than daily in production this limit, this does not seem to be practical. I removed this clause and have now everything but the assets fall under the previously mentioned max-age. I don't see a problem in setting it to 24*60*60 seconds. The assets could even be older,  I guess.


Rate limit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Planned:
- https://github.com/nand2/libvmod-throttle
- https://support.platform.sh/hc/en-us/community/posts/16439617864722-Rate-limit-connections-to-your-application-using-Varnish
- https://vinyl-cache.org/vmods/
- rate-limit is only in development-stage: 

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