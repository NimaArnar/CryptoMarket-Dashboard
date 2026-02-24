#!/usr/bin/env python3
"""
Script to close GitHub issues that have been fixed.

Usage:
    python scripts/close_github_issues.py [issue_num ...]
    Example: python scripts/close_github_issues.py 13 14

Token: Set GITHUB_TOKEN or GH_TOKEN in environment, or put GITHUB_TOKEN=... in .env in project root.
"""

import os
import sys
from pathlib import Path

# Load .env from project root if present (so token can be in .env without exporting)
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

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' library not installed.")
    print("   Install it with: pip install requests")
    sys.exit(1)

# GitHub repository details
REPO_OWNER = "NimaArnar"
REPO_NAME = "CryptoMarket-Dashboard"
GITHUB_API_BASE = "https://api.github.com"

# Issues that were fixed
# NOTE: 15 = Instant price feature for Telegram bot
# NOTE: 16 = Chart image feature (1w/1m/1y price & index charts) for Telegram bot
# NOTE: 17 = Timeframe summary (1d/1w/1m/1y) feature for Telegram bot
# NOTE: 34 = Add Chart/Summary buttons to Data Queries menu (Telegram bot)
# NOTE: 35 = Default all single-coin actions to BTC instead of ETH (Telegram bot)
# NOTE: 36 = Remove ETH-specific Price/Info buttons from menus (Telegram bot)
# NOTE: 37 = Back to Data Queries button on List All Coins (Telegram bot)
# NOTE: 38 = Resend Data Queries menu as latest message (Telegram bot)
# NOTE: 13 = Correlation between 2 coins (numerical) - /corr default BTC/ETH
# NOTE: 14 = Correlation with chart image (scatter plot)
FIXED_ISSUES = [13, 14, 15, 16, 17, 19, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38]

# Commit hash (will be updated)
COMMIT_HASH = "HEAD"


def get_github_token() -> str:
    """Get GitHub token from environment variable."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        token = os.getenv("GH_TOKEN")
    if not token:
        print("❌ Error: GitHub token not found!")
        print("\nPlease set GITHUB_TOKEN environment variable.")
        sys.exit(1)
    return token


def close_issue(token: str, issue_number: int, commit_hash: str) -> bool:
    """Close a GitHub issue via API."""
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    
    # Close the issue with a comment about the fix
    data = {
        "state": "closed",
        "state_reason": "completed"
    }
    
    response = requests.patch(url, headers=headers, json=data)
    
    if response.status_code == 200:
        # Add a comment about the fix
        comment_url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}/comments"
        comment_data = {
            "body": f"✅ Fixed in latest commit\n\nThis issue has been resolved and the fix has been committed."
        }
        requests.post(comment_url, headers=headers, json=comment_data)
        return True
    else:
        error_msg = f"Failed to close issue #{issue_number}: {response.status_code}"
        try:
            error_data = response.json()
            if "message" in error_data:
                error_msg += f"\n{error_data['message']}"
        except:
            error_msg += f"\n{response.text}"
        print(f"   ❌ {error_msg}")
        return False


def main():
    """Main function to close all fixed issues."""
    # Optional: close only specific issues e.g. python close_github_issues.py 37 38
    if len(sys.argv) > 1:
        try:
            issues_to_close = [int(x) for x in sys.argv[1:]]
        except ValueError:
            print("Usage: python close_github_issues.py [issue_num ...]")
            print("Example: python close_github_issues.py 37 38")
            sys.exit(1)
    else:
        issues_to_close = FIXED_ISSUES

    print("🔒 Closing Fixed GitHub Issues")
    print("=" * 50)
    
    # Get token
    token = get_github_token()
    print(f"✅ Token found\n")
    
    print(f"📋 Closing {len(issues_to_close)} issue(s)...")
    print("=" * 50)
    
    closed = 0
    failed = 0
    
    for issue_num in issues_to_close:
        print(f"🔒 Closing issue #{issue_num}...", end=" ")
        try:
            if close_issue(token, issue_num, COMMIT_HASH):
                print(f"✅ Closed")
                print(f"   https://github.com/{REPO_OWNER}/{REPO_NAME}/issues/{issue_num}")
                closed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Error: {e}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Summary:")
    print(f"   ✅ Closed: {closed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📋 Total: {len(issues_to_close)}")
    
    if closed > 0:
        print(f"\n🎉 Successfully closed {closed} issue(s)!")


if __name__ == "__main__":
    main()
