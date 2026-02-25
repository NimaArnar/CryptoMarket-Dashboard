#!/usr/bin/env python3
"""Create GitHub issues #39, #40, #41 from issue markdown files."""

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
    "039-correlation-send-1y-chart-two-coins.md",
    "040-watchlist-for-telegram-users.md",
    "041-add-coins-from-yahoo-finance-api.md",
]

# Load .env from project root if present
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key and value and key in ("GITHUB_TOKEN", "GH_TOKEN"):
                        os.environ.setdefault(key, value)
    except Exception:
        pass


def get_token():
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("Set GITHUB_TOKEN (or GH_TOKEN) environment variable or add to .env")
        sys.exit(1)
    return token


def create_issue(token, title, body, labels=None):
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    data = {"title": title, "body": body, "labels": labels or ["enhancement", "feature"]}
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
