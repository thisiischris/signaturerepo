#!/bin/sh
# Self-test for the secret-scan pre-push hook, gitleaks config and setup script.
# Runs everything in a scratch dir (mktemp -d), prints PASS/FAIL per case and
# exits non-zero on any failure. Test tokens are generated at runtime and never
# printed. Cases 2-4 need gitleaks 8.30.1 (run `sh scripts/setup-githooks.sh`).
# No network: setup cases use a fake `curl` on PATH that serves a bogus archive.
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

# Fake curl: writes a bogus "archive" to the -o target (no network) and logs
# the call. The pinned checksum can't match it, so setup must refuse to install.
FAKECURL="$WORK/fakecurl"; mkdir -p "$FAKECURL"
cat >"$FAKECURL/curl" <<'SH'
#!/bin/sh
out=""
while [ $# -gt 0 ]; do
  [ "$1" = "-o" ] && { out=$2; shift; }
  shift
done
[ -n "$out" ] || exit 2
printf 'not a real gitleaks archive\n' >"$out"
echo called >>"$FAKECURL_LOG"
SH
chmod +x "$FAKECURL/curl"

# Fake gitleaks reporting the pinned version (exits 0 for any subcommand).
PINBIN="$WORK/pinbin"; mkdir -p "$PINBIN"
printf '#!/bin/sh\necho %s\n' "$GITLEAKS_VERSION" >"$PINBIN/gitleaks"; chmod +x "$PINBIN/gitleaks"

run_setup() { # <case> <HOME> <PATH> [VAR=val ...] -> RC, OUT, STMP, CURL_LOG
  c=$1; h=$2; p=$3; shift 3
  STMP="$WORK/tmp$c"; mkdir -p "$STMP" "$h"
  OUT="$WORK/out-setup$c"; CURL_LOG="$WORK/curl$c.log"; : >"$CURL_LOG"
  (cd "$R" && env HOME="$h" PATH="$p" TMPDIR="$STMP" FAKECURL_LOG="$CURL_LOG" "$@" \
    sh scripts/setup-githooks.sh) >"$OUT" 2>&1
  RC=$?
}
mismatch_ok() { # <install dir>: failed on checksum, nothing installed, temp cleaned
  [ "$RC" -ne 0 ] && [ -s "$CURL_LOG" ] && [ ! -e "$1/gitleaks" ] &&
    [ -z "$(ls -A "$1" 2>/dev/null)" ] && [ -z "$(ls -A "$STMP")" ] &&
    grep -q "checksum mismatch" "$OUT"
}

# 5) bad download (pinned checksum can't be overridden): fail, install nothing
new_repo
INST="$WORK/install5"
run_setup 5 "$WORK/home5" "$FAKECURL:$NOGL_PATH" GITLEAKS_INSTALL_DIR="$INST"
if mismatch_ok "$INST"; then
  pass "5 setup rejects checksum mismatch, installs nothing, cleans temp"
else fail "5 setup checksum mismatch (rc=$RC)"; show "$OUT"; fi

# 5b) the old test-only override is gone: a matching env hash must not help
new_repo
INST="$WORK/install5b"
BOGUS_SHA=$(printf 'not a real gitleaks archive\n' | { sha256sum 2>/dev/null || shasum -a 256; } | cut -d' ' -f1)
run_setup 5b "$WORK/home5b" "$FAKECURL:$NOGL_PATH" GITLEAKS_INSTALL_DIR="$INST" \
  GITLEAKS_EXPECTED_SHA256="$BOGUS_SHA"
if mismatch_ok "$INST"; then
  pass "5b GITLEAKS_EXPECTED_SHA256 cannot override the pinned checksum"
else fail "5b checksum override still honoured (rc=$RC)"; show "$OUT"; fi

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

# 7-9) setup's "already installed" check picks gitleaks exactly like the hook.
# 7) wrong version first on PATH, pinned copy in ~/.local/bin: hook blocks, so
#    setup must NOT report "already installed" (it tries to install instead).
new_repo; commit_file README.txt clean
H="$WORK/home7"; mkdir -p "$H/.local/bin"; cp "$PINBIN/gitleaks" "$H/.local/bin/gitleaks"
(HOME="$H"; export HOME; run_hook "$FAKEBIN:$NOGL_PATH"; echo "$RC" >"$WORK/rc7")
HOOK_RC=$(cat "$WORK/rc7")
run_setup 7 "$H" "$FAKEBIN:$FAKECURL:$NOGL_PATH"
if [ "$HOOK_RC" -eq 1 ] && [ "$RC" -ne 0 ] && ! grep -q "already installed" "$OUT" &&
   grep -q "checksum mismatch" "$OUT"; then
  pass "7 wrong version on PATH: hook blocks and setup does not claim installed"
else fail "7 selection parity, wrong PATH version (hook rc=$HOOK_RC, setup rc=$RC)"; show "$OUT"; fi

# 8) pinned copy only in ~/.local/bin (not on PATH): hook uses it, setup agrees.
new_repo; commit_file README.txt clean
H="$WORK/home8"; mkdir -p "$H/.local/bin"; cp "$PINBIN/gitleaks" "$H/.local/bin/gitleaks"
(HOME="$H"; export HOME; run_hook "$NOGL_PATH"; echo "$RC" >"$WORK/rc8")
HOOK_RC=$(cat "$WORK/rc8")
run_setup 8 "$H" "$FAKECURL:$NOGL_PATH"
if [ "$HOOK_RC" -eq 0 ] && [ "$RC" -eq 0 ] && [ ! -s "$CURL_LOG" ] &&
   grep -q "already installed: $H/.local/bin/gitleaks" "$OUT"; then
  pass "8 ~/.local/bin fallback: hook and setup select the same binary"
else fail "8 selection parity, ~/.local/bin (hook rc=$HOOK_RC, setup rc=$RC)"; show "$OUT"; fi

# 9) pinned copy only in a custom GITLEAKS_INSTALL_DIR off PATH: the hook can't
#    find it, so setup must not treat it as installed.
new_repo; commit_file README.txt clean
H="$WORK/home9"; INST="$WORK/install9"; mkdir -p "$H" "$INST"; cp "$PINBIN/gitleaks" "$INST/gitleaks"
(HOME="$H"; export HOME; run_hook "$NOGL_PATH"; echo "$RC" >"$WORK/rc9")
HOOK_RC=$(cat "$WORK/rc9")
run_setup 9 "$H" "$FAKECURL:$NOGL_PATH" GITLEAKS_INSTALL_DIR="$INST"
if [ "$HOOK_RC" -eq 1 ] && [ "$RC" -ne 0 ] && ! grep -q "already installed" "$OUT" &&
   grep -q "checksum mismatch" "$OUT" && cmp -s "$PINBIN/gitleaks" "$INST/gitleaks"; then
  pass "9 custom install dir off PATH: hook can't find it, setup does not claim installed"
else fail "9 selection parity, custom dir (hook rc=$HOOK_RC, setup rc=$RC)"; show "$OUT"; fi

if [ "$FAILS" -ne 0 ]; then echo "$FAILS check(s) FAILED"; exit 1; fi
echo "All checks passed."
