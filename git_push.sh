#!/usr/bin/env bash
set -e

log_error() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> app.log
}

# Cargar variables de entorno
if [ -f .env ]; then
  source .env
fi

commit_message="$1"
branch="master"

if [ -z "$GITHUB_TOKEN" ]; then
  log_error "GITHUB_TOKEN no configurado"
  echo "❌ Push fallido - token no configurado"
  exit 1
fi

remote="$(git config --get remote.origin.url)"
remote_auth=${remote/https:\/\//https://$GITHUB_TOKEN@}
git remote set-url origin "$remote_auth"
trap 'git remote set-url origin "$remote"' EXIT

git add -A
if ! git diff --cached --quiet; then
  git commit -m "$commit_message"
fi

if git push origin "$branch"; then
  echo "✅ Push completado con éxito"
else
  log_error "Push fallido"
  echo "❌ Push fallido"
  exit 1
fi
