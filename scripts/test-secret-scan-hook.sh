#!/bin/sh
# Self-test for the secret-scan pre-push hook, gitleaks config and setup script.
# Runs everything in a scratch dir (mktemp -d), prints PASS/FAIL per case and
# exits non-zero on any failure. Test tokens are generated at runtime and never
# printed. Cases 2-4 need gitleaks 8.30.1 (run `sh scripts/setup-githooks.sh`);
# case 5 downloads the release archive once (network).
set -u

GITLEAKS_VERSION=8.30.1
SRC=$(cd "$(dirname "$0")/.." && pwd)
ZERO=0000000000000000000000000000000000000000

WORK=$(mktemp -d "${TMPDIR:-/tmp}/secret-scan-test.XXXXXX") || exit 1
trap 'rm -rf "$WORK"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

FAILS=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; FAILS=$((FAILS + 1)); }
# Show hook output on failure, masking anything token-shaped (defence in depth;
# the hook already runs gitleaks with --redact).
show() { sed -E 's/gh[pousr]_[A-Za-z0-9]{20,}/gh*_<masked>/g; s/^/    | /' "$1"; }

# Locate a real gitleaks of the pinned version (PATH, then ~/.local/bin).
REAL_GITLEAKS=""
for c in "$(command -v gitleaks 2>/dev/null || true)" "$HOME/.local/bin/gitleaks"; do
  [ -n "$c" ] && [ -x "$c" ] || continue
  v=$("$c" version 2>/dev/null </dev/null | head -n 1 | tr -d '[:space:]')
  if [ "${v#v}" = "$GITLEAKS_VERSION" ]; then REAL_GITLEAKS=$c; break; fi
done

# PATH with every directory containing a gitleaks executable removed.
NOGL_PATH=""
OLDIFS=$IFS; IFS=:
for d in $PATH; do
  [ -n "$d" ] || continue
  [ -x "$d/gitleaks" ] && continue
  NOGL_PATH="${NOGL_PATH:+$NOGL_PATH:}$d"
done
IFS=$OLDIFS

# Isolate from the user's git config and ~/.local/bin.
export HOME="$WORK/home"
export GIT_CONFIG_NOSYSTEM=1
mkdir -p "$HOME"

n=0
new_repo() {
  n=$((n + 1)); R="$WORK/repo$n"
  mkdir -p "$R/.githooks" "$R/scripts"
  cp "$SRC/.githooks/pre-push" "$R/.githooks/pre-push"
  cp "$SRC/.gitleaks.toml" "$R/.gitleaks.toml"
  cp "$SRC/scripts/setup-githooks.sh" "$R/scripts/setup-githooks.sh"
  git init -q "$R"
  git -C "$R" config user.name "Secret Scan Test"
  git -C "$R" config user.email "secret-scan-test@example.invalid"
  git -C "$R" config commit.gpgsign false
  git -C "$R" add -A && git -C "$R" commit -q -m init
}
gen_token() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 36; }
commit_file() { # <path> <content-kind: token|clean>
  mkdir -p "$R/$(dirname "$1")"
  if [ "$2" = token ]; then
    printf 'GITHUB_TOKEN=ghp_%s\n' "$(gen_token)" >"$R/$1"
  else
    printf 'GITHUB_TOKEN=\nLOG_LEVEL=info\n' >"$R/$1"
  fi
  git -C "$R" add -f "$1" && git -C "$R" commit -q -m "add $1"
}
run_hook() { # <PATH> -> sets RC, output in $OUT
  OUT="$WORK/out$n"
  sha=$(git -C "$R" rev-parse HEAD)
  (cd "$R" && printf 'refs/heads/p %s refs/heads/p %s\n' "$sha" "$ZERO" |
    PATH="$1" sh .githooks/pre-push origin u) >"$OUT" 2>&1
  RC=$?
}

# Real gitleaks first on PATH for cases 2-4.
REALBIN="$WORK/realbin"; mkdir -p "$REALBIN"
[ -n "$REAL_GITLEAKS" ] && ln -s "$REAL_GITLEAKS" "$REALBIN/gitleaks"

