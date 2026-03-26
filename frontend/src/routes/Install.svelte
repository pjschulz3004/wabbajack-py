<script lang="ts">
  import ProgressBar from '../lib/components/ProgressBar.svelte';
  import LogViewer from '../lib/components/LogViewer.svelte';
  import ManualDownloadCard from '../lib/components/ManualDownloadCard.svelte';
  import { logs, progress, manualDownloads, installState, sendWs, clearLogs } from '../lib/stores/ws';
  import { api } from '../lib/api';

  let { modlist = null }: { modlist?: any } = $props();

  // Detected installs
  interface DetectedInstall {
    name: string; version: string; game: string;
    output_dir: string; downloads_dir: string; game_dir: string; wabbajack_path: string;
    phase: string; completed_archives: number; placed_files: number; started: string;
  }
  let detectedInstalls = $state<DetectedInstall[]>([]);
  let detectedWjFiles = $state<string[]>([]);
  let gameDownloads = $state<Record<string, {count: number; size: number}>>({});

  $effect(() => {
    api.installs().then((data: any) => {
      detectedInstalls = data.installs ?? [];
      detectedWjFiles = data.wabbajack_files ?? [];
      gameDownloads = data.game_downloads ?? {};
    }).catch(() => {});
  });

  function loadDetectedInstall(inst: DetectedInstall) {
    wabbajackPath = inst.wabbajack_path;
    outputDir = inst.output_dir;
    downloadsDir = inst.downloads_dir;
    gameDir = inst.game_dir;
    showForm = true;
  }

  function loadWjFile(path: string) {
    wabbajackPath = path;
    showForm = true;
  }

  function formatSize(bytes: number): string {
    if (!bytes || bytes <= 0) return '0';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
  }

  // Form state
  let wabbajackPath = $state('');
  let outputDir = $state('');
  let downloadsDir = $state('');
  let gameDir = $state('');
  let workers = $state(4);
  let showForm = $state(true);

  // Set smart defaults when modlist changes
  $effect(() => {
    if (!modlist) return;
    const game = modlist.game ?? '';
    const title = (modlist.title ?? 'modlist').replace(/[^a-zA-Z0-9_-]/g, '_');

    // Fetch detected installs to find local .wabbajack file and base paths
    fetch('/api/installs').then(r => r.json()).then((data: any) => {
      const base = data.downloads_base ?? '';
      if (!downloadsDir && game) downloadsDir = `${base}/${game}`;
      if (!outputDir) outputDir = base.replace('/WabbajackDownloads', '') + `/${title}`;

      // Try to find a local .wabbajack file matching this modlist
      if (!wabbajackPath) {
        const wjFiles: string[] = data.wabbajack_files ?? [];
        const titleLower = (modlist.title ?? '').toLowerCase().replace(/\s+/g, '');
        const match = wjFiles.find((f: string) => {
          const fname = f.split('/').pop()?.toLowerCase().replace(/\s+/g, '') ?? '';
          return fname.includes(titleLower) || titleLower.includes(fname.replace(/\.wabbajack.*/, ''));
        });
        if (match) {
          wabbajackPath = match;
        } else if (modlist.links?.download) {
          // Fallback: use download URL (server will need to download it first)
          wabbajackPath = modlist.links.download;
        }
      }
    }).catch(() => {});

    // Fetch actual games to find the game dir
    api.games().then((data: any) => {
      const games = data.games ?? data ?? [];
      const match = games.find((g: any) =>
        g.id?.toLowerCase() === game.toLowerCase() ||
        g.name?.toLowerCase() === game.toLowerCase()
      );
      if (match?.path && !gameDir) gameDir = match.path;
    }).catch(() => {});
  });

  // Auto-subscribed store values (no leak)
  let currentLogs = $derived($logs);
  let currentProgress = $derived($progress);
  let currentManuals = $derived($manualDownloads);
  let currentState = $derived($installState);

  let isRunning = $derived(
    currentState?.status === 'running' || currentState?.status === 'installing'
  );
  let isPaused = $derived(currentState?.status === 'paused');
  let isDone = $derived(
    currentState?.status === 'complete' || currentState?.status === 'error'
  );

  let progressPhase = $derived(currentProgress?.phase ?? 'idle');
  let progressCurrent = $derived(currentProgress?.current ?? 0);
  let progressTotal = $derived(currentProgress?.total ?? 0);
  let progressSpeed = $derived(currentProgress?.speed ?? '');
  let progressEta = $derived(currentProgress?.eta ?? '');

  const phases: Record<string, { label: string; icon: string }> = {
    idle: { label: 'Ready', icon: 'O' },
    downloading: { label: 'Downloading Archives', icon: 'D' },
    extracting: { label: 'Extracting Files', icon: 'E' },
    placing: { label: 'Placing Files', icon: 'P' },
    bsa: { label: 'Building BSA Archives', icon: 'B' },
    mo2: { label: 'MO2 Setup', icon: 'M' },
    complete: { label: 'Install Complete', icon: 'V' },
    error: { label: 'Error', icon: 'X' },
  };

  let phaseInfo = $derived(phases[progressPhase] ?? phases.idle);

  let submitting = $state(false);
  let installError = $state('');

  async function startInstall() {
    installError = '';
    submitting = true;
    try {
      await api.startInstall({
        wabbajack_path: wabbajackPath,
        output_dir: outputDir,
        downloads_dir: downloadsDir,
        game_dir: gameDir,
        workers: workers,
      });
      showForm = false;
    } catch (err: any) {
      installError = err.message ?? 'Failed to start installation';
    } finally {
      submitting = false;
    }
  }

  function pauseInstall() {
    sendWs({ type: 'pause' });
  }

  function resumeInstall() {
    sendWs({ type: 'resume' });
  }

  function cancelInstall() {
    if (confirm('Cancel this installation? Progress will be lost.')) {
      sendWs({ type: 'cancel' });
    }
  }

  function resetForm() {
    clearLogs();
    showForm = true;
  }
