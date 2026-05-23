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
   `https://raw.githubusercontent.com/thisiischris/signaturerepo/main/zips/repository.signaturerepo/repository.signaturerepo-1.0.1.zip`
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
