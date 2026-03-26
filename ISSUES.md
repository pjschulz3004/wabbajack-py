# Issues & Redesign Notes (2026-03-26)

Source: Paul's full review after hands-on testing.

## Core Insight

**Everything hinges on profiles.** The UX should flow from profiles as the central organizing concept: install a modlist → profile is created → mods/downloads/settings live under that profile. Right now profiles are an afterthought (CLI flag only), and every other page suffers because of it.

---

## 1. Profiles (the linchpin)

**Current state:** Useless. Only a `--profile` CLI flag. No GUI management.

**What profiles should be:**
- Central hub of the app. This is where installed modlists show up.
- Create profiles from GUI (manual or auto-created on modlist install)
- Each profile = one modlist install, tied to one game
- Profile view shows: mod list, install status, mod info, links, descriptions
- Switch between profiles, manage them, delete them
- Per-profile settings (output dir, downloads dir, game dir)

**Why this matters:** Settings, downloads, mods view, install status all become per-profile. Without this, the app has no coherent navigation model.

## 2. Settings Page

**Problems:**
- Default output/downloads/game directories don't make sense for a multi-game tool
- These should be per-profile, not global
- Workers setting exists but isn't connected to anything (workers chosen at install time)
- Hash verification toggle is fine as a global setting

**Redesign:**
- Global settings: theme, Nexus auth, hash verification, default workers, check for updates
- Per-profile settings: output dir, downloads dir, game dir (lives on profile page, not settings)
- Remove game-specific paths from global settings

## 3. Nexus Authentication (broken)

**Symptoms:**
- Always shows "logged out" even after auth attempt
- OAuth flow fails: "application ID was invalid" / "5 minutes timeout"
- This was supposedly fixed in improve session 1 (cycle 5) but is still broken

**Note:** API key entry might still work. OAuth is the broken path. Need to verify the Nexus API application ID and callback flow.

## 4. Detected Games

**Problem:** Shows a giant list of games NOT found alongside the few that ARE found. Noisy and unhelpful.

**Fix:** Only show found games. Or collapse not-found into an expandable section. The user cares about what's available, not what isn't.

## 5. Updates (broken)

**Symptoms:**
- Header shows "WabbajackPy 3.1" (wrong version string)
- Updates page shows "0.3.0" initially
- "Check for updates" shows correct version + last 24 commits
- Update button doesn't actually update anything

**Expected:** Check for updates → compare local vs GitHub tag → offer to pull + restart.

## 6. Install (broken)

**Problems:**
- Still looking for .wabbajack files in `~/Jackify/` directory (hardcoded? legacy path?)
- All modlist files should live within the tool's own data structure
- No clear "where does this tool store its data?" answer
- Install should: pick modlist (from gallery download or local file) → pick/create profile → set dirs → go

## 7. Downloads Page

**Current state:** Unclear what it even shows.

**Redesign:**
- Active/queued downloads with progress (this is the "during install" view)
- Per-profile mod list with: mod name, archive name, source (Nexus/MediaFire/etc.), link to source page, mod description (auto-fetched from Nexus API)
- This is basically the profile's "mods" tab

## 8. Gallery

**Working mostly fine.** Issues:
- Only large card view. Wants: compact/list view option, smaller cards
- Info boxes have minimal info for most modlists (short blurbs)
- Some modlists have full wikis — surface more of that content
- Add view mode toggle (grid large / grid compact / list)

## 9. Naming

**Problem:** "wabbajack-py" uses someone else's brand name. Paul doesn't want to steal it.

**Action needed:** Pick a new name. Something that conveys the same concept (modlist installer for Linux) without using "Wabbajack" directly. Paul's working name was "Wobberjack" but that's still too close.

**Action:** Gather name candidates during next `/improve` session. Consider: Elder Scrolls lore references, Linux modding concepts, mythology, wordplay. Present shortlist for Paul to pick.

## 10. Installation Location

**Unanswered:** Where does this tool itself install? Where does it store its data (profiles, downloads, settings)? Needs a clear XDG-compliant data directory structure.

**Proposal:**
```
~/.local/share/wabbajack-py/     # (or new name)
  settings.json                   # global settings
  profiles/
    twisted-skyrim/
      profile.json                # game, dirs, modlist ref
      mods.json                   # mod metadata cache
      state.json                  # install progress
  modlists/                       # downloaded .wabbajack files
  cache/                          # extraction cache
```

---

## Priority Order

1. **Profiles redesign** — everything else flows from this
2. **Naming** — pick a name before more work goes in
3. **Nexus auth fix** — can't install without downloads
4. **Install flow** — wire up to profiles, remove Jackify paths
5. **Settings cleanup** — split global vs per-profile
6. **Downloads/mods view** — per-profile mod list with metadata
7. **Gallery improvements** — view modes, richer info
8. **Updates** — fix version detection and actual update mechanism
9. **Detected games** — only show found games
