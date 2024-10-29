# <p align=center>formulae-capitains-nemo</p>
[![Coverage Status](https://coveralls.io/repos/github/Formulae-Litterae-Chartae/formulae-capitains-nemo/badge.svg?branch=master)](https://coveralls.io/github/Formulae-Litterae-Chartae/formulae-capitains-nemo?branch=master)

This is the class extension "NemoFormulae" for [flask_nemo](https://github.com/Capitains/flask-capitains-nemo).

A working instance of this extension for the Formulae - Litterae - Chartae Project can be found at https://werkstatt.formulae.uni-hamburg.de.


## Getting Started
Further information:
- https://github.com/capitains/tutorial-nemo
- The app is configured via [formulae/app.py](./formulae/app.py)

## Runnning the app locally:
1. Clone the repositories:
    1. formulae-capitains-nemo (code-base) 
    2. formulae-corpora (texts) (ideally in the same folder e.g., `git` as the code base)
2. Setup the environment:
    1. Create a Python virtualenv (e.g., `virtualenv --python=python3 ~/envs`), 
    2. activate the virtualenv (e.g., `source ~/envs/bin/activate`) 
    3. install the requirements via `pip install -r requirements.txt` within in the venv and from the `formulae-capitains-nemo` folder 
3. If the requirements have been installed properly, you can launch `python app.py` within the env and in `formulae-capitains-nemo` folder 
4. Reach the site via [127.0.0.1:5000](127.0.0.1:5000)
5. Only if needed: Set the environment variable `CORPUS_FOLDERS` and re-start the app.

### How are static files handled?
https://flask.palletsprojects.com/en/2.3.x/quickstart/#static-files

## How to run the SPHINX-docs locally:
1. Install sphinx: https://www.sphinx-doc.org/en/master/usage/installation.html
    - For Debin/Ubuntu the [OS-specific package manager](https://www.sphinx-doc.org/en/master/usage/installation.html#os-specific-package-manager) worked best
2. Build the project: `sphinx-build -M html docs/source/ docs/build/`
3. Open `docs/build/html/index.html` with your preferred browser: `firefox docs/build/html/index.html`