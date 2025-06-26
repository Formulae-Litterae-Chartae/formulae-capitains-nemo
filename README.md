


# <p align=center> <img align=center src="https://avatars.githubusercontent.com/u/41728302"> <br> formulae-capitains-nemo</p>

[![Coverage Status](https://coveralls.io/repos/github/Formulae-Litterae-Chartae/formulae-capitains-nemo/badge.svg?branch=master)](https://coveralls.io/github/Formulae-Litterae-Chartae/formulae-capitains-nemo?branch=master)

This is the class extension "NemoFormulae" for [flask_nemo](https://github.com/Capitains/flask-capitains-nemo). A working instance of this extension for the Formulae - Litterae - Chartae Project can be found at https://werkstatt.formulae.uni-hamburg.de.

## Getting Started
Further information:
- https://github.com/capitains/tutorial-nemo
- The app is configured via [formulae/app.py](./formulae/app.py)

## Runnning the app locally:

### 1. Preliminary setup steps:
Only need to be executed the **before the first time** running the app:
1. Clone the repositories:
    1. `git clone formulae-capitains-nemo` (code-base) 
    2. `git clone formulae-corpora` (texts) (ideally in the same folder e.g., `git` as the code base)
2. Create a Python virtualenv (e.g., `virtualenv --python=python3 .venv`)
3. Only if needed: Set the environment variable `CORPUS_FOLDERS` and re-start the app.

### 2. Start the app:    
1. activate the virtualenv (e.g., `source .venv/bin/activate`) 
2. install the requirements via `pip install -r requirements.txt` within in the venv and from the `formulae-capitains-nemo` folder 
3. Optional: set-up Elastic Search via: `.env`
  1. For local development: `ELASTICSEARCH_URL = "http://localhost:9200"` -> requires: [local es instance](#run-elastic-search-local)
3. If the requirements have been installed properly, you can launch `python3 app.py` within the env and in `formulae-capitains-nemo` folder 
4. Reach the site via [127.0.0.1:5000](http://127.0.0.1:5000)

### Run Elastic Search local
1. Make sure that you have a few Gigabytes of RAM free
2. cd `formulae-capitains-nemo` folder
3. `docker-compose up` 
4.  es8 exited with code 137 -> Not enough memory free


### How are static files handled?
1. https://flask.palletsprojects.com/en/2.3.x/quickstart/#static-files
2. I do recommend to add `/static` and `/robots.txt` to your nginx configuration, so that are served directly without passing through the application. 

## How to run the SPHINX documentation locally:
1. Install sphinx: https://www.sphinx-doc.org/en/master/usage/installation.html
    - For Debin/Ubuntu the [OS-specific package manager](https://www.sphinx-doc.org/en/master/usage/installation.html#os-specific-package-manager) worked best
2. Build the project: `sphinx-build -M html docs/source/ docs/build/`
3. Open `docs/build/html/index.html` with your preferred browser: `firefox docs/build/html/index.html`

## Contribution guide
- Currently, we do not follow any specific design pattern. In the future I would to "reduce the weight" of our fat controller [formulae/app.py](./formulae/app.py). I have not fully decided on whether I want to have [fat models](https://www.tonymarston.net/php-mysql/fat-model-skinny-controller.html) or fat services instead; at the end services vs. models is more a naming thing than a real decision. Alternatively, I could do the [MVC-pattern](https://www.reddit.com/r/flask/comments/134j8qw/how_can_we_use_the_mvc_pattern_in_flask/). 
- Each new collection should 

## Run GitHub-actions locally:
1. Install [GitHub CLI](https://cli.github.com/)
2. Install [act](https://nektosact.com/installation/gh.html): `gh extension install https://github.com/nektos/gh-act`
3. cd git/formulae-capitains-nemo
3. `gh act -W '.github/workflows/python-app.yml'`
4. Comment out the redis port (gh seems to bring its own redis instance)