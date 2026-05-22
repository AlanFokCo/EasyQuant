# Release Notes — v1.0.3

**Release Date:** 2026-05-23

## Overview

This release focuses on Web Strategy Studio enhancements, security hardening, bug fixes, and documentation improvements. It includes significant UX optimizations for the browser-based strategy development platform, fixes for eqlib financial calculations, and comprehensive documentation updates.

---

## Web Strategy Studio

### New Features

- **Auto-logout on authentication failure**: Users are automatically logged out when JWT token expires or becomes invalid (401 response), with seamless redirect to login page
- **Preset users configuration**: Add support for configuring preset users via `users.yaml` file (recommended) or `EQ_PRESET_USERS` environment variable
- **Smart polling for history panel**: Backtest history list only polls when there are active (running/queued) runs, reducing unnecessary API calls

### UX Improvements

- **Fixed sidebar navigation**: Navigation buttons (history, compare, data) now respond correctly to clicks
- **Removed registration page**: Simplified login flow — users must be pre-configured by server
- **Loading indicators**: Added loading states for login button, stock search, and backtest runs
- **Hover states**: Enhanced button hover effects with visual feedback
- **Translated labels**: Key UI labels translated to Chinese (e.g., "初始资金", "使用本地数据")
- **Accessibility**: Added `aria-live="polite"` for toast notifications, improved keyboard navigation

### Bug Fixes

- **Race condition in run_queue.py**: Fixed semaphore acquisition order to prevent queue corruption
- **Stream hub buffer operations**: Added async lock for concurrent buffer access
- **Stock picker search cancellation**: AbortController cancels previous requests when new search starts
- **Unmount state handling**: Added `mountedRef` to prevent setState on unmounted components
- **JWT leak in URLs**: Fixed JWT token appearing in URLs when opening reports in new tabs

### Security

- **Harden authentication**: Improved JWT handling and token validation
- **Environment variable leak**: Filter sensitive variables (`EQ_JWT_SECRET`, `EQ_ADMIN_PASSWORD`) from subprocess environment
- **Static reports mount removed**: Reports now served through authenticated API endpoint only

---

## eqlib Core

### Bug Fixes

- **NaN handling in financial calculations**: Added `pd.isna()` and `np.isfinite()` checks in:
  - Sharpe ratio calculation (returns 0 when std is NaN or ≤ 0)
  - Sortino ratio calculation
  - Max drawdown calculation
  - Beta calculation
- **Index data fetch alignment**: Fixed alignment between index returns and strategy returns

---

## Documentation

### Updates

- **README (English & Chinese)**: Added Web Studio section, improved Quick Start guidance (PyPI vs source install)
- **User Guide**: Added Web Studio alternative for browser-based users
- **Tutorials**: Added Web Studio as learning path option
- **FAQ**: Added 6 new Web Studio questions (login, deployment, troubleshooting)
- **Web Studio Docs**: Updated authentication section with auto-logout mechanism and preset users configuration

### GitHub Pages Enhancements

- **New hero card**: Added "Web 工作室" (Web Studio) card on homepage
- **Card icons**: Added emoji icons for each hero card (🚀, 📖, 🎓, 🌐, 🔧)
- **Hover effects**: Enhanced card hover with elevation animation and shadow
- **Search shortcut hint**: Shows "⌘K 快捷搜索" when search input focused
- **Focus-visible states**: Improved accessibility for keyboard navigation
- **Back-to-top animation**: Added fade-in-up animation
- **Navigation indicator**: Added blue accent bar for active navigation items
- **Responsive layout**: Optimized for mobile devices
- **Print styles**: Added print-friendly output

---

## CI/CD

- **Studio Tests workflow**: Fixed ruff lint errors, added `@types/node` for frontend TypeScript
- **Backend pytest**: Stabilized asyncio loop handling and queue isolation tests
- **bcrypt compatibility**: Replaced passlib with bcrypt directly for bcrypt 4.x compatibility

---

## Installation

```bash
pip install easyquant-eqlib --upgrade
```

Or from source:

```bash
git clone https://github.com/AlanFokCo/EasyQuant.git
cd EasyQuant
pip install .
```

---

## Upgrade Notes

### Web Studio Users

If you're using Web Strategy Studio:

1. **Update preset users**: Create `web_strategy_studio/backend/users.yaml` to configure users:
   ```yaml
   preset_users:
     - username: your_username
       password: your_password
   ```

2. **JWT secret for production**: Set stable JWT secret to prevent logout after restart:
   ```bash
   export EQ_JWT_SECRET="your-secure-random-key"
   ```

3. **Admin password**: Change default admin password:
   ```bash
   export EQ_ADMIN_PASSWORD="your-secure-password"
   ```

### eqlib Users

No breaking changes. NaN handling improvements ensure stable output for edge cases (empty data, zero volatility).

---

## Full Changelog

See [v1.0.2...v1.0.3](https://github.com/AlanFokCo/EasyQuant/compare/v1.0.2...v1.0.3)

---

## Contributors

- @AlanFokCo
- @copilot (GitHub Copilot assisted fixes)
- Claude Opus 4.7 (AI-assisted development)