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
2. Install the repository add-on zip from:
   `https://thisiischris.github.io/signaturerepo/zips/repository.signaturerepo/repository.signaturerepo-1.0.0.zip`
3. Install add-ons from **Add-on browser → Install from repository → Signature Repository**.

## GitHub Pages

Enable Pages on the `main` branch, serving from the repository root. Kodi will read:

- `https://thisiischris.github.io/signaturerepo/addons.xml`
- `https://thisiischris.github.io/signaturerepo/zips/`

## Adding a new add-on

1. Create `addons/<addon.id>/` with a valid `addon.xml`.
2. Run `powershell -ExecutionPolicy Bypass -File tools/repo_generator.ps1` from the repo root.
3. Commit the updated `zips/`, `addons.xml`, and `addons.xml.md5`.

## Development

Work on add-on source under `addons/<addon.id>/`. Run the repo generator before pushing releases.
