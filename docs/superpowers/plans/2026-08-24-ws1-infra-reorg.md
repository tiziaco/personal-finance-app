# WS1 — Infrastructure Reorganisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move monitoring config out of the repo root into `infra/`, rename the dev compose file, and replace every product-specific *identifier* (`@rilevio/*`, `rilevio-network`, `rilevio-web`, `rilevio-server`) with a neutral identifier — the `@app` scope for workspace packages, `app-network` for the Docker network, and directory-matching names (`web-app`, `server`) for the two root packages — so the later B2C fork inherits the layout with no rename.

**Architecture:** Purely mechanical restructuring — no runtime behaviour changes. A static verification script (`scripts/verify-infra.sh`) is written first and asserts the target state; it fails against the current tree and passes once all tasks land. Each task is independently revertable and ends with the script plus a real stack boot.

**Tech Stack:** Docker Compose, GNU Make, pnpm workspaces, Prometheus, Grafana, cAdvisor, bash

**Spec:** `docs/superpowers/specs/2026-08-24-template-hardening-design.md` (WS1)

## Global Constraints

- Naming token is exactly `@app` for the pnpm workspace-package scope and `app-network` for the Docker network. Copied verbatim from spec constraint 2.
- The two ROOT packages are named after their directory, not the `@app` token: `web-app/package.json` is `web-app`, `server/pyproject.toml` is `server`. Both are private/unpublished, so the name is a local label. (Amended mid-execution — see Ruling 15.)
- Do not widen the role seam (spec constraint 1). WS1 touches no auth code; if a rename appears to require an auth edit, stop and escalate.
- Repo is at baseline commit `296c3b7` on `main`. Every task commits separately so any single task can be reverted alone.
- `.gitignore` files at root, `server/`, and `web-app/` are **verified correct and must not be modified**.
- Never `git add -A` blind — every commit stages explicit paths. Root `.env`, `server/.env.development`, and both `.env.local` files contain live Clerk secrets.
- Use `git mv` for all moves and renames so history follows the file.

---

## Out of Scope (deliberate — do not do these)

These contain the string `rilevio` but are **product content, not identifiers**. Renaming them is a rebrand, which is a separate decision:

| Location | Content |
|---|---|
| `web-app/apps/*/src/app/layout.tsx` | `title: "Rilevio"`, `title: "Rilevio \| Portale fornitore"`, description strings |
| `web-app/apps/*/src/app/(dashboard\|portal)/layout.tsx` | `logoAlt="Rilevio"` |
| `README.md`, `server/README.md`, `web-app/apps/*/README.md` | prose describing the Rilevio product |
| `server/app/models/enums.py:1` | docstring `"""Domain enumerations for the Rilevio application."""` |
| `web-app/packages/auth/src/permissions.ts:2` | comment `Role definitions and utilities for Rilevio RBAC.` |
| `server/README.md:31` | `POSTGRES_DB=rilevio` — renaming would orphan the existing `postgres-data` volume |

Also out of scope: `docs/superpowers/plans/2026-04-11-clerk-rbac.md` and `docs/superpowers/specs/2026-04-09-*.md` / `2026-04-11-*.md`. These are historical records of decisions made at the time. Rewriting them would falsify the record.

---

## File Map

### Created

| File | Responsibility |
|------|----------------|
| `scripts/verify-infra.sh` | Static assertions on repo layout and identifiers. No Docker daemon required beyond `docker compose config`. Reused by WS2 and WS4. |

### Moved (`git mv`)

| From | To |
|------|-----|
| `prometheus/prometheus.yml` | `infra/prometheus/prometheus.yml` |
| `grafana/datasources/datasource.yml` | `infra/grafana/datasources/datasource.yml` |
| `grafana/dashboards/dashboards.yml` | `infra/grafana/dashboards/dashboards.yml` |
| `grafana/dashboards/json/*.json` | `infra/grafana/dashboards/json/*.json` |
| `docker-compose.yml` | `docker-compose.dev.yml` |

### Modified

