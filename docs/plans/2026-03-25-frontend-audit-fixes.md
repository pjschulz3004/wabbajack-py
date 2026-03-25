# Frontend Audit Fixes Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 34 issues found by the impeccable frontend audit (4 critical, 8 high, 14 medium, 8 low).

**Architecture:** All fixes are in `frontend/src/`. No backend changes needed except H3 (WS message format mismatch).

**Tech Stack:** Svelte 5, TypeScript, CSS custom properties

---

### Task 1: LogViewer Virtual Scrolling (C1 -- CRITICAL)

**Files:**
- Modify: `frontend/src/lib/components/LogViewer.svelte`

Replace `{#each filteredLogs}` full DOM render with a windowed approach:
- Calculate visible range from `scrollTop` and container height
- Only render visible lines + 20-line buffer above/below
- Use a spacer div for total scroll height
- Keep auto-scroll behavior

This is the single biggest perf issue -- 50K DOM nodes will freeze the browser.

---

### Task 2: Fix Store Subscription Leaks (C2, C3 -- CRITICAL)

**Files:**
- Modify: `frontend/src/routes/Install.svelte`
- Modify: `frontend/src/routes/Downloads.svelte`

Install.svelte lines 18-26: Replace manual `.subscribe()` calls with Svelte `$` prefix auto-subscriptions:
```svelte
// BEFORE (leaks):
let currentLogs = $state<any[]>([]);
logs.subscribe(v => currentLogs = v);

// AFTER (correct):
// Use $logs directly in template, or:
let currentLogs = $derived($logs);
```

Downloads.svelte lines 23-28: Same pattern fix.

Also remove unused `import { get } from 'svelte/store'` from Install.svelte line 2.

---

### Task 3: Fix Pause/Cancel WS Message Format (H3 -- HIGH)

**Files:**
- Modify: `frontend/src/routes/Install.svelte`

Lines 76-86 send `{type: 'command', action: 'pause'}` but backend `ws.py` VALID_COMMANDS checks `msg.get("type")` directly. Fix frontend to match backend protocol:
```typescript
// BEFORE:
sendWs({ type: 'command', action: 'pause' });

// AFTER:
sendWs({ type: 'pause' });
sendWs({ type: 'resume' });
sendWs({ type: 'cancel' });
```

---

### Task 4: Fix Silent Install Failure (H2 -- HIGH)

**Files:**
- Modify: `frontend/src/routes/Install.svelte`

Line 69: Add user-visible error state instead of `console.error`:
```typescript
let installError = $state('');

async function startInstall() {
  installError = '';
  submitting = true;
  try {
    await api.startInstall({...});
    showForm = false;
  } catch (err: any) {
    installError = err.message ?? 'Failed to start installation';
  } finally {
    submitting = false;
  }
}
```

Add error banner in template below the form.

---

### Task 5: Focus Indicators + Contrast Fix (C4, H5, H6 -- CRITICAL/HIGH)

**Files:**
- Modify: `frontend/src/app.css`

Add global focus-visible styles:
```css
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

Fix contrast ratio -- bump `--text-secondary` from `#8888a0` to `#9898b0` (4.6:1 on bg-secondary, 5.2:1 on bg-primary):
```css
--text-secondary: #9898b0;
```

---

### Task 6: ARIA Landmarks + Keyboard Accessibility (H1, H8, M6-M9)

**Files:**
- Modify: `frontend/src/App.svelte` -- add `aria-current="page"` to active nav, `aria-label` on nav
- Modify: `frontend/src/routes/Downloads.svelte` -- add `role="button"`, `tabindex="0"`, `onkeydown` to `<th>` elements
- Modify: `frontend/src/lib/components/LogViewer.svelte` -- add `aria-pressed` to filter buttons
- Modify: `frontend/src/routes/Gallery.svelte` -- add `<label>` for search input and select (visually hidden)
- Modify: `frontend/src/routes/Downloads.svelte` -- add `<label>` for search input

---

### Task 7: Virtualize Downloads Table (H7 -- HIGH)

**Files:**
- Modify: `frontend/src/routes/Downloads.svelte`

Same windowed approach as LogViewer. Calculate visible rows from scroll position, render only visible + buffer. Use sticky header. 5667 rows should only render ~50 at a time.

---

### Task 8: Wire Gallery Card to Install Flow (H4 -- HIGH)

**Files:**
- Modify: `frontend/src/routes/Gallery.svelte`
- Modify: `frontend/src/App.svelte`

When user clicks a ModCard, navigate to Install page with the modlist pre-selected. Either:
- Export a `navigateTo` function from App.svelte
- Use a shared store for selected modlist
- Pass callback through props

---

### Task 9: Performance + Responsive Polish (M1, M2, M4, M5)

**Files:**
- Modify: `frontend/src/lib/components/ProgressBar.svelte` -- use `transform: scaleX()` instead of `width`
- Modify: `frontend/src/routes/Install.svelte` -- add `@media (max-width: 900px)` breakpoint for form grid
- Modify: `frontend/src/routes/Gallery.svelte` -- add sub-768px breakpoint accounting for sidebar

---

### Task 10: Cleanup + Minor Fixes (M10, M11, L1-L8)

**Files:**
- Modify: `frontend/src/App.svelte` -- fix version to v0.3.0, add `aria-hidden` to decorative SVGs
- Modify: `frontend/src/routes/Install.svelte` -- remove unused `get` import
- Modify: `frontend/src/routes/Downloads.svelte` -- replace hard-coded colors with tokens (L7, L8)
- Modify: `frontend/src/app.css` -- add Firefox scrollbar styles (`scrollbar-color`, `scrollbar-width`)
- Consolidate duplicate `@keyframes pulse` and `@keyframes shimmer` into app.css

---

## Execution Order

Tasks 1-4 are **immediate** (critical + high blockers).
Task 5 is **immediate** (accessibility, one-file change).
Tasks 6-8 are **short-term** (accessibility + UX).
Tasks 9-10 are **medium-term** (polish).

Estimated: 10 tasks, ~1-2 hours with parallel agents for independent tasks.
