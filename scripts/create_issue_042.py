#!/usr/bin/env python3
"""Create GitHub issue from issues/042-data-queries-labels-command-name-only.md."""
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

REPO_OWNER = "NimaArnar"
REPO_NAME = "CryptoMarket-Dashboard"
GITHUB_API_BASE = "https://api.github.com"
ISSUE_FILE = "042-data-queries-labels-command-name-only.md"

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
    t = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not t:
        print("Set GITHUB_TOKEN or GH_TOKEN")
        sys.exit(1)
    return t


def main():
    token = get_token()
    path = _project_root / "issues" / ISSUE_FILE
    if not path.exists():
        print(f"Not found: {path}")
        sys.exit(1)
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    title = lines[0].replace("# ", "").strip() if lines and lines[0].startswith("# ") else path.stem.replace("-", " ").title()
    body = "\n".join(lines[1:]).strip()
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    r = requests.post(url, headers=headers, json={"title": title, "body": body, "labels": ["enhancement", "telegram-bot"]})
    if r.status_code == 201:
        d = r.json()
        print(f"Created #{d['number']}: {d['title']}")
        print(d["html_url"])
    else:
        print(f"Error {r.status_code}: {r.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()
