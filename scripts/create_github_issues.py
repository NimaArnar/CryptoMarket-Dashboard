#!/usr/bin/env python3
"""
Script to create GitHub issues from markdown templates.

Usage:
    python scripts/create_github_issues.py

Requirements:
    - GitHub Personal Access Token with 'repo' scope
    - requests library: pip install requests
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

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

# Issue labels mapping
LABEL_MAPPING = {
    "bug": ["bug"],
    "security": ["security", "bug"],
    "enhancement": ["enhancement"],
    "performance": ["performance", "enhancement"],
    "code quality": ["enhancement", "good first issue"],
}


def get_github_token() -> str:
    """Get GitHub token from environment variable."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        token = os.getenv("GH_TOKEN")
    if not token:
        print("❌ Error: GitHub token not found!")
        print("\nPlease set one of these environment variables:")
        print("  - GITHUB_TOKEN")
        print("  - GH_TOKEN")
        print("\nTo get a token:")
        print("  1. Go to: https://github.com/settings/tokens")
        print("  2. Click 'Generate new token (classic)'")
        print("  3. Select 'repo' scope")
        print("  4. Copy the token")
        print("\nThen set it:")
        print("  Windows PowerShell: $env:GITHUB_TOKEN='your-token'")
        print("  Windows CMD: set GITHUB_TOKEN=your-token")
        print("  Linux/Mac: export GITHUB_TOKEN='your-token'")
        sys.exit(1)
    return token


def parse_issue_file(file_path: Path) -> Dict[str, str]:
    """Parse markdown issue file and extract title, body, and labels."""
    content = file_path.read_text(encoding="utf-8")
    
    # Extract title (first line after #)
    lines = content.split("\n")
    title = None
    body_start = 0
    
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_start = i + 1
            break
    
    if not title:
        # Fallback: use filename
        title = file_path.stem.replace("-", " ").title()
    
    # Extract body (everything after title)
    body = "\n".join(lines[body_start:]).strip()
    
    # Determine labels from content
    labels = []
    content_lower = content.lower()
    
    if "bug:" in content_lower or "bug" in title.lower():
        labels.append("bug")
    if "security" in content_lower or "security" in title.lower():
        labels.append("security")
    if "enhancement" in content_lower or "enhancement" in title.lower():
        labels.append("enhancement")
    if "performance" in content_lower:
        labels.append("performance")
    if "code quality" in content_lower:
        labels.append("good first issue")
    
    # Determine priority from content
    if "high priority" in content_lower or "high severity" in content_lower:
        labels.append("priority: high")
    elif "medium priority" in content_lower or "medium severity" in content_lower:
        labels.append("priority: medium")
    elif "low priority" in content_lower or "low severity" in content_lower:
        labels.append("priority: low")
    
    return {
        "title": title,
        "body": body,
        "labels": labels
    }


def create_issue(token: str, title: str, body: str, labels: List[str]) -> Dict:
    """Create a GitHub issue via API."""
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    
    data = {
        "title": title,
        "body": body,
        "labels": labels
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 201:
        return response.json()
    else:
        error_msg = f"Failed to create issue: {response.status_code}"
        try:
            error_data = response.json()
            if "message" in error_data:
                error_msg += f"\n{error_data['message']}"
        except:
            error_msg += f"\n{response.text}"
        raise Exception(error_msg)


def get_existing_issues(token: str) -> List[str]:
    """Get list of existing issue titles to avoid duplicates."""
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/issues"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    params = {"state": "all", "per_page": 100}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        issues = response.json()
        return [issue["title"] for issue in issues if "pull_request" not in issue]
    return []


def main():
    """Main function to create all issues."""
    print("🚀 GitHub Issue Creator")
    print("=" * 50)
    
    # Get token
    token = get_github_token()
    print(f"✅ Token found (length: {len(token)})")
    
    # Get issues directory
    issues_dir = Path(__file__).parent.parent / "issues"
    if not issues_dir.exists():
        print(f"❌ Issues directory not found: {issues_dir}")
        sys.exit(1)
    
    # Get all issue files
    issue_files = sorted(issues_dir.glob("*.md"))
    issue_files = [f for f in issue_files if f.name != "README.md"]
    
    if not issue_files:
        print(f"❌ No issue files found in {issues_dir}")
        sys.exit(1)
    
    print(f"\n📋 Found {len(issue_files)} issue file(s)")
    
    # Get existing issues to avoid duplicates
    print("\n🔍 Checking existing issues...")
    try:
        existing_titles = get_existing_issues(token)
        print(f"   Found {len(existing_titles)} existing issue(s)")
    except Exception as e:
        print(f"⚠️  Warning: Could not check existing issues: {e}")
        existing_titles = []
    
    # Create issues
    print("\n📝 Creating issues...")
    print("=" * 50)
    
    created = 0
    skipped = 0
    failed = 0
    
    for issue_file in issue_files:
        try:
            issue_data = parse_issue_file(issue_file)
            title = issue_data["title"]
            body = issue_data["body"]
            labels = issue_data["labels"]
            
            # Check if already exists
            if title in existing_titles:
                print(f"⏭️  Skipped: {title} (already exists)")
                skipped += 1
                continue
            
            # Create issue
            print(f"📌 Creating: {title}")
            result = create_issue(token, title, body, labels)
            issue_url = result.get("html_url", "N/A")
            issue_number = result.get("number", "N/A")
            print(f"   ✅ Created: #{issue_number} - {issue_url}")
            created += 1
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Summary:")
    print(f"   ✅ Created: {created}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📋 Total: {len(issue_files)}")
    
    if created > 0:
        print(f"\n🎉 Successfully created {created} issue(s)!")
        print(f"   View them at: https://github.com/{REPO_OWNER}/{REPO_NAME}/issues")


if __name__ == "__main__":
    main()

