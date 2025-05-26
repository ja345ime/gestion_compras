#!/usr/bin/env bash
set -e
branch=${1:-master}

if [ -z "$GITHUB_TOKEN" ]; then
  echo "GITHUB_TOKEN no configurado"
  exit 1
fi

remote=$(git config --get remote.origin.url)
remote_auth=${remote/https:\/\//https://$GITHUB_TOKEN@}

git push "$remote_auth" "$branch"
