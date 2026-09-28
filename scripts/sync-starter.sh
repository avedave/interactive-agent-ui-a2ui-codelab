#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTHOR_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STARTER_DIR="$(cd "${AUTHOR_DIR}/../smart-home-a2ui-starter" && pwd)"

echo "==> Syncing runtime assets from authoring repo to starter repo..."
echo "    Source: ${AUTHOR_DIR}"
echo "    Target: ${STARTER_DIR}"

mkdir -p "${STARTER_DIR}/static"

# Synchronize boilerplate & runtime files
cp -v "${AUTHOR_DIR}/sensors.py" "${STARTER_DIR}/"
cp -v "${AUTHOR_DIR}/requirements.txt" "${STARTER_DIR}/"
cp -v "${AUTHOR_DIR}/Dockerfile" "${STARTER_DIR}/"
cp -v "${AUTHOR_DIR}/.gitignore" "${STARTER_DIR}/"

cp -v "${AUTHOR_DIR}/static/index.html" "${STARTER_DIR}/static/"
cp -v "${AUTHOR_DIR}/static/styles.css" "${STARTER_DIR}/static/"
cp -v "${AUTHOR_DIR}/static/a2ui-bridge.js" "${STARTER_DIR}/static/"

echo "==> Sync complete!"
(
  cd "${STARTER_DIR}"
  git status --short
)
