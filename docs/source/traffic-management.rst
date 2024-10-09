Traffic management
====================

1st layer of traffic management
#####################
We use a robots.txt file, we should disallow all bots to crawl sites with a "+". To achieve this we used Google robots.txt wildcard expression "*". It is not known whether all bots accept this form of wildcard annotation. 

If you intend to make changes to the robots.txt, consider checking it's functionality before hand via online tools such as the: `robots.txt Validator and Testing Tool <https://technicalseo.com/tools/robots-txt/>`_

.. literalinclude:: ../../assets/robots.txt
   :caption: robots.txt
