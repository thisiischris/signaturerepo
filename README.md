# Signature Kodi Repository

Source repository for custom Kodi add-ons.

## Structure

```
signaturerepo/
├── addons/                          # Add-on source code
│   └── plugin.program.openwizard/
├── repository.signaturerepo/        # Repo add-on (install this in Kodi first)
├── zips/                            # Packaged add-ons for distribution
├── addons.xml                       # Generated add-on index for Kodi
├── addons.xml.md5                   # Checksum for addons.xml
└── tools/
    └── repo_generator.ps1            # Builds zips + addons.xml
```

## Add-ons

| Add-on | Folder | Description |
|--------|--------|-------------|
| OpenWizard | `addons/plugin.program.openwizard/` | Build wizard and maintenance tools |

## Install in Kodi

1. Enable **Unknown sources** in Kodi settings.
2. **Add-ons → Install from zip file** (do not rely on File manager browsing — GitHub does not list folders by default).
3. Choose **Enter link** and paste:
   `https://raw.githubusercontent.com/thisiischris/signaturerepo/main/zips/repository.signaturerepo/repository.signaturerepo-1.0.3.zip`
4. Install add-ons from **Install from repository → Signature Repository**.

If you add a file source, use `https://thisiischris.github.io/signaturerepo/zips/` (not the repo root). The root only shows this readme page.

## GitHub Pages

Kodi reads add-on metadata from `raw.githubusercontent.com` (reliable). GitHub Pages under `thisiischris.github.io/signaturerepo/zips/` is optional for browsing zips in File manager.

## Adding a new add-on

1. Create `addons/<addon.id>/` with a valid `addon.xml`.
2. Run `powershell -ExecutionPolicy Bypass -File tools/repo_generator.ps1` from the repo root.
3. Commit the updated `zips/`, `addons.xml`, and `addons.xml.md5`.

## Development

Work on add-on source under `addons/<addon.id>/`. Run the repo generator before pushing releases.

## Secret scanning (pre-push)

A `pre-push` hook runs [gitleaks](https://github.com/gitleaks/gitleaks) **8.30.1** on only the commits you're pushing and blocks the push if it finds likely secrets (values are always redacted). Any other gitleaks version is rejected.

**One-time setup:** `sh scripts/setup-githooks.sh` — sets `core.hooksPath=.githooks` and, if needed, downloads gitleaks 8.30.1 from the official GitHub release, verifies its pinned SHA-256 and installs it to `~/.local/bin` (override with `GITLEAKS_INSTALL_DIR`; `SKIP_GITLEAKS_INSTALL=1` sets only the hooks path).

**False positive?** Add a narrow, anchored *value* regex to `[allowlist] regexes` in `.gitleaks.toml` (or a `gitleaks:allow` comment on the line). Never allowlist paths — gitleaks skips those files entirely. `.gitleaks.toml` is the vendored gitleaks v8.30.1 default config with its global path allowlist removed, so lockfiles (`package-lock.json`, `yarn.lock`, `go.sum`, …), `node_modules/` and `.env.example` are scanned too; when bumping the pinned gitleaks version, re-vendor it (see the header in that file).

**Emergency bypass:** `SKIP_SECRET_SCAN=1 git push` (prints a warning; rotate anything real that slips through).

**Self-test:** `sh scripts/test-secret-scan-hook.sh` (scratch repo; prints PASS/FAIL per case).
