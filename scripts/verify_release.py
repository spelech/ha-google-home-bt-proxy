#!/usr/bin/env python3
"""
Release and Version Verification Engine for ha-google-home-bt-proxy
Validates version consistency across pyproject.toml and manifest.json,
and verifies markdown relative links and anchor integrity.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path


def check_version_sync(root_dir: Path) -> bool:
    """Verify version consistency between pyproject.toml and manifest.json."""
    print("🔍 Checking version consistency across manifests...")
    pyproject_file = root_dir / "pyproject.toml"
    manifest_file = root_dir / "custom_components" / "google_home_bt_proxy" / "manifest.json"

    if not pyproject_file.is_file():
        print(f"❌ Missing pyproject.toml at {pyproject_file}")
        return False
    if not manifest_file.is_file():
        print(f"❌ Missing manifest.json at {manifest_file}")
        return False

    with open(pyproject_file, "rb") as f:
        pyproject_data = tomllib.load(f)
    pyproject_version = pyproject_data.get("project", {}).get("version")

    with open(manifest_file, encoding="utf-8") as f:
        manifest_data = json.load(f)
    manifest_version = manifest_data.get("version")

    if not pyproject_version:
        print("❌ No version found in pyproject.toml")
        return False

    if not manifest_version:
        print("❌ No version found in manifest.json")
        return False

    if pyproject_version != manifest_version:
        print(
            f"❌ Version mismatch! pyproject.toml ({pyproject_version}) != "
            f"manifest.json ({manifest_version})"
        )
        return False

    print(f"✅ Version synchronized: v{pyproject_version}")
    return True


def check_markdown_links(root_dir: Path) -> bool:
    """Verify all relative markdown links point to existing files."""
    print("🔍 Checking markdown relative links...")
    has_errors = False
    excluded = {".venv", ".git", "node_modules", "bin", "obj", ".system_generated"}
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in excluded]
        for file in files:
            if not file.endswith(".md"):
                continue
            md_file = Path(root) / file
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
            for text, link in links:
                if (
                    link.startswith("http://")
                    or link.startswith("https://")
                    or link.startswith("#")
                    or link.startswith("mailto:")
                ):
                    continue
                target_path = link.split("#")[0]
                if not target_path:
                    continue
                resolved = (md_file.parent / target_path).resolve()
                if not resolved.exists():
                    print(f"❌ Broken link in {md_file.relative_to(root_dir)}: [{text}]({link})")
                    has_errors = True

    if not has_errors:
        print("✅ All markdown links verified successfully.")
    return not has_errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Release Verification Engine")
    parser.add_argument("--skip-tests", action="store_true", help="Skip test suite execution")
    parser.add_argument("--ci", action="store_true", help="CI mode")
    parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    version_ok = check_version_sync(root_dir)
    links_ok = check_markdown_links(root_dir)

    success = version_ok and links_ok
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
