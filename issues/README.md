# GitHub Issues for CryptoMarket-Dashboard

This directory contains issue templates for problems found during code review.

## How to Use

1. **Copy issue content**: Open each `.md` file and copy its content
2. **Create GitHub issue**: Go to your repository's Issues tab
3. **Paste and submit**: Create a new issue and paste the content

## Issue List

1. **001-duplicate-docstring.md** - Bug: Duplicate docstring in help_command (Low priority)
2. **002-memory-leak-processed-updates.md** - Bug: Potential memory leak (Medium priority)
3. **003-race-condition-dashboard-owners.md** - Bug: Race condition in dashboard ownership (Medium priority)
4. **004-stale-process-cleanup.md** - Bug: Stale process cleanup (Medium priority)
5. **005-input-validation-missing.md** - Security: Missing input validation (Medium priority)
6. **006-telegram-message-length-limit.md** - Bug: Message length limit exceeded (Medium priority)
7. **007-no-pagination-coins-command.md** - Enhancement: Add pagination (Low priority)
8. **008-synchronous-data-loading.md** - Performance: Blocking event loop (Medium priority)
9. **009-hardcoded-magic-numbers.md** - Code Quality: Magic numbers (Low priority)
10. **010-bare-except-clauses.md** - Code Quality: Bare except clauses (Medium priority)
11. **011-missing-type-hints.md** - Code Quality: Missing type hints (Low priority)
12. **012-no-rate-limiting.md** - Enhancement: Rate limiting (Medium priority)
13. **013-correlation-numerical.md** - Feature: Correlation between 2 coins (numerical)
14. **014-correlation-chart.md** - Feature: Correlation between 2 coins (with chart image)
15. **015-instant-price.md** - Feature: Instant price of coins
16. **016-1year-chart-image.md** - Feature: 1 year chart image of coins
17. **017-timeframe-summary.md** - Feature: 1d, 1w, 1m and 1y summary for coins
18. **018-telegram-command-bar.md** - Enhancement: Show command bar in Telegram using "/" button (High priority)
19. **019-enhance-info-command.md** - Enhancement: Show full coin details in /info command (High priority)
20. **020-bot-bio-and-about-button.md** - Enhancement: Add bot bio information and "What's this bot for?" button (Medium priority)
21. **021-fix-about-button-behavior.md** - Bug: Fix "What's this bot for?" button behavior (Medium priority)
22. **022-add-about-to-command-bar.md** - Enhancement: Add "What's this bot for?" to Telegram command bar (Low priority)
23. **023-help-menu-simplify-buttons.md** - Bug: Help menu should only show 2 buttons (Medium priority) ✅ Fixed
24. **024-about-button-edit-message.md** - Bug: About button should edit message, not send new (Medium priority) ✅ Fixed
25. **025-about-screen-single-button.md** - Bug: About screen should only show back button (Medium priority) ✅ Fixed
26. **026-add-info-button-to-menus.md** - Enhancement: Add Info button to menus (Medium priority)
27. **027-reduce-emojis-in-data-display.md** - Enhancement: Reduce emojis in data display - too crowded (Medium priority)

## Priority Guide

- **High**: Critical bugs, security vulnerabilities, data loss risks
- **Medium**: Performance issues, potential bugs, important enhancements
- **Low**: Code quality, minor improvements, nice-to-have features

## Creating Issues via GitHub CLI (Optional)

If you install GitHub CLI (`gh`), you can create issues directly:

```bash
# Install GitHub CLI first, then:
gh issue create --title "Bug: Duplicate docstring" --body-file issues/001-duplicate-docstring.md
```

## Creating Issues via GitHub Web UI

1. Go to: https://github.com/NimaArnar/CryptoMarket-Dashboard/issues/new
2. Copy the content from any `.md` file in this directory
3. Paste into the issue body
4. Set appropriate labels (bug, enhancement, security, etc.)
5. Submit