# 1) wrong gitleaks version first on PATH
FAKEBIN="$WORK/fakebin"; mkdir -p "$FAKEBIN"
printf '#!/bin/sh\necho 8.18.0\n' >"$FAKEBIN/gitleaks"; chmod +x "$FAKEBIN/gitleaks"
new_repo; commit_file README.txt clean
run_hook "$FAKEBIN:$NOGL_PATH"
if [ "$RC" -eq 1 ] && grep -q "wrong gitleaks version" "$OUT"; then
  pass "1 wrong gitleaks version (8.18.0) blocks push"
else fail "1 wrong gitleaks version (rc=$RC)"; show "$OUT"; fi

if [ -z "$REAL_GITLEAKS" ]; then
  fail "2-4 gitleaks $GITLEAKS_VERSION not found (run: sh scripts/setup-githooks.sh)"
  FAILS=$((FAILS + 2))
else
  # 2) real-format GitHub PAT in .env.example
  new_repo; commit_file .env.example token
  run_hook "$REALBIN:$NOGL_PATH"
  if [ "$RC" -eq 1 ] && grep -q "github-pat" "$OUT"; then
    pass "2 token in .env.example blocked (github-pat)"
  else fail "2 token in .env.example (rc=$RC)"; show "$OUT"; fi

  # 3) same in a nested lockfile
  new_repo; commit_file sub/package-lock.json token
  run_hook "$REALBIN:$NOGL_PATH"
  if [ "$RC" -eq 1 ]; then
    pass "3 token in sub/package-lock.json blocked"
  else fail "3 token in sub/package-lock.json (rc=$RC)"; show "$OUT"; fi

  # 4) clean commit
  new_repo; commit_file .env.example clean
  run_hook "$REALBIN:$NOGL_PATH"
  if [ "$RC" -eq 0 ]; then
    pass "4 clean commit allowed"
  else fail "4 clean commit (rc=$RC)"; show "$OUT"; fi
fi

# 5) setup with wrong expected hash: must fail, install nothing, leave no temp files
new_repo
INST="$WORK/install5"; STMP="$WORK/tmp5"; mkdir -p "$STMP"
OUT="$WORK/out-setup5"
(cd "$R" && PATH="$NOGL_PATH" TMPDIR="$STMP" GITLEAKS_INSTALL_DIR="$INST" \
  GITLEAKS_EXPECTED_SHA256=0000000000000000000000000000000000000000000000000000000000000000 sh scripts/setup-githooks.sh) >"$OUT" 2>&1
RC=$?
if [ "$RC" -ne 0 ] && [ ! -e "$INST/gitleaks" ] && [ -z "$(ls -A "$STMP")" ] &&
   grep -q "checksum mismatch" "$OUT"; then
  pass "5 setup rejects checksum mismatch, installs nothing, cleans temp"
else fail "5 setup checksum mismatch (rc=$RC)"; show "$OUT"; fi

# 6) SKIP_GITLEAKS_INSTALL=1: hooksPath set, only pre-push made executable
new_repo
printf '#!/bin/sh\n' >"$R/.githooks/other"; chmod 644 "$R/.githooks/other"
chmod 644 "$R/.githooks/pre-push"
OUT="$WORK/out-setup6"
(cd "$R" && PATH="$NOGL_PATH" SKIP_GITLEAKS_INSTALL=1 sh scripts/setup-githooks.sh) >"$OUT" 2>&1
RC=$?
if [ "$RC" -eq 0 ] && [ "$(git -C "$R" config core.hooksPath)" = .githooks ] &&
   [ -x "$R/.githooks/pre-push" ] && [ ! -x "$R/.githooks/other" ]; then
  pass "6 SKIP_GITLEAKS_INSTALL sets hooksPath, chmods only pre-push"
else fail "6 SKIP_GITLEAKS_INSTALL (rc=$RC)"; show "$OUT"; fi

if [ "$FAILS" -ne 0 ]; then echo "$FAILS check(s) FAILED"; exit 1; fi
echo "All checks passed."
