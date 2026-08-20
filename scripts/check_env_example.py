"""Verify that every os.getenv() call in paradox_bot/ has an entry in .env.example.

Exits 1 and lists the missing variables. Runs in CI as a gate — an undocumented
environment variable is one nobody sets on the server until something breaks.
BOT_PREFIX shipped undocumented for exactly this reason before the gate existed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = PROJECT_ROOT / "paradox_bot"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"

_GETENV_RE = re.compile(r'os\.(?:getenv|environ\.get)\(\s*["\']([A-Z_][A-Z0-9_]*)["\']')


def collect_used() -> set[str]:
    found: set[str] = set()
    for py_file in PACKAGE_DIR.rglob("*.py"):
        found.update(_GETENV_RE.findall(py_file.read_text(encoding="utf-8")))
    return found


def collect_documented() -> set[str]:
    documented: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            documented.add(line.split("=", 1)[0].strip())
    return documented


def main() -> None:
    used = collect_used()
    documented = collect_documented()

    missing = sorted(used - documented)
    unused = sorted(documented - used)

    for name in missing:
        print(f"missing from .env.example: {name}", file=sys.stderr)
    for name in unused:
        print(f"documented but never read: {name}", file=sys.stderr)

    if missing or unused:
        raise SystemExit(1)
    print(f"OK: {len(used)} environment variables, all documented")


if __name__ == "__main__":
    main()
