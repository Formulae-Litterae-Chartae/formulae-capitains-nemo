[![Coverage Status](https://coveralls.io/repos/github/Formulae-Litterae-Chartae/formulae-capitains-nemo/badge.svg?branch=master)](https://coveralls.io/github/Formulae-Litterae-Chartae/formulae-capitains-nemo?branch=master)

# formulae-capitains-nemo
This is the class extension "NemoFormulae" for flask_nemo (https://github.com/Capitains/flask-capitains-nemo).

A working instance of this extension for the Formulae - Litterae - Chartae Project can be found at https://werkstatt.formulae.uni-hamburg.de.


## Getting Started
Further information:
- https://github.com/capitains/tutorial-nemo


## How to run the SPHINX-docs locally:
1. Install sphinx: https://www.sphinx-doc.org/en/master/usage/installation.html
    - For Debin/Ubuntu the [OS-specific package manager](https://www.sphinx-doc.org/en/master/usage/installation.html#os-specific-package-manager) worked best
2. Build the project: `sphinx-build -M html docs/source/ docs/build/sphinx-build -M html docs/source/ docs/build/`
3. Open `docs/build/html/index.html` with your preferred browser: `firefox docs/build/html/index.htm`