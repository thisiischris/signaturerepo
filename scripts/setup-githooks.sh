#!/bin/sh
# One-time setup: point git at the repo's versioned hooks.
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
echo "Git hooks enabled (core.hooksPath=.githooks)."
command -v gitleaks >/dev/null 2>&1 || [ -x "$HOME/.local/bin/gitleaks" ] || \
  echo "NOTE: gitleaks not found - install it or pushes will be blocked: https://github.com/gitleaks/gitleaks#installing"
