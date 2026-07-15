#!/usr/bin/env bash
# Seed the local OpenProject with data the integration tests rely on.
set -euo pipefail
SERVICE="${OP_SERVICE:-openproject}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker compose exec -T "$SERVICE" bundle exec rails runner - < "$HERE/seed_test_data.rb" \
  | grep -E '^SEED_OK'
