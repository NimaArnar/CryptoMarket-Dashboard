#!/usr/bin/env python3
"""Create GitHub issues #37 and #38 from issue markdown files."""

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

REPO_OWNER = "NimaArnar"
REPO_NAME = "CryptoMarket-Dashboard"
GITHUB_API_BASE = "https://api.github.com"

ISSUE_FILES = [
    "037-coins-list-back-to-data-queries.md",
    "038-data-queries-buttons-resend-menu-message.md",
]


def get_token():
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("Set GITHUB_TOKEN (or GH_TOKEN) environment variable.")
        sys.exit(1)
    return token


def create_issue(token, title, body, labels=None):
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    data = {"title": title, "body": body, "labels": labels or ["enhancement"]}
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 201:
        return r.json()
    raise RuntimeError(f"{r.status_code}: {r.text}")


def parse_file(path):
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    title = None
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            start = i + 1
            break
    if not title:
        title = path.stem.replace("-", " ").title()
    body = "\n".join(lines[start:]).strip()
    return title, body


def main():
    token = get_token()
    issues_dir = Path(__file__).parent.parent / "issues"
    for name in ISSUE_FILES:
        path = issues_dir / name
        if not path.exists():
            print(f"Skip (not found): {name}")
            continue
        title, body = parse_file(path)
        try:
            result = create_issue(token, title, body)
            num = result.get("number")
            url = result.get("html_url", "")
            print(f"Created #{num}: {title}")
            print(f"  {url}")
        except Exception as e:
            print(f"Failed {name}: {e}")


if __name__ == "__main__":
    main()