| File | Change |
|------|--------|
| `docker-compose.dev.yml` | volume paths → `./infra/…`; network `rilevio-network` → `app-network`; add `container_name` to `server`/`db` |
| `docker-compose.prod.yml` | network `app` → `app-network` |
| `Makefile` | add `COMPOSE_FILE`; pass `-f $(COMPOSE_FILE)` on every compose call; fix dead `personal-finance-app-*` image names in `clean` |
| `web-app/package.json` | `"name": "rilevio-web"` → `"web-app"` (matches its directory) |
| `web-app/packages/{ui,types,auth}/package.json` | `@rilevio/*` → `@app/*` (name + deps) |
| `web-app/apps/{internal,supplier}-portal/package.json` | name + 3 workspace deps |
| `web-app/apps/*/next.config.ts` | `transpilePackages` array |
| `web-app/apps/*/src/**/*.{ts,tsx}` | import specifiers |
| `web-app/apps/*/src/styles/globals.css` | `@import "@rilevio/ui/styles/globals.css"` |
| `server/pyproject.toml` | `name = "rilevio-server"` → `"server"` (matches its directory) |
| `CLAUDE.md`, `README.md`, `web-app/README.md`, `web-app/apps/*/README.md` | structure diagrams and identifier references only |

---

## Task 1: Verification script

**Files:**
- Create: `scripts/verify-infra.sh`

**Interfaces:**
- Produces: executable `scripts/verify-infra.sh`, exit 0 = all assertions pass, exit 1 = at least one failed. Each assertion prints `PASS: <desc>` or `FAIL: <desc>`. Later tasks run this as their test.

- [ ] **Step 1: Write the verification script**

```bash
mkdir -p scripts
cat > scripts/verify-infra.sh <<'EOF'
#!/usr/bin/env bash
# Static verification of the WS1 infrastructure layout.
# No Docker daemon required except for `docker compose config` (parse-only).
set -uo pipefail
cd "$(dirname "$0")/.."

fails=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; fails=$((fails+1)); }

check() { # check <description> <command...>
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc"; fi
}

# --- layout ---------------------------------------------------------------
check "infra/prometheus/prometheus.yml exists"          test -f infra/prometheus/prometheus.yml
check "infra/grafana/datasources/datasource.yml exists" test -f infra/grafana/datasources/datasource.yml
check "infra/grafana/dashboards/dashboards.yml exists"  test -f infra/grafana/dashboards/dashboards.yml
check "infra/grafana/dashboards/json/ is non-empty"     bash -c 'compgen -G "infra/grafana/dashboards/json/*.json" > /dev/null'
check "docker-compose.dev.yml exists"                   test -f docker-compose.dev.yml
check "old prometheus/ dir is gone"                     bash -c '! test -d prometheus'
check "old grafana/ dir is gone"                        bash -c '! test -d grafana'
check "old docker-compose.yml is gone"                  bash -c '! test -f docker-compose.yml'

# --- identifiers ----------------------------------------------------------
# Product/brand strings are deliberately out of scope; only identifiers are checked.
check "no @rilevio/ scope in web-app sources" \
  bash -c '! grep -rq "@rilevio/" web-app --include="*.ts" --include="*.tsx" --include="*.css" --include="package.json" --exclude-dir=node_modules --exclude-dir=.next'
check "no rilevio-network in compose files" \
  bash -c '! grep -rq "rilevio-network" docker-compose.dev.yml docker-compose.prod.yml'
check "no bare 'app' network in prod compose" \
  bash -c '! grep -qE "^\s+- app$" docker-compose.prod.yml'
check "app-network declared in dev compose"  grep -q "app-network:" docker-compose.dev.yml
check "app-network declared in prod compose" grep -q "app-network:" docker-compose.prod.yml
check "web-app package name is web-app"      grep -q '"name": "web-app"' web-app/package.json
check "server package name is server"        grep -q 'name = "server"' server/pyproject.toml

# --- makefile -------------------------------------------------------------
check "Makefile defines COMPOSE_FILE"        grep -q "COMPOSE_FILE" Makefile
check "no stale personal-finance-app images" bash -c '! grep -q "personal-finance-app" Makefile'

# --- compose validity (parse-only; needs docker CLI, not a running daemon) --
if command -v docker >/dev/null 2>&1; then
  check "docker-compose.dev.yml parses"  docker compose -f docker-compose.dev.yml config
else
  echo "SKIP: docker CLI not found — dev compose parse check skipped"
fi

# Prod compose cannot be validated with `docker compose config`: it points env_file at
# ./web-app/.env.local, which does not exist (prod compose is stale — it still models a
# single web-app service from before the two-portal split). Reshaping it is WS2's scope.
# Structural validation instead: every service network reference must resolve.
check "prod compose network refs all resolve" python3 -c "
import sys, yaml
d = yaml.safe_load(open('docker-compose.prod.yml'))
declared = set((d.get('networks') or {}).keys())
for name, svc in (d.get('services') or {}).items():
    for n in (svc.get('networks') or []):
        if n not in declared:
            print('unresolved network %r on service %r' % (n, name)); sys.exit(1)
sys.exit(0)
"

echo
if [ "$fails" -eq 0 ]; then
  echo "All infra checks passed."
else
  echo "$fails check(s) failed."
fi
exit $((fails > 0))
EOF
chmod +x scripts/verify-infra.sh
```

