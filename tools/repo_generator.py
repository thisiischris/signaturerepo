#!/usr/bin/env python3
"""Build Kodi repository zips and generate addons.xml."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ADDON_DIRS = [ROOT / "addons", ROOT / "repository.signaturerepo"]
ZIPS_DIR = ROOT / "zips"
EXCLUDE_DIRS = {"__pycache__", ".git", ".github", "tools", "zips"}
EXCLUDE_FILES = {".gitignore", ".DS_Store", "Thumbs.db"}


def addon_paths() -> list[Path]:
    paths: list[Path] = []
    for base in ADDON_DIRS:
        if not base.exists():
            continue
        if (base / "addon.xml").is_file():
            paths.append(base)
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "addon.xml").is_file():
                paths.append(child)
    return paths


def read_addon_id(addon_dir: Path) -> str:
    tree = ET.parse(addon_dir / "addon.xml")
    addon_id = tree.getroot().attrib.get("id")
    if not addon_id:
        raise ValueError(f"Missing addon id in {addon_dir / 'addon.xml'}")
    return addon_id


def read_addon_version(addon_dir: Path) -> str:
    tree = ET.parse(addon_dir / "addon.xml")
    version = tree.getroot().attrib.get("version")
    if not version:
        raise ValueError(f"Missing addon version in {addon_dir / 'addon.xml'}")
    return version


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix in {".pyc", ".pyo"}:
        return True
    return False


def build_zip(addon_dir: Path) -> Path:
    addon_id = read_addon_id(addon_dir)
    version = read_addon_version(addon_dir)
    target_dir = ZIPS_DIR / addon_id
    target_dir.mkdir(parents=True, exist_ok=True)

    zip_path = target_dir / f"{addon_id}-{version}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(addon_dir.rglob("*")):
            if not file_path.is_file() or should_skip(file_path):
                continue
            arcname = Path(addon_id) / file_path.relative_to(addon_dir)
            archive.write(file_path, arcname.as_posix())

    return zip_path


def extract_addon_xml(addon_dir: Path) -> str:
    content = (addon_dir / "addon.xml").read_text(encoding="utf-8")
    match = re.search(r"<addon\b[^>]*>.*?</addon>", content, re.DOTALL)
    if not match:
        raise ValueError(f"Could not parse addon block in {addon_dir / 'addon.xml'}")
    return match.group(0).strip()


def write_addons_xml(addon_dirs: list[Path]) -> None:
    blocks = [extract_addon_xml(addon_dir) for addon_dir in addon_dirs]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n'
    xml += "\n".join(f"  {block}" for block in blocks)
    xml += "\n</addons>\n"
    (ROOT / "addons.xml").write_text(xml, encoding="utf-8")


def write_addons_md5() -> None:
    digest = hashlib.md5((ROOT / "addons.xml").read_bytes()).hexdigest()
    (ROOT / "addons.xml.md5").write_text(digest, encoding="utf-8")


def main() -> None:
    addon_dirs = addon_paths()
    if not addon_dirs:
        raise SystemExit("No add-ons found.")

    if ZIPS_DIR.exists():
        shutil.rmtree(ZIPS_DIR)
    ZIPS_DIR.mkdir(parents=True, exist_ok=True)

    for addon_dir in addon_dirs:
        zip_path = build_zip(addon_dir)
        print(f"Built {zip_path.relative_to(ROOT)}")

    write_addons_xml(addon_dirs)
    write_addons_md5()
    print("Updated addons.xml and addons.xml.md5")


if __name__ == "__main__":
    main()
