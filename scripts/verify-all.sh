#!/usr/bin/env bash
#
# One-command verification for SecureDoc AI.
#
#   ./scripts/verify-all.sh
#
# Runs every check that does not need the Docker daemon, then runs the full
# runtime smoke test when Docker is available. Exit code is non-zero if any
# required check fails.
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0
SKIP=0

green() { printf '\033[32m%s\033[0m' "$1"; }
red() { printf '\033[31m%s\033[0m' "$1"; }
yellow() { printf '\033[33m%s\033[0m' "$1"; }

step() { printf '\n== %s\n' "$1"; }
ok() { printf '  %s %s\n' "$(green ok)" "$1"; PASS=$((PASS + 1)); }
bad() { printf '  %s %s\n' "$(red FAIL)" "$1"; FAIL=$((FAIL + 1)); }
skip() { printf '  %s %s\n' "$(yellow skip)" "$1"; SKIP=$((SKIP + 1)); }

run() {
  # run <label> <command...>
  local label="$1"; shift
  if "$@"; then ok "$label"; else bad "$label"; fi
}

docker_ready() { docker info >/dev/null 2>&1; }

# ---------------------------------------------------------------- backend ----
step "Backend tests (pytest)"
if [ -x backend/.venv/bin/python ]; then
  run "pytest" bash -c 'cd backend && ./.venv/bin/python -m pytest -q'
else
  skip "backend/.venv missing — run: make backend-install"
fi

# ----------------------------------------------------------- java tests -----
step "Java validator tests (maven)"
if command -v mvn >/dev/null 2>&1; then
  run "mvn test" bash -c 'cd java-validator && mvn -B -q test'
else
  skip "maven not on PATH"
fi

# -------------------------------------------------------- frontend build ----
step "Frontend type-check + build"
if command -v npm >/dev/null 2>&1 && [ -d frontend/node_modules ]; then
  run "npm run build" bash -c 'cd frontend && npm run build'
else
  skip "frontend/node_modules missing — run: make frontend-install"
fi

# --------------------------------------------- no API key in the bundle -----
step "Frontend must not contain the API key"
if grep -rIl -e 'VITE_API_KEY' -e 'X-API-Key' \
     frontend/src frontend/.env* frontend/vite.config.ts 2>/dev/null; then
  bad "API-key markers found in frontend source/config"
else
  ok "no API-key markers in frontend source/config"
fi
if [ -d frontend/dist ]; then
  if grep -rIl -e 'VITE_API_KEY' -e 'X-API-Key' frontend/dist 2>/dev/null; then
    bad "built bundle contains API-key markers"
  else
    ok "built bundle contains no API-key markers"
  fi
  if [ -n "${SECUREDOC_API_KEY:-}" ] && grep -rIq -- "${SECUREDOC_API_KEY}" frontend/dist; then
    bad "built bundle leaks the SECUREDOC_API_KEY value"
  else
    ok "built bundle does not contain the SECUREDOC_API_KEY value"
  fi
else
  skip "frontend/dist missing — build the frontend first"
fi

# ----------------------------------------------------- compose config -------
step "Docker Compose configuration"
if command -v docker >/dev/null 2>&1; then
  run "docker compose config" bash -c \
    'TOKEN_VAULT_KEY=x SECUREDOC_API_KEY=y docker compose config --quiet'
else
  skip "docker CLI not found"
fi

# ------------------------------------------------------- runtime smoke ------
step "Docker runtime smoke test"
if docker_ready; then
  echo "  Docker daemon detected — building and starting the stack..."
  if TOKEN_VAULT_KEY="$(openssl rand -base64 32)" \
     SECUREDOC_API_KEY="$(openssl rand -hex 32)" \
     docker compose up --build -d; then
    # Wait for the backend healthcheck to go green.
    for _ in $(seq 1 60); do
      if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then break; fi
      sleep 2
    done
    API_KEY="$(docker compose exec -T backend printenv SECUREDOC_API_KEY 2>/dev/null || true)"
    run "backend /health" bash -c 'curl -fsS http://127.0.0.1:8000/health | grep -q status'
    run "java-validator /health" bash -c 'curl -fsS http://127.0.0.1:8080/health >/dev/null'
    run "frontend /" bash -c 'curl -fsS http://127.0.0.1:3000/ >/dev/null'
    run "smoke test" bash -c "SECUREDOC_API_KEY='${API_KEY}' BASE_URL=http://127.0.0.1:8000 ./scripts/smoke-test.sh"
    docker compose down >/dev/null 2>&1 || true
  else
    bad "docker compose up"
  fi
else
  skip "Docker daemon unavailable — runtime verification NOT performed"
fi

# ------------------------------------------------------------- summary ------
printf '\n---------------------------------------------\n'
printf 'passed: %s   failed: %s   skipped: %s\n' "$PASS" "$FAIL" "$SKIP"
if [ "$SKIP" -gt 0 ]; then
  printf '%s\n' "Skipped checks are unverified in this environment (see docs/verification.md)."
fi
[ "$FAIL" -eq 0 ] || exit 1
echo "All available checks passed."
