Traffic management
====================
We have had a situation, where the access times of our application where increased so much, that it became almost unusable for real users. To find the reason behind this behavior, we checked the access logs we saw a huge number of accesses to our website by bots. Since, the functionality of this application makes possible to compare multiple resources by joining them into one url with one or more '+', there is huge number of possible links (for :math:`n` resources they are :math:`n^k`, where k is number '+'+1).

Varnish |varnish|
#####################
Varnish Cache is a...


.. |varnish| image:: https://www.varnish-software.com/media/xs4hjt04/vs-logo-2020-140x60-1.svg
  :width: 50
  :alt: Alternative text

Let all '+' lead to 404
~~~~~~~~~~

Our initial approach was to define a Varnish-rule, that basically blocked all url-accesses, with a '+' and return a `404`. This vastly stabilized the application and made it useful again.  But with Google's: `Note that returning "no availability" codes for more than a few days will cause Google to permanently slow or stop crawling URLs on your site, so follow the additional next steps` (source: `Handle overcrawling of your site (emergencies) <https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget#emergencies>`_) in mind, we should change this behavior in the future:

	

.. code-block:: python
   :linenos:
   :caption: snippet from default.vcl


   if (req.url ~ "/texts/") {
      if (req.url ~ "\+.*\+.*") {
         return (synth(404, "Denied by request filtering configuration"));
      }
      return (pass);
   }

The next step is to comment-out this rule and switch to a request limit approach as seen in https://support.platform.sh/hc/en-us/community/posts/16439617864722-Rate-limit-connections-to-your-application-using-Varnish.


robots.txt
#####################
We use a `robots.txt <../../assets/robots.txt>`_  file to disallow all bots to crawl sites containing a "+". To achieve this we used the robots.txt wildcard expression "*". It is not known whether all bots accept this form of wildcard annotation. 

If you intend to make changes to the robots.txt, consider checking it's functionality before hand via online tools such as the: `robots.txt Testing & Validation Tool <https://tamethebots.com/tools/robotstxt-checker>`_ 


.. literalinclude:: ../../assets/robots.txt
   :linenos:
   :caption: robots.txt

This reduce the accesses by over 50% within one day (10k-20k 404s per hour on 09.10.24 vs 300-6k 404s per hour on 10.10.24). The most prominent of the remaining crawlers on 10.10.24 are AcademicBotRTU and YandexBot, these remained until the 15.10.24, on which I added explicit rules to block them. Since, Google needs at most `24-36 hours <https://support.google.com/webmasters/thread/70176854/how-long-does-it-take-for-google-bot-to-take-into-effect-new-robots-txt-file?hl=en>`_  to check the new robots.txt, I expect other crawlers to have the same frequency. 

Why not add :code:`crawl-delay`?
~~~~~~~~~~
Well, Googlebot and Yandex wont use it. So, it wont cause any harm and is mostly just ignored. https://support.google.com/webmasters/thread/251817470/putting-crawl-delay-in-robots-txt-file-is-good?hl=en


Which bots frequently crawled our website?
~~~~~~~~~~

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

What if a crawler ignores `robots.txt`
~~~~~~~~~~
https://blog.archive.org/2017/04/17/robots-txt-meant-for-search-engines-dont-work-well-for-web-archives/

nginx
#####################
