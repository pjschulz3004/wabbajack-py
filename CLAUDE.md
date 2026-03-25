# wabbajack-py

Cross-platform Wabbajack modlist installer with web GUI. Python backend (FastAPI), Svelte 5 frontend.

## Design Context

### Users
Gamers installing large modlists (100-650GB, thousands of archives). They know what Wabbajack is, they've modded before, they want the install to work on Linux/macOS where Wabbajack doesn't. They sit through multi-hour installs and need to trust the tool is working. Mix of technical modders and people who just want to play.

### Brand Personality
**Fast, bold, unapologetic.** Aggressive performance focus. Speed is the brand. No compromises. This tool exists because the original doesn't run on their OS. It should feel like an upgrade, not a workaround.

### Emotional Goals
**Confidence and control.** Like a cockpit: every metric visible, user feels in command of the process. During a 450GB install, the UI should communicate exactly what's happening, how fast, and how much remains. No mystery, no anxiety.

### Aesthetic Direction
- **Reference:** Steam Big Picture -- dark, gaming-native, large elements, card-heavy, ambient glow effects
- **Anti-reference:** Generic admin dashboards. No corporate SaaS with blue headers and white cards. This is a gaming tool, not Jira.
- **Theme:** Dark only. Near-black backgrounds (#0f0f13), amber/orange accent (#e8922a) inspired by Wabbajack's identity
- **Depth:** Cards with subtle glow on hover, not flat. Layered backgrounds create hierarchy.
- **Motion:** Purposeful transitions (Svelte built-in), smooth progress animations, pulse on active elements. Never gratuitous.

### Design Tokens
```css
--bg-primary:     #0f0f13    /* near-black canvas */
--bg-secondary:   #1a1a24    /* cards, panels */
--bg-tertiary:    #252532    /* inputs, hover states */
--border:         #2d2d3d    /* subtle edges */
--text-primary:   #e8e8f0    /* main text */
--text-secondary: #8888a0    /* labels, metadata */
--accent:         #e8922a    /* amber -- primary action, highlights */
--accent-hover:   #f5a03d    /* lighter amber for hover */
--accent-glow:    rgba(232, 146, 42, 0.25)  /* box-shadow glow */
--success:        #4ade80    /* green -- completed, verified */
--error:          #f87171    /* red -- failures */
--warning:        #fbbf24    /* yellow -- warnings, manual action needed */
--radius:         8px        /* cards */
--radius-sm:      4px        /* buttons, inputs */
--font-mono:      'JetBrains Mono', 'Fira Code', monospace  /* logs, paths, hashes */
```

### Design Principles

1. **Data density over decoration.** Show throughput, ETA, file counts, archive status. Every pixel should inform. Gamers read dashboards; give them one.

2. **Speed is visible.** Progress bars animate smoothly. Download speeds update in real-time. Parallel operations show concurrent activity. The UI should feel fast even when waiting.

3. **Gaming-native, not web-app.** Cards glow on hover. Status uses color-coded badges (green/amber/red). Banner images for modlists. The aesthetic belongs next to Steam, not next to Notion.

4. **No mystery.** Every phase of install is labeled. Failures surface immediately with file name and reason. Log viewer is always one click away. The user never wonders "is it stuck?"

5. **Bold over safe.** Use the full accent color. Make the progress bar prominent. Size text for readability at arm's length. This is a tool people stare at for hours.

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, uvicorn, WebSocket
- **Frontend:** Svelte 5 (runes), TypeScript, Vite
- **Styling:** CSS custom properties (no framework), system fonts + JetBrains Mono
- **State:** WebSocket for real-time (progress, logs), REST for CRUD (settings, profiles)
- **Packaging:** PyInstaller (single binary), Inno Setup (Windows), AppImage (Linux)
