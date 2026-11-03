#!/bin/sh
# One-time setup: enable the versioned git hooks and install the pinned,
# checksum-verified gitleaks release used by .githooks/pre-push.
#
# Env:
#   SKIP_GITLEAKS_INSTALL=1     only set core.hooksPath, install nothing
#   GITLEAKS_INSTALL_DIR=<dir>  install dir (default: $HOME/.local/bin)
#   GITLEAKS_EXPECTED_SHA256=<hex>  override expected archive hash (testing only)
set -eu

GITLEAKS_VERSION=8.30.1

cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/pre-push
echo "Git hooks enabled (core.hooksPath=.githooks)."

if [ "${SKIP_GITLEAKS_INSTALL:-}" = "1" ]; then
  echo "SKIP_GITLEAKS_INSTALL=1: not installing gitleaks."
  exit 0
fi

INSTALL_DIR=${GITLEAKS_INSTALL_DIR:-$HOME/.local/bin}

has_pinned_version() {
  [ -n "$1" ] && [ -x "$1" ] || return 1
  v=$("$1" version 2>/dev/null </dev/null | head -n 1 | tr -d '[:space:]') || return 1
  [ "${v#v}" = "$GITLEAKS_VERSION" ]
}

for candidate in "$(command -v gitleaks 2>/dev/null || true)" "$INSTALL_DIR/gitleaks"; do
  if has_pinned_version "$candidate"; then
    echo "gitleaks $GITLEAKS_VERSION already installed: $candidate"
    exit 0
  fi
done

case "$(uname -s)" in
  Darwin) os=darwin ;;
  Linux)  os=linux ;;
  *) echo "ERROR: unsupported OS '$(uname -s)'; install gitleaks $GITLEAKS_VERSION manually." >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64)  arch=x64 ;;
  arm64|aarch64) arch=arm64 ;;
  armv7*)        arch=armv7 ;;
  *) arch="$(uname -m)" ;;
esac

# Source: official gitleaks_8.30.1_checksums.txt from the v8.30.1 GitHub release.
case "${os}_${arch}" in
  darwin_arm64) sha=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
  darwin_x64)   sha=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
  linux_arm64)  sha=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
  linux_armv7)  sha=8d39f0d94ba0d774b2282187656fb039a2d82893ec1fd6be7d7121aae759a57d ;;
  linux_x64)    sha=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
  *) echo "ERROR: unsupported platform ${os}_${arch}; install gitleaks $GITLEAKS_VERSION manually." >&2; exit 1 ;;
esac
EXPECTED=$(printf '%s' "${GITLEAKS_EXPECTED_SHA256:-$sha}" | tr 'A-F' 'a-f')

ASSET="gitleaks_${GITLEAKS_VERSION}_${os}_${arch}.tar.gz"
URL="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${ASSET}"

TMP=$(mktemp -d "${TMPDIR:-/tmp}/gitleaks-install.XXXXXX")
cleanup() { rm -rf "$TMP"; rm -f "$INSTALL_DIR/.gitleaks.tmp.$$"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Downloading $URL"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL --proto '=https' -o "$TMP/$ASSET" "$URL"
elif command -v wget >/dev/null 2>&1; then
  wget -q -O "$TMP/$ASSET" "$URL"
else
  echo "ERROR: need curl or wget to download gitleaks." >&2; exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$TMP/$ASSET" | cut -d' ' -f1)
elif command -v shasum >/dev/null 2>&1; then
  actual=$(shasum -a 256 "$TMP/$ASSET" | cut -d' ' -f1)
else
  echo "ERROR: need sha256sum or shasum to verify the download." >&2; exit 1
fi

if [ "$actual" != "$EXPECTED" ]; then
  echo "ERROR: checksum mismatch for $ASSET (expected $EXPECTED, got $actual). Nothing installed." >&2
  exit 1
fi
echo "Checksum verified (sha256 $actual)."

mkdir "$TMP/x"
tar -xzf "$TMP/$ASSET" -C "$TMP/x" gitleaks
[ -f "$TMP/x/gitleaks" ] || { echo "ERROR: gitleaks binary missing from archive." >&2; exit 1; }
chmod 755 "$TMP/x/gitleaks"

mkdir -p "$INSTALL_DIR"
cp "$TMP/x/gitleaks" "$INSTALL_DIR/.gitleaks.tmp.$$"
mv -f "$INSTALL_DIR/.gitleaks.tmp.$$" "$INSTALL_DIR/gitleaks"
echo "Installed gitleaks $GITLEAKS_VERSION to $INSTALL_DIR/gitleaks"

case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *) [ "$INSTALL_DIR" = "$HOME/.local/bin" ] || \
       echo "NOTE: $INSTALL_DIR is not on PATH; add it so the pre-push hook can find gitleaks." ;;
esac