- [ ] **Step 2: Run it to confirm it fails against the current tree**

Run: `./scripts/verify-infra.sh`
Expected: exits 1. At minimum these FAIL — `infra/prometheus/prometheus.yml exists`, `docker-compose.dev.yml exists`, `old prometheus/ dir is gone`, `no @rilevio/ scope in web-app sources`, `Makefile defines COMPOSE_FILE`, `no stale personal-finance-app images`.

This failing output is the task list for Tasks 2–5. If a check passes that you expected to fail, stop — the tree is not at the assumed baseline.

- [ ] **Step 3: Commit**

```bash
git add scripts/verify-infra.sh
git commit -m "test(infra): add static verification script for WS1 layout

Asserts the target infra/ layout, compose file naming, network naming,
and absence of product-specific identifiers. Fails against current tree
by design; Tasks 2-5 turn it green."
```

---

## Task 2: Move monitoring config into `infra/`

**Files:**
- Move: `prometheus/` → `infra/prometheus/`
- Move: `grafana/` → `infra/grafana/`
- Modify: `docker-compose.yml` (volume paths only — the rename happens in Task 3)

**Interfaces:**
- Consumes: `scripts/verify-infra.sh` from Task 1.
- Produces: `infra/prometheus/prometheus.yml`, `infra/grafana/datasources/datasource.yml`, `infra/grafana/dashboards/dashboards.yml`, `infra/grafana/dashboards/json/*.json`. Task 3 relies on these paths already being correct inside the compose file.

- [ ] **Step 1: Move the directories**

```bash
mkdir -p infra
git mv prometheus infra/prometheus
git mv grafana infra/grafana
```

- [ ] **Step 2: Run verification to confirm the layout checks now pass but compose is broken**

Run: `./scripts/verify-infra.sh`
Expected: `infra/…` and `old …/ dir is gone` checks now PASS. `docker-compose.dev.yml exists` still FAILS (Task 3). Compose still parses — Compose does not validate that bind-mount source paths exist at config time, so this check passing does **not** mean the paths are right. Step 3 fixes them.

- [ ] **Step 3: Update the bind-mount paths in `docker-compose.yml`**

Three mounts reference the old locations. Replace them:

```yaml
  prometheus:
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
```

```yaml
  grafana:
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./infra/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./infra/grafana/datasources:/etc/grafana/provisioning/datasources
```

Note the `grafana` service previously had a **fourth** mount:
`./grafana/dashboards/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml`.
Delete it. It is fully subsumed by the directory mount on the line above — the directory already contains `dashboards.yml`, so the file mount was mounting the same content twice at the same path.

Apply with:

```bash
python3 - <<'PY'
p = "docker-compose.yml"
s = open(p).read()
s = s.replace("- ./prometheus/prometheus.yml:", "- ./infra/prometheus/prometheus.yml:")
s = s.replace("      - ./grafana/dashboards/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml\n", "")
s = s.replace("- ./grafana/dashboards:", "- ./infra/grafana/dashboards:")
s = s.replace("- ./grafana/datasources:", "- ./infra/grafana/datasources:")
open(p, "w").write(s)
PY
grep -n "infra/" docker-compose.yml
```

Expected output: exactly three lines, all under `prometheus:` and `grafana:`.

- [ ] **Step 4: Boot the monitoring stack and confirm provisioning still works**

These checks are deliberately password-free — they verify the **bind-mount paths**, which is exactly what this task changes, rather than Grafana's auth. Do not read `.env`.