</script>

<div class="install-page">
  <!-- Phase Indicator -->
  <div class="phase-strip">
    {#each Object.entries(phases).filter(([k]) => k !== 'idle' && k !== 'error') as [key, p]}
      <div
        class="phase-step"
        class:active={progressPhase === key}
        class:done={
          Object.keys(phases).indexOf(progressPhase) > Object.keys(phases).indexOf(key)
        }
      >
        <span class="phase-dot"></span>
        <span class="phase-name">{p.label}</span>
      </div>
    {/each}
  </div>

  <!-- Progress Bar -->
  <section class="progress-section">
    <ProgressBar
      current={progressCurrent}
      total={progressTotal}
      phase={phaseInfo.label}
      speed={progressSpeed}
      eta={progressEta}
    />
  </section>

  <!-- Manual Downloads -->
  {#if currentManuals.length > 0}
    <section class="manual-section">
      <h3 class="section-title">Manual Downloads Needed</h3>
      <div class="manual-grid">
        {#each currentManuals as dl (dl.name)}
          <ManualDownloadCard name={dl.name} url={dl.url} status={dl.status ?? 'waiting'} />
        {/each}
      </div>
    </section>
  {/if}

  <!-- Log Viewer -->
  <section class="log-section">
    <LogViewer logs={currentLogs} />
  </section>

  <!-- Detected Installs -->
  {#if !isRunning && !modlist && (detectedInstalls.length > 0 || detectedWjFiles.length > 0 || Object.keys(gameDownloads).length > 0)}
    <section class="detected-section">
      {#if detectedInstalls.length > 0}
        <h3 class="section-title">Previous Installs</h3>
        <div class="detected-list">
          {#each detectedInstalls as inst}
            <button class="detected-card" onclick={() => loadDetectedInstall(inst)}>
              <div class="detected-info">
                <span class="detected-name">{inst.name}</span>
                <span class="detected-meta">{inst.game}{inst.version ? ` v${inst.version}` : ''}</span>
              </div>
              <div class="detected-status">
                <span class="badge" class:badge-success={inst.phase === 'complete'} class:badge-warning={inst.phase !== 'complete' && inst.phase !== 'init'} class:badge-neutral={inst.phase === 'init' || inst.phase === 'unknown'}>
                  {inst.phase}
                </span>
                {#if inst.completed_archives > 0}
                  <span class="detected-stat">{inst.completed_archives} archives done</span>
                {/if}
              </div>
            </button>
          {/each}
        </div>
      {/if}

      {#if detectedWjFiles.length > 0}
        <h3 class="section-title">Modlist Files</h3>
        <div class="detected-list">
          {#each detectedWjFiles as path}
            <button class="detected-card" onclick={() => loadWjFile(path)}>
              <span class="detected-name">{path.split('/').pop()}</span>
              <span class="detected-meta mono">{path}</span>
            </button>
          {/each}
        </div>
      {/if}

      {#if Object.keys(gameDownloads).length > 0}
        <h3 class="section-title">Downloaded Archives</h3>
        <div class="dl-stats">
          {#each Object.entries(gameDownloads) as [game, stats]}
            <div class="dl-stat">
              <span class="dl-game">{game}</span>
              <span class="dl-count">{stats.count.toLocaleString()} files</span>
              <span class="dl-size">{formatSize(stats.size)}</span>
            </div>
          {/each}
        </div>
      {/if}
    </section>
  {/if}

  <!-- Action Area -->
  <section class="action-section">
    {#if showForm && !isRunning}
      {#if modlist}
        <div class="modlist-banner">
          <h3 class="modlist-title">{modlist.title}</h3>
          <span class="modlist-meta">{modlist.game} &middot; {modlist.author ?? 'Unknown'}</span>
        </div>
      {/if}
      <form class="install-form" onsubmit={(e) => { e.preventDefault(); startInstall(); }}>
        <h3 class="section-title">Start Installation</h3>
        <div class="form-grid">
          <div class="form-field">
            <label for="wabbajack-path">.wabbajack File</label>
            <input
              id="wabbajack-path"
              type="text"
              bind:value={wabbajackPath}
              placeholder="/path/to/modlist.wabbajack"
              required
            />
          </div>
          <div class="form-field">
            <label for="output-dir">Output Directory</label>
            <input
              id="output-dir"
              type="text"
              bind:value={outputDir}
              placeholder="/path/to/install/output"
              required
            />
          </div>
          <div class="form-field">
            <label for="downloads-dir">Downloads Directory</label>
            <input
              id="downloads-dir"
              type="text"
              bind:value={downloadsDir}
              placeholder="/path/to/downloads"
              required
            />
          </div>
          <div class="form-field">
            <label for="game-dir">Game Directory</label>
            <input
              id="game-dir"
              type="text"
              bind:value={gameDir}
              placeholder="/path/to/game"
              required
            />
          </div>
          <div class="form-field workers-field">
            <label for="workers">Workers: {workers}</label>
            <input
              id="workers"
              type="range"
              min="1"
              max="16"
              bind:value={workers}
            />
            <span class="workers-hint">Parallel download threads</span>
          </div>
        </div>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" disabled={submitting}>
            {submitting ? 'Starting...' : 'Start Install'}
          </button>
        </div>
      </form>
      {#if installError}
        <div class="error-banner" role="alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          {installError}
        </div>
      {/if}
    {:else}
      <div class="control-bar">
        {#if isRunning && !isPaused}
          <button class="btn btn-ghost" onclick={pauseInstall}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
            Pause
          </button>
        {/if}
        {#if isPaused}
          <button class="btn btn-primary" onclick={resumeInstall}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><polygon points="5,3 19,12 5,21"/></svg>
            Resume
          </button>
        {/if}
        {#if isRunning || isPaused}
          <button class="btn btn-danger" onclick={cancelInstall}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            Cancel
          </button>
        {/if}
        {#if isDone}
          <button class="btn btn-ghost" onclick={resetForm}>New Install</button>
        {/if}
      </div>
    {/if}
  </section>
</div>

<style>
  .install-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1.5rem;
    height: 100%;
    overflow-y: auto;
  }

  .section-title {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
    margin-bottom: 0.75rem;
  }

  /* Phase Strip */
  .phase-strip {
    display: flex;
    gap: 0;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.625rem 1rem;
    overflow-x: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  .phase-strip::-webkit-scrollbar { display: none; }

  .phase-step {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.75rem;
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--text-secondary);
    opacity: 0.4;
    transition: all 0.2s;
    white-space: nowrap;
  }

  .phase-step.active {
    opacity: 1;
    color: var(--accent);
  }

  .phase-step.done {
    opacity: 0.7;
    color: var(--success);
  }

  .phase-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
    flex-shrink: 0;
  }

  .phase-step.active .phase-dot {
    box-shadow: 0 0 8px var(--accent-glow);
    animation: dot-pulse 1.5s ease-in-out infinite;
  }

  @keyframes dot-pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.4); }
  }

  /* Progress */
  .progress-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.75rem 1rem;
  }

  /* Manual Downloads */
  .manual-section {
    background: var(--bg-secondary);
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    padding: 1rem;
  }

  .manual-grid {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  /* Log Section */
  .log-section {
    flex: 1;
    min-height: 200px;
  }

  /* Action Section */
  .action-section {
    flex-shrink: 0;
  }

  .install-form {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .form-field label {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-secondary);
  }

  .workers-field {
    grid-column: 1 / -1;
  }

  .workers-field input[type="range"] {
    width: 100%;
    accent-color: var(--accent);
    padding: 0.25rem 0;
    border: none;
    background: transparent;
  }

  .workers-hint {
    font-size: 0.65rem;
    color: var(--text-secondary);
    opacity: 0.6;
  }

  .form-actions {
    margin-top: 1rem;
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
  }

  .error-banner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    padding: 0.625rem 0.875rem;
    background: rgba(248, 113, 113, 0.1);
    border: 1px solid var(--error);
    border-radius: var(--radius-sm);
    color: var(--error);
    font-size: 0.825rem;
  }

  .modlist-banner {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    border-radius: var(--radius);
  }

  .modlist-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--accent);
  }

  .modlist-meta {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }

  .control-bar {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    padding: 0.75rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }

  /* Detected installs */
  .detected-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .detected-list {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .detected-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.625rem 0.875rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: border-color 0.15s;
    text-align: left;
    color: inherit;
    font: inherit;
    width: 100%;
  }
  .detected-card:hover { border-color: var(--accent); }

  .detected-info {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    min-width: 0;
  }

  .detected-name {
    font-size: 0.825rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .detected-meta {
    font-size: 0.7rem;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .detected-meta.mono { font-family: var(--font-mono); font-size: 0.65rem; }

  .detected-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .detected-stat {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  .dl-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .dl-stat {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }

  .dl-game {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .dl-count, .dl-size {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  @media (max-width: 900px) {
    .form-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 768px) {
    .install-page { padding: 0.75rem; }
    .log-section { min-height: 120px; }
    .phase-step { padding: 0.25rem 0.5rem; font-size: 0.625rem; }
  }
</style>
