"""Fail if the repository is not ready to publish: leftover placeholders, tracked secrets, missing files.

Usage (from the repo root):  python scripts/prepublish_check.py
"""

import re
import subprocess
import sys

files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
problems = []

for required in ("README.md", "LICENSE", ".gitignore", ".env.example", "SECURITY.md", "THIRD_PARTY_NOTICES.md"):
    if required not in files:
        problems.append(f"missing file: {required}")

if any(re.search(r"(^|/)\.env$", f) for f in files):
    problems.append(".env is tracked by git - remove it (git rm --cached .env)")

PLACEHOLDERS = [r"\[YOUR NAME\]", r"<add your", r"CHANGE_ME_BEFORE_PUBLISH"]
SECRETS = [r"BEGIN (RSA |EC )?PRIVATE KEY", r"AKIA[0-9A-Z]{16}", r"ghp_[A-Za-z0-9]{30,}", r"sk-[A-Za-z0-9]{32,}"]

for f in files:
    if f.endswith((".png", ".lock", ".json")) and f != "frontend/package.json" or f == "scripts/prepublish_check.py":
        continue
    try:
        text = open(f, encoding="utf-8").read()
    except (UnicodeDecodeError, FileNotFoundError):
        continue
    for pat in PLACEHOLDERS:
        if re.search(pat, text):
            problems.append(f"placeholder still present in {f}: {pat}")
    for pat in SECRETS:
        if re.search(pat, text):
            problems.append(f"possible secret in {f}: {pat}")

if problems:
    print("NOT READY TO PUBLISH:")
    print("\n".join(f" - {p}" for p in problems))
    sys.exit(1)
print(f"OK: {len(files)} tracked files, no placeholders, no tracked .env, no secret patterns found.")