```bash
docker compose up -d prometheus grafana
sleep 15

# Prometheus loaded its config from the new path
curl -sf http://localhost:9090/-/healthy && echo "prometheus healthy"
curl -sf http://localhost:9090/api/v1/status/config | grep -q "job_name" \
  && echo "prometheus config loaded" || echo "PROMETHEUS CONFIG MISSING"

# Grafana is up (this endpoint needs no auth)
curl -sf http://localhost:3001/api/health && echo "grafana healthy"

# The provisioning bind mounts actually landed inside the container
docker compose exec -T grafana ls /etc/grafana/provisioning/datasources/datasource.yml \
  && echo "datasource mount OK" || echo "DATASOURCE MOUNT MISSING"
docker compose exec -T grafana ls /etc/grafana/provisioning/dashboards/dashboards.yml \
  && echo "dashboards.yml mount OK" || echo "DASHBOARDS.YML MOUNT MISSING"
docker compose exec -T grafana sh -c 'ls /etc/grafana/provisioning/dashboards/json/*.json | wc -l' \
  | tr -d ' ' | grep -qx "3" && echo "3 dashboard JSONs mounted" || echo "DASHBOARD JSON COUNT WRONG"
```

Expected: `prometheus healthy`, `prometheus config loaded`, `grafana healthy`, `datasource mount OK`, `dashboards.yml mount OK`, `3 dashboard JSONs mounted`.

Any `MISSING`/`WRONG` line means a bind-mount path is wrong — fix it before proceeding. Do not continue on a partial pass.

- [ ] **Step 5: Tear down and commit**

```bash
docker compose down
git add docker-compose.yml infra/
git commit -m "refactor(infra): move prometheus and grafana config under infra/

Monitoring config no longer sits in the repo root next to application
code. Also drops a redundant grafana dashboards.yml bind mount that was
already covered by the parent directory mount."
```

---

## Task 3: Rename dev compose file and parameterise the Makefile

**Files:**
- Move: `docker-compose.yml` → `docker-compose.dev.yml`
- Modify: `Makefile`

**Interfaces:**
- Consumes: `infra/` paths from Task 2.
- Produces: Makefile variable `COMPOSE_FILE ?= docker-compose.dev.yml`, referenced as `-f $(COMPOSE_FILE)` in every compose invocation. Tasks 4 and WS2 extend the same variable.

- [ ] **Step 1: Rename the file**

```bash
git mv docker-compose.yml docker-compose.dev.yml
```

- [ ] **Step 2: Confirm every Make target is now broken**

Run: `make docker-stop`
Expected: failure — Compose cannot find a default `docker-compose.yml`/`compose.yaml`. This confirms the Makefile genuinely drives every command through the default filename and that Step 3 is necessary.

- [ ] **Step 3: Add `COMPOSE_FILE` and thread it through every compose call**

In `Makefile`, directly below the existing `DOCKER_COMPOSE ?= docker-compose` line, add:

```makefile
COMPOSE_FILE ?= docker-compose.dev.yml
```

Then replace every `$(DOCKER_COMPOSE)` invocation with `$(DOCKER_COMPOSE) -f $(COMPOSE_FILE)`. There are **ten** call sites (confirm with `grep -c '\$(DOCKER_COMPOSE) ' Makefile` before editing):

| Target | Line content after edit |
|---|---|
| `docker-build` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) build internal-portal supplier-portal server` |
| `docker-build-web` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) build internal-portal supplier-portal` |
| `docker-build-api` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) build server` |
| `docker-run` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d` |
| `docker-run-core` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d internal-portal supplier-portal server db` |
| `docker-run-db` | `APP_ENV=$(ENV) $(DOCKER_COMPOSE) -f $(COMPOSE_FILE) --env-file $$ENV_FILE up -d db` |
| `docker-stop` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down` |
| `docker-logs` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) logs -f` |
| `docker-logs-core` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) logs -f internal-portal supplier-portal server db` |
| `clean` | `@$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down -v` |

Apply mechanically:

```bash
python3 - <<'PY'
p = "Makefile"
s = open(p).read()
s = s.replace(
    "DOCKER_COMPOSE ?= docker-compose\n",
    "DOCKER_COMPOSE ?= docker-compose\nCOMPOSE_FILE ?= docker-compose.dev.yml\n",
    1)
s = s.replace("$(DOCKER_COMPOSE) ", "$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) ")
open(p, "w").write(s)
PY
grep -n "DOCKER_COMPOSE" Makefile
```

Expected: one `?=` definition line, one `COMPOSE_FILE ?=` line, and ten call sites each containing `-f $(COMPOSE_FILE)`. Verify the `?=` definition line itself was **not** rewritten — it has no trailing space after `docker-compose`, so the replace cannot match it, but confirm visually.

- [ ] **Step 4: Fix the dead image names in `clean`**

