# Installing Git on Windows

## Quick Installation

### Option 1: Download Git for Windows (Recommended)

1. **Download Git:**
   - Go to: https://git-scm.com/download/win
   - The download will start automatically
   - Or click "Click here to download" if it doesn't start

2. **Run the Installer:**
   - Double-click the downloaded file (e.g., `Git-2.43.0-64-bit.exe`)
   - Click "Next" through the installation wizard
   - **Recommended settings:**
     - Use default editor (or choose your preferred editor)
     - Use Git from the command line and also from 3rd-party software
     - Use bundled OpenSSH
     - Use the OpenSSL library
     - Checkout Windows-style, commit Unix-style line endings
     - Use MinTTY (the default terminal of MSYS2)
     - Default (fast-forward or merge)
     - Git Credential Manager
     - Enable file system caching
     - Enable symbolic links

3. **Complete Installation:**
   - Click "Install"
   - Wait for installation to complete
   - Click "Finish"

4. **Restart PowerShell:**
   - Close your current PowerShell window
   - Open a new PowerShell window
   - Verify installation: `git --version`

### Option 2: Install via Winget (Windows Package Manager)

If you have Windows 10/11 with winget:

```powershell
winget install --id Git.Git -e --source winget
```

### Option 3: Install via Chocolatey

If you have Chocolatey installed:

```powershell
choco install git
```

## Verify Installation

After installation, open a **new PowerShell window** and run:

```powershell
git --version
```

You should see something like: `git version 2.43.0.windows.1`

## After Installation

Once Git is installed, you can proceed with the GitHub setup:

```powershell
cd C:\Users\Nima\Desktop\CryptoDashboard
git init
git add .
git commit -m "Initial commit: Crypto Market Cap Dashboard"
git remote add origin https://github.com/NimaArnar/CryptoMarket-Dashboard.git
git branch -M main
git push -u origin main
```

## Troubleshooting

### "Git is not recognized" after installation
- **Solution**: Close and reopen PowerShell/Command Prompt
- If still not working, restart your computer

### Need to add Git to PATH manually
- Usually not needed, but if required:
  1. Find Git installation (usually `C:\Program Files\Git\cmd`)
  2. Add it to System Environment Variables → Path

### Authentication Issues
- Use Personal Access Token instead of password
- Generate at: https://github.com/settings/tokens

