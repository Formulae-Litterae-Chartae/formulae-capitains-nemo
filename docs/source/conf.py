# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# https://biapol.github.io/blog/johannes_mueller/entry_sphinx/Readme.html
import os
import sys
sys.path.append(os.path.abspath('../../'))
print('Sphinx runs with the following prefix:'+sys.prefix)



# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'formulae-capitains-nemo'
copyright = '2024, Matthew Munson, Thorben Schomacker'
author = 'Matthew Munson, Thorben Schomacker'
release = '1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['myst_parser',
              'sphinx_rtd_theme', 
              'sphinx.ext.autodoc',
              'sphinx.ext.autosummary']

intersphinx_mapping = {'flask': ('https://docs.python.org/3', None)}

templates_path = ['_templates']
exclude_patterns = []




# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_static_path = ['_static']
html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'style_nav_header_background': '#212529'
}
html_logo = '../../assets/images/logo_226x113.png'