The `clean` target currently reads:

```makefile
	@docker rmi -f personal-finance-app-web-app personal-finance-app-server 2>/dev/null || true
```

`personal-finance-app-*` are image names from an unrelated project — this line has never removed this project's images. Compose names images `<project>-<service>`, and the project name defaults to the directory name. Replace it with a project-derived removal:

```makefile
	@docker rmi -f $$($(DOCKER_COMPOSE) -f $(COMPOSE_FILE) images -q 2>/dev/null) 2>/dev/null || true
```

Apply:

```bash
python3 - <<'PY'
p = "Makefile"
s = open(p).read()
s = s.replace(
    "\t@docker rmi -f personal-finance-app-web-app personal-finance-app-server 2>/dev/null || true\n",
    "\t@docker rmi -f $$($(DOCKER_COMPOSE) -f $(COMPOSE_FILE) images -q 2>/dev/null) 2>/dev/null || true\n",
    1)
open(p, "w").write(s)
PY
grep -n "docker rmi" Makefile
grep -c "personal-finance-app" Makefile   # expect 0
```

- [ ] **Step 5: Verify the Make targets work again**

```bash
make docker-run-core
sleep 20
curl -sf http://localhost:8000/health && echo "server up"
curl -sf -o /dev/null -w "internal-portal: %{http_code}\n" http://localhost:3000
curl -sf -o /dev/null -w "supplier-portal: %{http_code}\n" http://localhost:3002
make docker-stop
```

Expected: `server up`, and both portals returning `200` or `307` (Clerk redirect to sign-in is a valid healthy response).

- [ ] **Step 6: Run verification and commit**

Run: `./scripts/verify-infra.sh`
Expected: `docker-compose.dev.yml exists`, `old docker-compose.yml is gone`, `Makefile defines COMPOSE_FILE`, and `no stale personal-finance-app images` now PASS. Network and scope checks still FAIL.

```bash
git add Makefile docker-compose.dev.yml
git commit -m "refactor(infra): rename dev compose to docker-compose.dev.yml

Adds COMPOSE_FILE to the Makefile and threads -f through every compose
call site. Also replaces the clean target's hardcoded personal-finance-app
image names — leftovers from an unrelated project — with compose-derived
image IDs."
```

---

## Task 4: Rename the Docker network to `app-network`

**Files:**
- Modify: `docker-compose.dev.yml` (7 service references + 1 declaration)
- Modify: `docker-compose.prod.yml` (3 service references + 1 declaration)

**Interfaces:**
- Consumes: `docker-compose.dev.yml` from Task 3.
- Produces: network named `app-network` in both compose files. WS2's Traefik service attaches to this name.

- [ ] **Step 1: Confirm the current inconsistency**

```bash
grep -n "rilevio-network\|^  app:\|- app$" docker-compose.dev.yml docker-compose.prod.yml
```

Expected: dev uses `rilevio-network` (7 service entries + 1 declaration under `networks:`), prod uses `app` (3 service entries + 1 declaration). Two different names for the same logical network across environments.

- [ ] **Step 2: Rename in both files**

```bash
python3 - <<'PY'
import re

# dev: rilevio-network -> app-network (safe, unique token)
p = "docker-compose.dev.yml"
s = open(p).read()
assert "rilevio-network" in s, "expected rilevio-network in dev compose"
s = s.replace("rilevio-network", "app-network")
open(p, "w").write(s)

# prod: bare `app` network -> app-network. Anchored so it cannot hit
# service names, image names, or the `- app` list item of another key.
p = "docker-compose.prod.yml"
s = open(p).read()
s = re.sub(r"(?m)^(\s+)- app$", r"\1- app-network", s)
s = re.sub(r"(?m)^(\s{2})app:$", r"\1app-network:", s)
open(p, "w").write(s)
PY
echo "--- dev ---"; grep -n "app-network" docker-compose.dev.yml
echo "--- prod ---"; grep -n "app-network" docker-compose.prod.yml
```

Expected: dev shows 8 lines (7 service refs + 1 declaration), prod shows 4 lines (3 service refs + 1 declaration).

- [ ] **Step 3: Confirm both files still parse and every service resolves the network**

```bash
docker compose -f docker-compose.dev.yml config > /tmp/dev.yml && echo "dev parses"
grep -c "app-network" /tmp/dev.yml
```

Expected: `dev parses`. A dangling network reference makes `config` fail outright, so a clean parse proves every dev service reference matches the declaration.

