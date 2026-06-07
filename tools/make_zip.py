import zipfile, os, hashlib

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
addon_src = os.path.join(base, "addons", "plugin.program.openwizard")
zip_path = os.path.join(base, "zips", "plugin.program.openwizard", "plugin.program.openwizard-2.0.11.zip")

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(addon_src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith(".pyc"):
                continue
            full_path = os.path.join(root, file)
            arc_path = "plugin.program.openwizard/" + os.path.relpath(full_path, addon_src).replace(os.sep, "/")
            zf.write(full_path, arc_path)

print("Zip created:", zip_path)

addons_xml = os.path.join(base, "addons.xml")
with open(addons_xml, "rb") as f:
    content = f.read().replace(b"\r\n", b"\n")  # match what GitHub serves (LF only)
md5 = hashlib.md5(content).hexdigest()
with open(os.path.join(base, "addons.xml.md5"), "w", newline="") as f:
    f.write(md5)
print("MD5:", md5)
