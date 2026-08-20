"""Verify that the version in pyproject.toml has a matching CHANGELOG.md section.

Exits 1 on a mismatch. Runs in CI as a gate — a release tagged from a version
nobody wrote a changelog entry for is a release nobody can read.

An [Unreleased] section is allowed to sit above the current version: that is
work landed but not yet released.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"

_SECTION_RE = re.compile(r"^##\s*\[([^\]]+)\]", re.MULTILINE)


def project_version() -> str:
    with PYPROJECT.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def changelog_versions() -> list[str]:
    return _SECTION_RE.findall(CHANGELOG.read_text(encoding="utf-8"))


def main() -> None:
    version = project_version()
    sections = changelog_versions()

    if not sections:
        print("CHANGELOG.md has no '## [version]' sections", file=sys.stderr)
        raise SystemExit(1)

    if version not in sections:
        print(
            f"pyproject.toml is at {version}, but CHANGELOG.md has no section for it.\n"
            f"Sections found: {', '.join(sections)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"OK: version {version} documented in CHANGELOG.md")


if __name__ == "__main__":
    main()
