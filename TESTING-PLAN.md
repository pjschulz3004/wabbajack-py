# UX / Functional Testing Plan

## Goal
Move beyond unit tests to actual user-experience testing: launch the app, interact with the GUI, verify workflows end-to-end.

## Available Tools

| Tool | Command | Best For |
|------|---------|----------|
| **Playwright** | `npx playwright test` | Automated E2E tests, headless or headed |
| **agent-browser** | via Chrome DevTools MCP | Interactive debugging, screenshots, Claude-driven testing |
| **Chromium** | `/usr/bin/chromium` | Manual inspection |
| **pytest + httpx** | existing | API-level integration tests (no browser) |

## Architecture

```
Frontend (Svelte 5)          Backend (FastAPI)
  localhost:5173   ─proxy─>   localhost:6969
  (vite dev server)           (uvicorn)
```

**Dev mode:** `cd frontend && npm run dev` + `.venv/bin/python -m wabbajack.cli serve --no-browser`
**Prod mode:** Frontend builds into static files served by FastAPI: `.venv/bin/python -m wabbajack.cli serve`

## Test Categories

### 1. Smoke Tests (does it even start?)
- [ ] Backend starts without errors on port 6969
- [ ] Frontend dev server starts on port 5173
- [ ] Root page loads, shows app shell with sidebar nav
- [ ] Version number appears in header (not "0.3.0" or blank)
- [ ] WebSocket connects (check browser console for errors)

### 2. Gallery (working, needs view mode testing)
- [ ] Gallery loads modlists from Wabbajack API
- [ ] Search filters by title
- [ ] Game filter dropdown works
- [ ] NSFW toggle hides/shows adult content
- [ ] Sort by name/updated/size works
- [ ] **NEW: View mode toggle** (grid → compact → list)
- [ ] Clicking a modlist opens the detail modal
- [ ] Detail modal shows: description, mod count, sizes, author, game badge

### 3. Settings
- [ ] Settings page loads without errors
- [ ] **Detected Games** shows only installed games (not 40+ "Not Found" entries)
- [ ] Workers slider adjusts value (1-32)
- [ ] Hash verification toggle works
- [ ] Save button persists settings (reload page, values retained)
- [ ] **Nexus Auth:** shows current login status
- [ ] **Nexus Auth:** set API key → shows logged in with username
- [ ] **Nexus Auth:** logout → clears status
- [ ] **Nexus Auth:** status survives page reload (file persistence)
- [ ] **Nexus Auth:** SSO/OAuth flow (may still fail — needs Nexus app registration)
- [ ] **Updates:** "Check for Updates" shows correct version and commit count
- [ ] **Updates:** Update button behavior (if updates available)

### 4. Install Flow (core workflow, currently broken)
- [ ] Can select a .wabbajack file (from gallery download or file picker)
- [ ] Install form shows: output dir, downloads dir, game dir, workers
- [ ] Start install → progress appears (phase, file count, speed)
- [ ] WebSocket streams live log messages
- [ ] Cancel button stops the install
- [ ] Install state persists across page reloads
- [ ] Error states display clearly (missing dirs, no Nexus key, etc.)

### 5. Profiles (currently placeholder)
- [ ] Profiles page loads
- [ ] (Currently empty — future work)

### 6. Downloads (currently placeholder)
- [ ] Downloads page loads
- [ ] (Currently empty — future work)

## Playwright Setup

```bash
cd /home/paul/gaming-fix/wabbajack-py

# Install Playwright + browsers (one-time)
npm init -y  # if no root package.json
npm install -D @playwright/test
npx playwright install chromium

# Create config
cat > playwright.config.ts << 'EOF'
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  use: {
    baseURL: 'http://localhost:6969',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  webServer: {
    command: '.venv/bin/python -m wabbajack.cli serve --no-browser --port 6969',
    port: 6969,
    reuseExistingServer: true,
    timeout: 10000,
  },
  projects: [
    { name: 'chromium', use: { channel: 'chromium' } },
  ],
});
EOF

# Create e2e directory
mkdir -p e2e
```

## Starter E2E Tests

```typescript
// e2e/smoke.spec.ts
import { test, expect } from '@playwright/test';

test('app loads with sidebar and header', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.sidebar')).toBeVisible();
  await expect(page.locator('.header')).toContainText(/0\.\d+\.\d+/);
});

test('gallery loads modlists', async ({ page }) => {
  await page.goto('/');
  await page.click('text=Gallery');
  await expect(page.locator('.mod-card')).toHaveCount({ minimum: 1 }, { timeout: 15000 });
});

test('gallery view toggle works', async ({ page }) => {
  await page.goto('/');
  await page.click('text=Gallery');
  await page.waitForSelector('.mod-card');

  // Switch to compact
  await page.click('[aria-label="Compact view"]');
  await expect(page.locator('.grid-compact')).toBeVisible();

  // Switch to list
  await page.click('[aria-label="List view"]');
  await expect(page.locator('.grid-list')).toBeVisible();
});

test('settings shows only installed games', async ({ page }) => {
  await page.goto('/');
  await page.click('text=Settings');
  // Should NOT see "Not Found" badges
  await expect(page.locator('text=Not Found')).toHaveCount(0);
});

test('settings nexus auth shows status', async ({ page }) => {
  await page.goto('/');
  await page.click('text=Settings');
  await expect(page.locator('text=Nexus Mods')).toBeVisible();
});

test('version is not stale default', async ({ page }) => {
  await page.goto('/');
  // Should show 0.4.0, not 0.3.0
  await expect(page.locator('header')).not.toContainText('0.3.0');
});
```

## agent-browser Approach (interactive, Claude-driven)

For exploratory testing within Claude sessions:

```bash
# Start the backend first
.venv/bin/python -m wabbajack.cli serve --no-browser --port 6969 &

# Then use Chrome DevTools MCP tools:
# navigate_page → take_screenshot → click → fill → evaluate_script
```

This lets Claude navigate the app, take screenshots, fill forms, and verify visual output interactively. Good for:
- Visual regression checking after changes
- Testing flows that are hard to automate (file dialogs, WebSocket streams)
- Exploratory testing with screenshot evidence

## Testing Priority for Tomorrow

1. **Set up Playwright** (one-time, 10 min)
2. **Smoke tests** — verify the app starts and basic nav works
3. **Gallery tests** — the most functional page, verify view modes
4. **Settings tests** — verify all the fixes from today (auth, games, version)
5. **Install flow** — this is where the real bugs are, needs manual exploration first
6. **Screenshot baseline** — capture current state of every page for regression comparison

## Known Issues to Verify Fixed
- [ ] Nexus always showing "logged out" → should persist via file now
- [ ] Version showing "0.3.0" → should show "0.4.0" from OpenAPI
- [ ] Games page showing 40+ "Not Found" → should only show installed
- [ ] Update check broken → git commands fixed
- [ ] Hardcoded Jackify path → removed
