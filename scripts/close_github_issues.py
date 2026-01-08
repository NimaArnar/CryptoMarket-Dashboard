#!/usr/bin/env python3
"""
Script to close GitHub issues that have been fixed.

Usage:
    python scripts/close_github_issues.py
"""

import os
import sys

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
FIXED_ISSUES = [19, 23, 24, 25, 26, 27]

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
    print("🔒 Closing Fixed GitHub Issues")
    print("=" * 50)
    
    # Get token
    token = get_github_token()
    print(f"✅ Token found\n")
    
    print(f"📋 Closing {len(FIXED_ISSUES)} issue(s)...")
    print("=" * 50)
    
    closed = 0
    failed = 0
    
    for issue_num in FIXED_ISSUES:
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
    print(f"   📋 Total: {len(FIXED_ISSUES)}")
    
    if closed > 0:
        print(f"\n🎉 Successfully closed {closed} issue(s)!")


if __name__ == "__main__":
    main()
