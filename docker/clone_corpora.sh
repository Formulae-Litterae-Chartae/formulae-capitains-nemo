#!/bin/sh
set -eu

if [ -z "${FORMULAE_CORPORA_REPO_URL:-}" ]; then
  echo "FORMULAE_CORPORA_REPO_URL is not set"
  exit 1
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "GITHUB_TOKEN is not set"
  exit 1
fi

if [ -z "${ELASTICSEARCH_URL:-}" ]; then
  echo "ELASTICSEARCH_URL is not set"
  exit 1
fi

case "$FORMULAE_CORPORA_REPO_URL" in
  https://github.com/*)
    authrepo=$(printf "%s" "$FORMULAE_CORPORA_REPO_URL" | sed "s#https://#https://x-access-token:${GITHUB_TOKEN}@#")
    ;;
  *)
    echo "Please use an https://github.com/... URL for FORMULAE_CORPORA_REPO_URL"
    exit 1
    ;;
esac

if [ -d /data/.git ]; then
  echo "Updating existing XML DB repository..."
  cd /data
  git remote set-url origin "$authrepo"
  git fetch --depth 1 origin

  if [ -n "${FORMULAE_CORPORA_REF:-}" ]; then
    git checkout "$FORMULAE_CORPORA_REF"
    git reset --hard "$FORMULAE_CORPORA_REF"
  else
    branch="$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's#^origin/##')"
    git checkout "$branch"
    git reset --hard "origin/$branch"
  fi

  echo "Update done."
else
  if [ -n "$(ls -A /data 2>/dev/null)" ]; then
    echo "/data is not empty but is not a git repository"
    exit 1
  fi

  echo "Cloning XML DB into volume..."
  git clone --depth 1 "$authrepo" /data

  if [ -n "${FORMULAE_CORPORA_REF:-}" ]; then
    cd /data
    git fetch --depth 1 origin "$FORMULAE_CORPORA_REF"
    git checkout "$FORMULAE_CORPORA_REF"
  fi

  echo "Clone done."
fi

if [ "${REBUILD_ELASTICSEARCH:-false}" = "true" ]; then
  echo "Rebuilding Elasticsearch index at ${ELASTICSEARCH_URL}..."
  python3 /data/rebuild_elasticsearch_from_xml.py "${ELASTICSEARCH_URL}"
  echo "Elasticsearch rebuild done."
else
  echo "REBUILD_ELASTICSEARCH is not true; skipping index rebuild."
fi

echo "Done."