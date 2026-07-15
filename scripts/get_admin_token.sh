#!/usr/bin/env bash
# Mint (or reset) a user's API token from the running container and print it.
# Idempotent-ish: it deletes any existing API token for the user and creates a
# fresh one (the plaintext value is only recoverable at creation).
#
# Usage:
#   ./scripts/get_admin_token.sh                 # admin -> prints APITOKEN=...
#   ./scripts/get_admin_token.sh jane.doe        # a specific login
#   eval "$(./scripts/get_admin_token.sh)"       # exports APITOKEN in your shell
set -euo pipefail

SERVICE="${OP_SERVICE:-openproject}"
LOGIN="${1:-admin}"

read -r -d '' RUBY <<RB || true
u = User.find_by(login: '${LOGIN}') || User.where(admin: true).order(:id).first
raise "no user '${LOGIN}' found" unless u
Token::API.where(user_id: u.id).delete_all
t = Token::API.create!(user: u)
val = (t.respond_to?(:plain_value) && t.plain_value.present?) ? t.plain_value : t.value.to_s
puts "APITOKEN=#{val}"
puts "APIUSER=#{u.login}"
RB

docker compose exec -T "$SERVICE" bundle exec rails runner - <<<"$RUBY" \
  | grep -E '^(APITOKEN|APIUSER)='