**Prod is validated differently — do not run `docker compose config` on it.** `docker-compose.prod.yml` points `env_file` at `./web-app/.env.local`, which does not exist: prod compose is stale, still modelling a single `web-app` service from before the two-portal split. Reshaping it belongs to WS2, not WS1. Validate structurally instead:

```bash
./scripts/verify-infra.sh 2>&1 | grep "prod compose network refs"
```

Expected: `PASS: prod compose network refs all resolve`. This asserts every service's `networks:` entry matches a declared top-level network — exactly what this task changes.

- [ ] **Step 4: Boot the full stack to confirm cross-service DNS still resolves**

Prometheus scrapes `server:8000` and `cadvisor:8080` by service name — that only works if all three share the network.

```bash
make docker-run
sleep 30
curl -sf "http://localhost:9090/api/v1/targets" \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['data']['activeTargets']; [print(t['labels']['job'], '->', t['health']) for t in d]"
make docker-stop
```

Expected: both `fastapi` and `cadvisor` report `up`. Any `down` means the network rename broke service discovery.

- [ ] **Step 5: Run verification and commit**

Run: `./scripts/verify-infra.sh`
Expected: all four network checks now PASS. Only the `@rilevio/` scope and package-name checks still FAIL.

```bash
git add docker-compose.dev.yml docker-compose.prod.yml
git commit -m "refactor(infra): unify docker network as app-network

Dev used rilevio-network, prod used app. Both now use app-network, so
dev and prod agree and the B2C fork inherits the name unchanged."
```

---

## Task 5: Rename the pnpm scope to `@app` and the package identifiers

**Files:**
- Modify: `web-app/package.json`
- Modify: `web-app/packages/{ui,types,auth}/package.json`
- Modify: `web-app/apps/{internal-portal,supplier-portal}/package.json`
- Modify: `web-app/apps/*/next.config.ts`
- Modify: `web-app/apps/*/src/**/*.{ts,tsx}` (import specifiers)
- Modify: `web-app/apps/*/src/styles/globals.css`
- Modify: `web-app/packages/ui/src/components/layout/{app-sidebar,nav-sidebar}.tsx`
- Modify: `server/pyproject.toml`

**Interfaces:**
- Produces: pnpm scope `@app` — `@app/ui`, `@app/types`, `@app/auth`, `@app/internal-portal`, `@app/supplier-portal`; root workspace package `web-app`; Python distribution `server`. No exported symbol names change — only the specifier before the slash.

- [ ] **Step 1: Record the current reference count as a baseline**

```bash
grep -rl "@rilevio/" web-app --include="*.ts" --include="*.tsx" --include="*.css" --include="package.json" \
  --exclude-dir=node_modules --exclude-dir=.next | sort | tee /tmp/rilevio-files.txt | wc -l
```

Expected: **33 files**. Keep `/tmp/rilevio-files.txt` — Step 4 verifies exactly this set changed and nothing else.

- [ ] **Step 2: Confirm the type-check currently passes (so a later failure is attributable)**

```bash
cd web-app && pnpm install --frozen-lockfile && pnpm type-check; cd ..
```

Expected: clean. If it already fails, stop and report — this task must not be layered on a broken baseline.

- [ ] **Step 3: Rewrite the scope**

`@rilevio/` is a unique, unambiguous token — every occurrence is a package specifier. A literal replace is safe. Brand strings (`"Rilevio"`, `Rilevio`) do not contain the `@…/` form and are untouched.

```bash
# scope in all web-app sources and manifests
grep -rlZ "@rilevio/" web-app --include="*.ts" --include="*.tsx" --include="*.css" --include="package.json" \
  --exclude-dir=node_modules --exclude-dir=.next \
  | xargs -0 sed -i '' 's|@rilevio/|@app/|g'

# root workspace package name
sed -i '' 's|"name": "rilevio-web"|"name": "web-app"|' web-app/package.json

# python distribution name
sed -i '' 's|^name = "rilevio-server"|name = "server"|' server/pyproject.toml
```

Note: `sed -i ''` is the BSD/macOS form. On GNU/Linux use `sed -i` with no argument.

- [ ] **Step 4: Confirm exactly the expected files changed**

`/tmp/rilevio-files.txt` already holds repo-relative paths (grep was run from the repo root), so it compares directly:

