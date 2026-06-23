"""
Model versioning utilities.

Provides read/write access to the model version file and git tagging.
"""

import os
import subprocess
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_PATH = os.path.join(ROOT, "models/version.txt")


def read_version() -> str:
    """Read current model version from models/version.txt."""
    if os.path.exists(VERSION_PATH):
        with open(VERSION_PATH) as f:
            return f.read().strip()
    return "0.0.0"


def bump_version(part: str = "patch") -> str:
    """Bump major / minor / patch version."""
    current = read_version()
    parts = current.split(".")
    if len(parts) != 3:
        parts = ["0", "0", "0"]

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1

    new_version = f"{major}.{minor}.{patch}"
    os.makedirs(os.path.dirname(VERSION_PATH), exist_ok=True)
    with open(VERSION_PATH, "w") as f:
        f.write(new_version + "\n")
    return new_version


def tag_version(version: str | None = None, push: bool = True) -> str | None:
    """Create a git tag for the current model version."""
    if version is None:
        version = read_version()

    tag = f"models/v{version}"
    try:
        subprocess.run(
            ["git", "tag", "-a", tag, "-m", f"Model version {version}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        if push:
            subprocess.run(
                ["git", "push", "origin", tag],
                cwd=ROOT,
                check=True,
                capture_output=True,
            )
        print(f"✓ Created git tag: {tag}")
        return tag
    except subprocess.CalledProcessError as e:
        print(f"⚠ Git tag failed: {e.stderr.decode().strip()}")
        return None


def get_tags() -> list[str]:
    """List all model version tags."""
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "models/v*", "--sort=-v:refname"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        return []
