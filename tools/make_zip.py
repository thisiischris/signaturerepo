import zipfile, os, hashlib

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── wizard zip ────────────────────────────────────────────────────────────────
addon_src = os.path.join(base, "addons", "plugin.program.openwizard")
wizard_zip = os.path.join(base, "zips", "plugin.program.openwizard", "plugin.program.openwizard-2.1.0.zip")

with zipfile.ZipFile(wizard_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(addon_src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith(".pyc"):
                continue
            full_path = os.path.join(root, file)
            arc_path = "plugin.program.openwizard/" + os.path.relpath(full_path, addon_src).replace(os.sep, "/")
            zf.write(full_path, arc_path)

print("Wizard zip created:", wizard_zip)

# ── repository zip ────────────────────────────────────────────────────────────
repo_addon_xml = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="repository.signaturerepo" name="Signature Repository" version="1.0.4" provider-name="thisiischris">
    <extension point="xbmc.addon.repository" name="Signature Repository">
        <dir minversion="19.0.0" maxversion="22.9.9">
            <info compressed="false">https://raw.githubusercontent.com/thisiischris/signaturerepo/main/addons.xml</info>
            <checksum>https://raw.githubusercontent.com/thisiischris/signaturerepo/main/addons.xml.md5</checksum>
            <datadir zip="true">https://raw.githubusercontent.com/thisiischris/signaturerepo/main/zips/</datadir>
        </dir>
    </extension>
    <extension point="xbmc.addon.metadata">
        <summary lang="en">Signature custom Kodi add-ons</summary>
        <description lang="en">Repository for Signature Kodi add-ons.</description>
        <platform>all</platform>
        <assets>
            <icon>icon.png</icon>
        </assets>
    </extension>
</addon>"""

repo_zip = os.path.join(base, "zips", "repository.signaturerepo", "repository.signaturerepo-1.0.4.zip")
old_repo_zip = os.path.join(base, "zips", "repository.signaturerepo", "repository.signaturerepo-1.0.3.zip")

# copy icon from old zip, replace addon.xml
with zipfile.ZipFile(old_repo_zip, "r") as old_zf:
    with zipfile.ZipFile(repo_zip, "w", zipfile.ZIP_DEFLATED) as new_zf:
        for item in old_zf.infolist():
            if item.filename.endswith("addon.xml"):
                new_zf.writestr(item.filename, repo_addon_xml)
            else:
                new_zf.writestr(item, old_zf.read(item.filename))

print("Repo zip created:", repo_zip)

# ── addons.xml MD5 ────────────────────────────────────────────────────────────
addons_xml = os.path.join(base, "addons.xml")
with open(addons_xml, "rb") as f:
    content = f.read().replace(b"\r\n", b"\n")  # match LF bytes GitHub serves
md5 = hashlib.md5(content).hexdigest()
with open(os.path.join(base, "addons.xml.md5"), "w", newline="") as f:
    f.write(md5)
print("MD5:", md5)
