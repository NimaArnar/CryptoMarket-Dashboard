#!/usr/bin/env python3
"""
Update GitHub repo About section (description + website/homepage).

Uses GITHUB_TOKEN or GH_TOKEN from environment (or .env) with 'repo' scope.
"""

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


def get_token() -> str:
    t = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not t:
        print("Set GITHUB_TOKEN or GH_TOKEN in your environment or .env")
        sys.exit(1)
    return t


def main() -> None:
    token = get_token()
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    description = (
        "Interactive crypto market cap dashboard (Dash/Plotly) with a Telegram bot "
        "for remote control, data queries, charts, and correlation analysis."
    )
    homepage = "https://nimaarnar.github.io/CryptoMarket-Dashboard/"

    payload = {
        "description": description,
        "homepage": homepage,
    }

    resp = requests.patch(url, headers=headers, json=payload)
    if resp.status_code == 200:
        print("✅ Updated repo About section:")
        print(f"  Description: {description}")
        print(f"  Website   : {homepage}")
    else:
        print(f"❌ Error {resp.status_code}: {resp.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()

