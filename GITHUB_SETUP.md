# GitHub Setup Instructions

Follow these steps to push your CryptoDashboard project to GitHub.

## Prerequisites

1. **Git installed** on your computer
   - Check if installed: `git --version`
   - If not installed, download from: https://git-scm.com/downloads

2. **GitHub account**
   - Create one at: https://github.com

## Step-by-Step Instructions

### Step 1: Create a New Repository on GitHub

1. Go to https://github.com and sign in
2. Click the **"+"** icon in the top right corner
3. Select **"New repository"**
4. Fill in the details:
   - **Repository name**: `CryptoDashboard` (or your preferred name)
   - **Description**: "Interactive cryptocurrency market cap dashboard using CoinGecko API"
   - **Visibility**: Choose **Public** or **Private**
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
5. Click **"Create repository"**

### Step 2: Initialize Git in Your Project (if not already done)

Open PowerShell in your project directory and run:

```powershell
cd C:\Users\Nima\Desktop\CryptoDashboard
git init
```

### Step 3: Add All Files to Git

```powershell
git add .
```

This will add all files except those in `.gitignore` (cache, logs, etc.)

### Step 4: Create Your First Commit

```powershell
git commit -m "Initial commit: Crypto Market Cap Dashboard"
```

### Step 5: Connect to GitHub Repository

Replace `YOUR_USERNAME` with your actual GitHub username:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/CryptoDashboard.git
```

### Step 6: Push to GitHub

```powershell
git branch -M main
git push -u origin main
```

You'll be prompted for your GitHub username and password (or personal access token).

### Step 7: Verify

Go to your GitHub repository page and verify all files are uploaded correctly.

## Important Notes

### Authentication

If you're asked for credentials:
- **Username**: Your GitHub username
- **Password**: Use a **Personal Access Token** (not your GitHub password)
  - Generate one at: https://github.com/settings/tokens
  - Select scopes: `repo` (full control of private repositories)

### What Gets Uploaded

The `.gitignore` file ensures these are **NOT** uploaded:
- `cg_cache/` - API cache files
- `logs/` - Log files
- `market_caps Data/` - Exported Excel files
- `__pycache__/` - Python cache
- Temporary files

### What Gets Uploaded

These files **WILL** be uploaded:
- `crypto_market_cap_dashboard.py` - Main application
- `requirements.txt` - Dependencies
- `README.md` - Documentation
- `.gitignore` - Git ignore rules
- `GITHUB_SETUP.md` - This file

## Future Updates

After making changes to your code:

```powershell
# Check what changed
git status

# Add changed files
git add .

# Commit changes
git commit -m "Description of your changes"

# Push to GitHub
git push
```

## Troubleshooting

### "Repository not found" error
- Check that the repository name matches exactly
- Verify you have access to the repository
- Make sure you're using the correct username

### "Authentication failed" error
- Use a Personal Access Token instead of password
- Make sure the token has `repo` scope

### "Large files" error
- The cache files are already in `.gitignore`
- If you see this error, check that `.gitignore` is working correctly

### Want to remove a file from Git (but keep locally)
```powershell
git rm --cached filename
git commit -m "Remove file from Git"
```

## Optional: Add a License

If you want to add a license file:

1. Go to your repository on GitHub
2. Click "Add file" → "Create new file"
3. Name it `LICENSE`
4. GitHub will suggest templates - choose one (e.g., MIT License)
5. Commit the file

## Optional: Add Topics/Tags

On your GitHub repository page:
1. Click the gear icon next to "About"
2. Add topics like: `python`, `dash`, `cryptocurrency`, `dashboard`, `coingecko`, `data-visualization`

## Done! 🎉

Your project is now on GitHub and ready to share!