```bash
git diff --name-only | grep "^web-app/" | sort > /tmp/changed-web.txt
diff <(sort /tmp/rilevio-files.txt) /tmp/changed-web.txt && echo "web-app file set matches exactly"
echo "--- non-web-app changes ---"
git diff --name-only | grep -v "^web-app/"
```

Expected: `web-app file set matches exactly`, and the only file under `--- non-web-app changes ---` is `server/pyproject.toml`.

If `diff` reports a file present in `changed-web.txt` but absent from the baseline, the sed hit something unintended — inspect it before continuing.

Then confirm no brand strings were caught in the blast radius:

```bash
git diff | grep "^[-+].*Rilevio" && echo "!!! BRAND STRING TOUCHED — REVERT !!!" || echo "OK — no brand strings modified"
```

Expected: `OK — no brand strings modified`. If a brand string appears, `git checkout -- .` and redo Step 3 more narrowly.

- [ ] **Step 5: Reinstall and type-check**

The workspace link names changed, so the lockfile must be regenerated — `--frozen-lockfile` will correctly refuse.

```bash
cd web-app
pnpm install
pnpm type-check
cd ..
```

Expected: `pnpm install` resolves `@app/ui`, `@app/types`, `@app/auth` as `workspace:*` links; `pnpm type-check` clean. An unresolved-import error means a specifier was missed — grep for it and fix before continuing.

- [ ] **Step 6: Build both portals**

Type-check does not exercise the Tailwind `@import "@app/ui/styles/globals.css"` or `transpilePackages`. A build does.

```bash
cd web-app && pnpm build; cd ..
```

Expected: both `internal-portal` and `supplier-portal` build successfully.

- [ ] **Step 7: Run verification and commit**

Run: `./scripts/verify-infra.sh`
Expected: **all checks PASS**, script exits 0, prints `All infra checks passed.`

```bash
git add web-app/package.json web-app/pnpm-lock.yaml web-app/packages web-app/apps server/pyproject.toml
git commit -m "refactor: rename pnpm scope @rilevio to @app

Package identifiers only — @app/{ui,types,auth}, web-app, server.
Product and brand strings (page titles, logoAlt, README prose) are
deliberately unchanged; renaming those is a rebrand, not a refactor.

Makes the planned B2C fork a copy with no rename step."
```

---

## Task 6: Update documentation to match the new layout

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `web-app/README.md`
- Modify: `web-app/apps/{internal-portal,supplier-portal}/README.md`

**Interfaces:**
- Consumes: final layout from Tasks 2–5. Documentation-only; no code depends on this task.

- [ ] **Step 1: Find every stale structural reference**

```bash
grep -n "prometheus/\|grafana/\|docker-compose.yml\|@rilevio\|rilevio-app/\|rilevio-web" \
  CLAUDE.md README.md web-app/README.md web-app/apps/*/README.md
```

Expected hits include: `CLAUDE.md:14` (`rilevio-app/` tree), the `prometheus/` and `grafana/` lines in that tree, `docker-compose.yml` in the same tree, and the `@rilevio/*` package tables in `web-app/README.md` and both app READMEs.

- [ ] **Step 2: Update `CLAUDE.md`'s repo structure block**

Replace the tree so it reflects reality:

```
rilevio-app/
├── server/               # FastAPI backend (Python 3.13, uv)
├── web-app/              # Next.js monorepo (pnpm workspaces)
│   ├── apps/
│   │   ├── internal-portal/   # Dashboard for project managers (port 3000)
│   │   └── supplier-portal/   # External supplier portal (port 3002)
│   └── packages/
│       ├── auth/              # @app/auth — Role enum, useAppAuth(), getUserRole()
│       ├── types/             # @app/types — shared TypeScript types
│       └── ui/                # @app/ui — shared component library (shadcn/ui)
├── infra/                # Infrastructure config
│   ├── prometheus/            # Prometheus scrape config
│   └── grafana/               # Grafana datasources and dashboards
├── docker-compose.dev.yml     # Development stack
└── docker-compose.prod.yml
```

Note this also fixes two pre-existing inaccuracies: the old tree omitted `packages/auth` and `packages/types` entirely, listing only `packages/ui`.

- [ ] **Step 3: Apply the identifier and path replacements across all five docs**

