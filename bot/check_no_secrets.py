#!/usr/bin/env python3
"""Fail when a credential is about to ship in this repository.

Checks every tracked-looking file for the shapes that have actually leaked in this project and
its ancestors: Telegram bot tokens, .env files, private keys, GitHub tokens.
"""

import pathlib
import re
import sys

SKIP_DIRS = {".git", "build", ".gradle", "node_modules", "venv", "__pycache__"}
SKIP_NAMES = {"check_no_secrets.py"}

MAX_BYTES = 2 * 1024 * 1024

PATTERNS = [
    ("telegram bot token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bot token assignment", re.compile(r"^\s*BOT_TOKEN\s*=\s*['\"]?[0-9]{6,}:[A-Za-z0-9_-]{20,}", re.MULTILINE)),
]


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    hits = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_NAMES:
            continue
        if path.name == ".env" or path.name.startswith(".env."):
            hits.append((path, "env file committed"))
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for label, pattern in PATTERNS:
            match = pattern.search(text)
            if match:
                line = text[: match.start()].count("\n") + 1
                hits.append((path, f"{label} at line {line}"))

    if not hits:
        print(f"no credentials found in {root}")
        return 0

    for path, reason in hits:
        relative = path.relative_to(root)
        print(f"::error file={relative}::{reason}")
        print(f"  {relative}: {reason}")

    print(f"\n{len(hits)} finding(s). Remove the file or the value before pushing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
