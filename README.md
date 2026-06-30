


# <p align=center> <img align=center src="https://avatars.githubusercontent.com/u/41728302"> <br> formulae-capitains-nemo</p>

[![Coverage Status](https://coveralls.io/repos/github/Formulae-Litterae-Chartae/formulae-capitains-nemo/badge.svg?branch=master)](https://coveralls.io/github/Formulae-Litterae-Chartae/formulae-capitains-nemo?branch=master)

This is the class extension "NemoFormulae" for [flask_nemo](https://github.com/Capitains/flask-capitains-nemo). A working instance of this extension for the Formulae - Litterae - Chartae Project can be found at https://werkstatt.formulae.uni-hamburg.de. 

## Table of content:
- [Release notes](#release-notes)


## Release notes
| Version | Note | Migration needed? |
| ---| --- | --- |
| [v1.2](https://github.com/Formulae-Litterae-Chartae/formulae-capitains-nemo/releases/tag/v1.2) | [Release Note for v1.2](#v1.2) | [migrations/v1-2-admin-users](https://formulae-litterae-chartae.github.io/formulae-capitains-nemo/migrations/v1-2-admin-users.html)


### Version 1.2.0 <a name="v1.2"></a>
Version 1.2.0 introduces graphical user account administration with Flask-Admin.

Main changes:
* added a new ``User.is_admin`` field;
* added a Flask-Admin interface for user administration;
* separated project-team access from administrative access:
  * ``project_team`` controls access to project-internal application content;
  * ``is_admin`` controls access to the administration interface;
* added an Administration link to the user account dropdown;
* added production and development configuration options for the admin URL.

This release requires a database migration. Existing users are not promoted automatically. After the migration, all existing users have ``is_admin = 0``.
One administrator account must be promoted manually.

See :doc:`migrations/v1-2-admin-users` for the full migration procedure.

## Getting Started
Further information:
- https://github.com/capitains/tutorial-nemo
- The app is configured via [formulae/app.py](./formulae/app.py)
- Complete documentation should be done using Sphinx

## Running the app locally :computer::

### 1. Preliminary setup steps:
Only needs to be executed **before the first time** running the app:
1. Clone the repositories:
    1. `git clone formulae-capitains-nemo` (code-base) 
    2. `git clone formulae-corpora` (texts) (ideally in the same folder e.g., `git` as the code base)
2. Create a Python virtualenv (e.g., `virtualenv --python=python3 .venv`)
3. Only if needed: Set the environment variable `CORPUS_FOLDERS` and re-start the app.

### 2. Start the app:    
1. activate the virtualenv (e.g., `source .venv/bin/activate` or `source env/bin/activate`) 
2. install the requirements via `pip install -r requirements.txt` within in the venv and from the `formulae-capitains-nemo` folder 
3. *Optional*: set-up Elastic Search via: `.env`
  1. For local development: `ELASTICSEARCH_URL = "http://localhost:9200"` -> requires: [local elastic search instance](#run-elastic-search-local)
3. If the requirements have been installed properly, you can launch `python3 app.py` within the venv and in `formulae-capitains-nemo` folder 
4. Reach the site via [127.0.0.1:5000](http://127.0.0.1:5000)

### Run Elastic Search local
1. Make sure that you have a few Gigabytes of RAM free
2. cd `formulae-capitains-nemo` folder
3. `docker-compose up` 
-  `es8 exited with code 137` -> Not enough memory free

## Running with Docker Compose :whale2:
The application can be started locally using Docker Compose. The setup includes:
- **Elasticsearch** – search index backend
- **Redis** – temporary storage for search workflows
- **formulae_corpora** – helper container that clones/updates the XML corpus and can rebuild the search index
- **nemo** – the Flask web application
### Requirements
- Docker
- Docker Compose
### Environment variables
Create a `.docker-env` file in the project root:
```env
  ELASTICSEARCH_URL=http://elasticsearch:9200
  FORMULAE_CORPORA_REPO_URL=<repository>
  GITHUB_TOKEN=<github-token>
  FORMULAE_CORPORA_REF=
  REBUILD_ELASTICSEARCH=false
  ES_API_KEY=<api-key-for-elastic-search-leave-blank-for-anonymous-access>
```
### Startup sequence
```shell
  docker compose up -d elasticsearch redis
  docker compose run --rm formulae_corpora
  docker compose up -d nemo
```
:computer: Application URL: http://localhost:5000
### Stop
```shell
  docker compose down
```

### If you want to test changes to nemo:
```shell
docker-compose up --build --force-recreate nemo
```

### How are static files handled?
1. https://flask.palletsprojects.com/en/2.3.x/quickstart/#static-files
2. I do recommend to add `/static` and `/robots.txt` to your nginx configuration, so that are served directly without passing through the application. 

## How to run the SPHINX documentation locally:
1. Install sphinx: https://www.sphinx-doc.org/en/master/usage/installation.html
    - For Debin/Ubuntu the [OS-specific package manager](https://www.sphinx-doc.org/en/master/usage/installation.html#os-specific-package-manager) worked best
2. activate the virtualenv (e.g., `source .venv/bin/activate`) 
3. install the requirements via `pip install -r requirements_sphinx.txt` within in the venv and from the `formulae-capitains-nemo` folder 
3. Build the project: `sphinx-build -M html docs/source/ docs/build/` or `python -m sphinx -M html docs/source/ docs/build/`
4. Open `docs/build/html/index.html` with your preferred browser: `firefox docs/build/html/index.html`

## Contribution guide
- Currently, we do not follow any specific design pattern. In the future I would to "reduce the weight" of our fat controller [formulae/app.py](./formulae/app.py). I have not fully decided on whether I want to have [fat models](https://www.tonymarston.net/php-mysql/fat-model-skinny-controller.html) or fat services instead; at the end services vs. models is more a naming thing than a real decision. Alternatively, I could do the [MVC-pattern](https://www.reddit.com/r/flask/comments/134j8qw/how_can_we_use_the_mvc_pattern_in_flask/). 
- Each new collection should 

## Run GitHub-actions locally:
1. Install [GitHub CLI](https://cli.github.com/)
2. Install [act](https://nektosact.com/installation/gh.html): `gh extension install https://github.com/nektos/gh-act`
3. cd git/formulae-capitains-nemo
3. `gh act -W '.github/workflows/python-app.yml'` or `gh act -W '.github/workflows/documentation.yml'`
4. Comment out the redis port (gh seems to bring its own redis instance)