```bash
python3 - <<'PY'
import pathlib
docs = ["CLAUDE.md", "README.md", "web-app/README.md",
        "web-app/apps/internal-portal/README.md",
        "web-app/apps/supplier-portal/README.md"]
for d in docs:
    p = pathlib.Path(d)
    s = p.read_text()
    s = s.replace("@rilevio/", "@app/")
    s = s.replace("docker-compose.yml", "docker-compose.dev.yml")
    s = s.replace("├── prometheus/", "├── infra/prometheus/")
    s = s.replace("├── grafana/", "├── infra/grafana/")
    p.write_text(s)
    print("updated", d)
PY
```

Note: `docker-compose.prod.yml` contains the substring `docker-compose.yml`… it does not — the filename is `docker-compose.prod.yml`, so the replace above cannot corrupt it. Confirm anyway in Step 4.

- [ ] **Step 4: Verify no doc regression**

Two directions to check — nothing replaced twice, and nothing missed.

```bash
DOCS="CLAUDE.md README.md web-app/README.md web-app/apps/internal-portal/README.md web-app/apps/supplier-portal/README.md"

# (a) nothing double-replaced
grep -rn "docker-compose.dev.prod\|infra/infra/" $DOCS \
  && echo "!!! DOUBLE-REPLACEMENT BUG !!!" || echo "OK — no double replacements"

# (b) nothing missed
grep -n "@rilevio" $DOCS && echo "!!! @rilevio SURVIVED !!!" || echo "OK — no @rilevio left"
grep -nE "^(├──|│?\s*├──|└──)\s*(prometheus|grafana)/" $DOCS \
  && echo "!!! ROOT-LEVEL prometheus/grafana TREE ENTRY SURVIVED !!!" || echo "OK — no root-level monitoring entries"
grep -n "docker-compose\.yml" $DOCS \
  && echo "!!! BARE docker-compose.yml REFERENCE SURVIVED !!!" || echo "OK — no bare docker-compose.yml"
```

Expected: all four `OK —` lines, no `!!!` lines. Note check (b)'s last grep must not match `docker-compose.prod.yml` — that filename does not contain the substring `docker-compose.yml`, so a hit is a genuine stale reference.

- [ ] **Step 5: Final full verification**

```bash
./scripts/verify-infra.sh
make docker-run
sleep 30
curl -sf http://localhost:8000/health && echo "server ok"
curl -sf http://localhost:9090/-/healthy && echo "prometheus ok"
curl -sf http://localhost:3001/api/health && echo "grafana ok"
make docker-stop
```

Expected: `All infra checks passed.` plus all three `ok` lines.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md web-app/README.md web-app/apps/*/README.md
git commit -m "docs: update structure and identifiers for infra/ layout

Reflects infra/, docker-compose.dev.yml, and the @app scope. Also adds
packages/auth and packages/types to the CLAUDE.md tree, which had only
ever listed packages/ui."
```

---

## Task 7: Mark WS1 complete in the spec

**Files:**
- Modify: `docs/superpowers/specs/2026-08-24-template-hardening-design.md`

- [ ] **Step 1: Update the tracker row**

Change the WS1 row from:

```
| 1 | Infrastructure reorganisation | Planning | — | — |
```

to:

```
| 1 | Infrastructure reorganisation | ✅ Complete | `plans/2026-08-24-ws1-infra-reorg.md` | — |
```

And set the WS2 row's `Blocked by` column from `WS1` to `—`.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-08-24-template-hardening-design.md
git commit -m "docs(spec): mark WS1 complete, unblock WS2"
```

---

## Verification Matrix

| Spec requirement (WS1) | Task |
|---|---|
| Move `prometheus/` and `grafana/` under `infra/` | Task 2 |
| Rename `docker-compose.yml` → `docker-compose.dev.yml` | Task 3 |
| Update `Makefile` targets | Task 3 |
| Update `server/scripts/*.sh` references | **None needed** — verified: no script under `server/scripts/` references the root compose file, `prometheus/`, `grafana/`, or the `@rilevio` scope. They operate on `server/`-local paths only. |
| Genericise package scope `@rilevio/*` → `@app/*` | Task 5 |
| Genericise network name → `app-network` | Task 4 |
| Genericise container names | **No rename required** — verified: `container_name` is set on exactly three services (`internal-portal`, `supplier-portal` in dev; `web-app` in prod). None carries a product prefix, so all three are already neutral. |
| Acceptance: `make docker-run` / `docker-run-core` work | Task 3 Step 5, Task 6 Step 5 |
| Acceptance: Grafana finds datasource and dashboards | Task 2 Step 4 |
| Acceptance: no stale path references remain | Task 1 script, run at the end of every task |
