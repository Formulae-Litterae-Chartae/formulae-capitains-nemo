#!/bin/sh
set -eu

if [ -d /data/.git ] || [ -n "$(ls -A /data 2>/dev/null)" ]; then
  echo "XML DB volume already populated; skipping clone."
  exit 0
fi

if [ -z "${FORMULAE_CORPORA_REPO_URL:-}" ]; then
  echo "FORMULAE_CORPORA_REPO_URL is not set"
  exit 1
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "GITHUB_TOKEN is not set"
  exit 1
fi

echo "Cloning XML DB into volume..."

case "$FORMULAE_CORPORA_REPO_URL" in
  https://github.com/*)
    authrepo=$(printf "%s" "$FORMULAE_CORPORA_REPO_URL" | sed "s#https://#https://x-access-token:${GITHUB_TOKEN}@#")
    ;;
  *)
    echo "Please use an https://github.com/... URL for FORMULAE_CORPORA_REPO_URL"
    exit 1
    ;;
esac

git clone --depth 1 "$authrepo" /data

if [ -n "${FORMULAE_CORPORA_REF:-}" ]; then
  cd /data
  git fetch --depth 1 origin "$FORMULAE_CORPORA_REF"
  git checkout "$FORMULAE_CORPORA_REF"
fi

echo "Done."