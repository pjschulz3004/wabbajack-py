<script lang="ts">
  import { api } from '../lib/api';
  import { updateProgress, connected } from '../lib/stores/ws';

  interface NexusStatusResponse {
    status: 'logged_out' | 'free' | 'premium';
    username?: string;
  }

  interface GameInfo {
    name: string;
    path: string;
    installed: boolean;
  }

  interface SettingsData {
    output_dir: string;
    downloads_dir: string;
    game_dir: string;
    workers: number;
    verify_hashes: boolean;
  }

  // Settings state
  let settings: SettingsData = $state({
    output_dir: '',
    downloads_dir: '',
    game_dir: '',
    workers: 12,
    verify_hashes: true,
  });
  let originalSettings: string = $state('');
  let settingsLoading: boolean = $state(true);
  let settingsError: string = $state('');
  let saving: boolean = $state(false);
  let saveSuccess: boolean = $state(false);

  // Games state
  let games: GameInfo[] = $state([]);
  let gamesLoading: boolean = $state(false);

  // Update state
  let updateInfo: any = $state(null);
  let updateChecking = $state(false);
  let updateApplying = $state(false);
  let updateError = $state('');
  let updateStep = $state('');
  let updateMessage = $state('');
  let updatePct = $state(0);
  let restarting = $state(false);

  // Watch WS update events
  let currentUpdateMsg = $derived($updateProgress);

  $effect(() => {
    const msg = currentUpdateMsg;
    if (!msg) return;
    if (msg.type === 'update_progress') {
      updateApplying = true;
      updateStep = msg.step ?? '';
      updateMessage = msg.message ?? '';
      updatePct = msg.pct ?? 0;
    } else if (msg.type === 'update_complete') {
      updateMessage = msg.message ?? 'Update complete!';
      updatePct = 100;
    } else if (msg.type === 'update_restart') {
      restarting = true;
      updateMessage = 'Restarting server...';
    } else if (msg.type === 'update_error') {
      updateApplying = false;
      updateError = msg.message ?? 'Update failed';
    }
  });

  // When server comes back after restart, reload the page
  let isConnected = $derived($connected);
  $effect(() => {
    if (restarting && isConnected) {
      // Server is back, reload to pick up new frontend
      setTimeout(() => window.location.reload(), 500);
    }
  });

  async function checkUpdate() {
    updateChecking = true;
    updateError = '';
    try {
      updateInfo = await api.checkUpdate();
    } catch (e: any) {
      updateError = e.message || 'Failed to check for updates';
    } finally {
      updateChecking = false;
    }
  }

  async function applyUpdate() {
    updateApplying = true;
    updateError = '';
    updateStep = 'starting';
    updateMessage = 'Starting update...';
    updatePct = 0;
    try {
      await api.applyUpdate();
      // Server returns immediately; progress comes via WebSocket
    } catch (e: any) {
      updateError = e.message || 'Update failed';
      updateApplying = false;
    }
  }

  // Nexus state
  let nexus: NexusStatusResponse = $state({ status: 'logged_out' });
  let nexusLoading: boolean = $state(true);
  let nexusLoggingIn: boolean = $state(false);
  let nexusLoggingOut: boolean = $state(false);
  let showApiKey: boolean = $state(false);
  let apiKeyInput: string = $state('');
  let apiKeySubmitting: boolean = $state(false);
  let nexusError: string = $state('');
  let ssoPolling: boolean = $state(false);

  let hasChanges = $derived(
    JSON.stringify(settings) !== originalSettings
  );

  let nexusBadgeClass = $derived(
    nexus.status === 'premium'
      ? 'badge-success'
      : nexus.status === 'free'
        ? 'badge-warning'
        : 'badge-error'
  );

  let nexusLabel = $derived(
    nexus.status === 'premium'
      ? 'Premium'
      : nexus.status === 'free'
        ? 'Free'
        : 'Logged Out'
  );

  async function loadSettings() {
    settingsLoading = true;
    settingsError = '';
    try {
      const data = await api.settings();
      settings = {
        output_dir: data.output_dir ?? '',
        downloads_dir: data.downloads_dir ?? '',
        game_dir: data.game_dir ?? '',
        workers: data.workers ?? 12,
        verify_hashes: data.verify_hashes ?? true,
      };
      originalSettings = JSON.stringify(settings);
    } catch (e: any) {
      settingsError = e.message || 'Failed to load settings';
    } finally {
      settingsLoading = false;
    }
  }

  async function loadGames() {
    gamesLoading = true;
    try {
      const data = await api.games();
      games = Array.isArray(data) ? data : data.games ?? [];
    } catch {
      games = [];
    } finally {
      gamesLoading = false;
    }
  }

  async function loadNexus() {
    nexusLoading = true;
    try {
      nexus = await api.nexusStatus();
    } catch {
      nexus = { status: 'logged_out' };
    } finally {
      nexusLoading = false;
    }
  }

  async function save() {
    saving = true;
    saveSuccess = false;
    settingsError = '';
    try {
      await api.updateSettings(settings);
      originalSettings = JSON.stringify(settings);
      saveSuccess = true;
      setTimeout(() => { saveSuccess = false; }, 3000);
    } catch (e: any) {
      settingsError = e.message || 'Failed to save settings';
    } finally {
      saving = false;
    }
  }

  async function nexusLogin() {
    nexusLoggingIn = true;
    nexusError = '';
    try {
      const resp = await api.nexusLogin();
      if (resp.auth_url) {
        window.open(resp.auth_url, '_blank');
      }
      ssoPolling = true;
      pollSso();
    } catch (e: any) {
      nexusError = e.message || 'Failed to start Nexus login';
      nexusLoggingIn = false;
    }
  }

  async function pollSso() {
    let attempts = 0;
    const maxAttempts = 120; // 2 minutes at 1s intervals
    while (ssoPolling && attempts < maxAttempts) {
      await new Promise(r => setTimeout(r, 1000));
      attempts++;
      try {
        const resp = await api.nexusSsoStatus();
        if (resp.status === 'complete' || resp.status === 'premium' || resp.status === 'free') {
          ssoPolling = false;
          nexusLoggingIn = false;
          await loadNexus();
          return;
        }
        if (resp.status === 'error') {
          ssoPolling = false;
          nexusLoggingIn = false;
          nexusError = resp.error || 'SSO login failed';
          return;
        }
      } catch {
        // continue polling on transient errors
      }
    }
    ssoPolling = false;
    nexusLoggingIn = false;
    if (attempts >= maxAttempts) {
      nexusError = 'Login timed out. Please try again.';
    }
  }

  async function submitApiKey() {
    if (!apiKeyInput.trim()) return;
    apiKeySubmitting = true;
    nexusError = '';
    try {
      await api.nexusSetKey(apiKeyInput.trim());
      apiKeyInput = '';
      showApiKey = false;
      await loadNexus();
    } catch (e: any) {
      nexusError = e.message || 'Failed to set API key';
    } finally {
      apiKeySubmitting = false;
    }
  }

  async function nexusLogout() {
    nexusLoggingOut = true;
    nexusError = '';
    try {
      await api.nexusLogout();
      await loadNexus();
    } catch (e: any) {
      nexusError = e.message || 'Failed to logout';
    } finally {
      nexusLoggingOut = false;
    }
  }

  $effect(() => {
    loadSettings();
    loadGames();
    loadNexus();
    return () => { ssoPolling = false; };
  });
</script>

<div class="settings-page">
  <header class="page-header">
    <h2>Settings</h2>
  </header>

  {#if settingsError}
    <div class="error-banner" role="alert">
      <span>{settingsError}</span>
      <button class="btn btn-sm btn-ghost" onclick={() => { settingsError = ''; }}>Dismiss</button>
    </div>
  {/if}

  {#if settingsLoading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading settings...</p>
    </div>
  {:else}
    <!-- Section 1: Paths -->
    <section class="settings-section">
      <div class="section-header">
        <h2>Paths</h2>
        <p class="section-desc">Configure output, download, and game directories</p>
      </div>

      <div class="field-group">
        <label class="field-label" for="output-dir">Output Directory</label>
        <input
          id="output-dir"
          type="text"
          bind:value={settings.output_dir}
          placeholder="/path/to/modlist/output"
          spellcheck="false"
        />
        <p class="field-hint">Where the installed modlist is placed</p>
      </div>

      <div class="field-group">
        <label class="field-label" for="downloads-dir">Downloads Directory</label>
        <input
          id="downloads-dir"
          type="text"
          bind:value={settings.downloads_dir}
          placeholder="/path/to/downloads"
          spellcheck="false"
        />
        <p class="field-hint">Where mod archives are cached</p>
      </div>

      <div class="field-group">
        <label class="field-label" for="game-dir">Game Directory</label>
        <input
          id="game-dir"
          type="text"
          bind:value={settings.game_dir}
          placeholder="/path/to/game"
          spellcheck="false"
        />
        <p class="field-hint">Auto-detected games shown below</p>
      </div>

      <!-- Detected Games -->
      <div class="detected-games">
        <h3 class="subsection-title">Detected Games</h3>
        {#if gamesLoading}
          <p class="muted-text">Scanning for games...</p>
        {:else if games.length === 0}
          <p class="muted-text">No games detected</p>
        {:else}
          <div class="games-list">
            {#each games as game}
              <div class="game-row" class:installed={game.installed}>
                <div class="game-info">
                  <span class="game-name">{game.name}</span>
                  {#if game.installed}
                    <span class="badge badge-success">Installed</span>
                  {:else}
                    <span class="badge badge-error">Not Found</span>
                  {/if}
                </div>
                {#if game.path}
                  <code class="game-path">{game.path}</code>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </section>

    <!-- Section 2: Performance -->
    <section class="settings-section">
      <div class="section-header">
        <h2>Performance</h2>
        <p class="section-desc">Download and processing settings</p>
      </div>

      <div class="field-group">
        <label class="field-label" for="workers">
          Workers
          <span class="field-value">{settings.workers}</span>
        </label>
        <input
          id="workers"
          type="range"
          min="1"
          max="32"
          step="1"
          bind:value={settings.workers}
        />
        <div class="range-labels">
          <span>1</span>
          <span>32</span>
        </div>
        <p class="field-hint">Number of concurrent download/extraction workers</p>
      </div>

      <div class="field-group">
        <label class="toggle-row">
          <input
            type="checkbox"
            bind:checked={settings.verify_hashes}
          />
          <span class="toggle-label">Hash Verification</span>
        </label>
        <p class="field-hint">Verify file integrity after download (recommended)</p>
      </div>
    </section>

    <!-- Section 3: Nexus Mods -->
    <section class="settings-section">
      <div class="section-header">
        <h2>Nexus Mods</h2>
        <p class="section-desc">Manage your Nexus Mods authentication</p>
      </div>

      {#if nexusError}
        <div class="error-banner compact" role="alert">
          <span>{nexusError}</span>
          <button class="btn btn-sm btn-ghost" onclick={() => { nexusError = ''; }}>Dismiss</button>
        </div>
      {/if}

      {#if nexusLoading}
        <p class="muted-text">Checking Nexus status...</p>
      {:else}
        <div class="nexus-status-row">
          <div class="nexus-info">
            <span class="info-label">Status</span>
            <span class="badge {nexusBadgeClass}">{nexusLabel}</span>
          </div>
          {#if nexus.username}
            <div class="nexus-info">
              <span class="info-label">Username</span>
              <span class="info-value">{nexus.username}</span>
            </div>
          {/if}
        </div>

        <div class="nexus-actions">
          {#if nexus.status === 'logged_out'}
            <button
              class="btn btn-primary"
              onclick={nexusLogin}
              disabled={nexusLoggingIn}
            >
              {#if nexusLoggingIn}
                {#if ssoPolling}
                  Waiting for browser...
                {:else}
                  Connecting...
                {/if}
              {:else}
                Login with Nexus
              {/if}
            </button>

            <div class="api-key-section">
              <button
                class="btn btn-ghost btn-sm"
                onclick={() => { showApiKey = !showApiKey; }}
              >
                {#if showApiKey}Hide{:else}Set API Key Manually{/if}
              </button>

              {#if showApiKey}
                <div class="api-key-form">
                  <input
                    type="password"
                    placeholder="Paste your Nexus API key"
                    bind:value={apiKeyInput}
                    spellcheck="false"
                  />
                  <button
                    class="btn btn-primary btn-sm"
                    onclick={submitApiKey}
                    disabled={apiKeySubmitting || !apiKeyInput.trim()}
                  >
                    {#if apiKeySubmitting}Saving...{:else}Save Key{/if}
                  </button>
                </div>
              {/if}
            </div>
          {:else}
            <button
              class="btn btn-danger btn-sm"
              onclick={nexusLogout}
              disabled={nexusLoggingOut}
            >
              {#if nexusLoggingOut}Logging out...{:else}Logout{/if}
            </button>
          {/if}
        </div>
      {/if}
    </section>

    <!-- Section 4: Updates -->
    <section class="settings-section">
      <div class="section-header">
        <h2>Updates</h2>
        <p class="section-desc">Check for and install new versions</p>
      </div>

      {#if updateError}
        <div class="error-banner compact" role="alert">
          <span>{updateError}</span>
          <button class="btn btn-sm btn-ghost" onclick={() => { updateError = ''; }}>Dismiss</button>
        </div>
      {/if}

      <div class="update-row">
        <div class="update-info">
          <span class="info-label">Current</span>
          <span class="badge badge-accent">{updateInfo?.current ?? '0.3.0'}</span>
        </div>
        {#if updateInfo?.latest && updateInfo.latest !== updateInfo.current}
          <div class="update-info">
            <span class="info-label">Latest</span>
            <span class="badge badge-success">{updateInfo.latest}</span>
          </div>
        {/if}
        {#if updateInfo?.install_type}
          <div class="update-info">
            <span class="info-label">Install</span>
            <span class="info-value">{updateInfo.install_type}</span>
          </div>
        {/if}
      </div>

      {#if updateApplying}
        <!-- Update progress -->
        <div class="update-progress">
          <div class="update-progress-bar">
            <div class="update-progress-fill" style="width: {updatePct}%"></div>
          </div>
          <div class="update-progress-info">
            <span class="update-step">{updateMessage}</span>
            <span class="update-pct">{updatePct}%</span>
          </div>
        </div>
      {:else}
        <div class="update-actions">
          {#if updateInfo?.update_available}
            <button class="btn btn-primary" onclick={applyUpdate} disabled={updateApplying}>
              Update to {updateInfo.latest}
            </button>
            {#if updateInfo.changelog}
              <details class="changelog">
                <summary>Changelog</summary>
                <pre class="changelog-body">{updateInfo.changelog}</pre>
              </details>
            {/if}
          {:else}
            <button class="btn btn-ghost" onclick={checkUpdate} disabled={updateChecking}>
              {updateChecking ? 'Checking...' : 'Check for Updates'}
            </button>
            {#if updateInfo && !updateInfo.update_available && !updateInfo.error}
              <span class="update-ok">Up to date</span>
            {/if}
          {/if}
        </div>
      {/if}
    </section>

    <!-- Save Button -->
    <div class="save-bar">
      <div class="save-status">
        {#if saveSuccess}
          <span class="save-ok">Settings saved</span>
        {:else if hasChanges}
          <span class="unsaved">Unsaved changes</span>
        {/if}
      </div>
      <button
        class="btn btn-primary"
        onclick={save}
        disabled={saving || !hasChanges}
      >
        {#if saving}
          Saving...
        {:else}
          Save Settings
        {/if}
      </button>
    </div>
  {/if}
</div>

{#if restarting}
  <div class="restart-overlay">
    <div class="restart-card">
      <div class="restart-spinner"></div>
      <h3>Restarting Server</h3>
      <p>Applying update and reloading...</p>
    </div>
  </div>
{/if}

<style>
  .settings-page {
    padding: 1.5rem;
    max-width: 800px;
    margin: 0 auto;
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .page-header h2 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .error-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    background: rgba(248, 113, 113, 0.1);
    border: 1px solid rgba(248, 113, 113, 0.3);
    border-radius: var(--radius);
    padding: 0.75rem 1rem;
    margin-bottom: 1.5rem;
    color: var(--error);
    font-size: 0.875rem;
  }

  .error-banner.compact {
    margin-bottom: 1rem;
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 1rem;
    gap: 1rem;
    color: var(--text-secondary);
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--bg-tertiary);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  /* spin keyframe from global app.css */

  /* Sections */
  .settings-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    margin-bottom: 1.25rem;
  }

  .section-header {
    margin-bottom: 1.25rem;
  }

  .section-header h2 {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .section-desc {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 0.125rem;
  }

  /* Fields */
  .field-group {
    margin-bottom: 1rem;
  }

  .field-group:last-child {
    margin-bottom: 0;
  }

  .field-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.825rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.375rem;
  }

  .field-value {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--accent);
    font-weight: 700;
  }

  .field-hint {
    font-size: 0.725rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
  }

  .muted-text {
    font-size: 0.825rem;
    color: var(--text-secondary);
  }

  /* Range slider */
  input[type="range"] {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 6px;
    background: var(--bg-tertiary);
    border: none;
    border-radius: 3px;
    outline: none;
    padding: 0;
  }

  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
    border: 2px solid var(--bg-primary);
    box-shadow: 0 0 6px var(--accent-glow);
  }

  input[type="range"]::-moz-range-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
    border: 2px solid var(--bg-primary);
    box-shadow: 0 0 6px var(--accent-glow);
  }

  .range-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.675rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
    font-family: var(--font-mono);
  }

  /* Checkbox toggle */
  .toggle-row {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    cursor: pointer;
    margin-bottom: 0;
  }

  .toggle-row input[type="checkbox"] {
    -webkit-appearance: none;
    appearance: none;
    width: 36px;
    height: 20px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 10px;
    position: relative;
    cursor: pointer;
    transition: background 0.2s, border-color 0.2s;
    flex-shrink: 0;
    padding: 0;
  }

  .toggle-row input[type="checkbox"]::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--text-secondary);
    transition: transform 0.2s, background 0.2s;
  }

  .toggle-row input[type="checkbox"]:checked {
    background: var(--accent-dim);
    border-color: var(--accent);
  }

  .toggle-row input[type="checkbox"]:checked::after {
    transform: translateX(16px);
    background: var(--accent);
  }

  .toggle-label {
    font-size: 0.825rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  /* Detected Games */
  .detected-games {
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }

  .subsection-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.75rem;
  }

  .games-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .game-row {
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.625rem 0.875rem;
  }

  .game-row.installed {
    border-color: rgba(74, 222, 128, 0.2);
  }

  .game-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .game-name {
    font-size: 0.825rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .game-path {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Nexus Mods */
  .nexus-status-row {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    margin-bottom: 1rem;
  }

  .nexus-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .nexus-info .info-label {
    font-size: 0.8rem;
    color: var(--text-secondary);
  }

  .nexus-info .info-value {
    font-size: 0.8rem;
    color: var(--text-primary);
    font-weight: 600;
  }

  .nexus-actions {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .api-key-section {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
    align-items: flex-start;
  }

  .api-key-form {
    display: flex;
    gap: 0.5rem;
    width: 100%;
    max-width: 480px;
  }

  .api-key-form input {
    flex: 1;
  }

  /* Save Bar */
  .save-bar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1rem 0;
    position: sticky;
    bottom: 0;
    background: linear-gradient(transparent, var(--bg-primary) 40%);
    padding-top: 2.5rem;
    margin-top: 0.5rem;
  }

  .save-status {
    font-size: 0.8rem;
  }

  .save-ok {
    color: var(--success);
    font-weight: 500;
  }

  .unsaved {
    color: var(--warning);
    font-weight: 500;
  }

  /* Updates */
  .update-row {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    margin-bottom: 1rem;
  }

  .update-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .update-info .info-label {
    font-size: 0.8rem;
    color: var(--text-secondary);
  }

  .update-info .info-value {
    font-size: 0.8rem;
    color: var(--text-primary);
    font-weight: 600;
  }

  .update-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .update-success {
    color: var(--success);
    font-weight: 500;
    font-size: 0.875rem;
  }

  .update-ok {
    color: var(--success);
    font-size: 0.8rem;
    font-weight: 500;
  }

  .changelog {
    width: 100%;
    margin-top: 0.5rem;
  }

  .changelog summary {
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-weight: 600;
  }

  .changelog-body {
    margin-top: 0.5rem;
    padding: 0.75rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-secondary);
    white-space: pre-wrap;
    max-height: 300px;
    overflow-y: auto;
  }

  /* Update progress */
  .update-progress {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .update-progress-bar {
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
  }

  .update-progress-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
    transition: width 0.4s ease;
    box-shadow: 0 0 8px var(--accent-glow);
  }

  .update-progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .update-step {
    font-size: 0.8rem;
    color: var(--text-primary);
    font-weight: 500;
  }

  .update-pct {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--accent);
    font-weight: 700;
  }

  /* Restart overlay */
  .restart-overlay {
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: rgba(15, 15, 19, 0.92);
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
  }

  .restart-card {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }

  .restart-card h3 {
    font-size: 1.25rem;
    color: var(--text-primary);
    font-weight: 700;
  }

  .restart-card p {
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .restart-spinner {
    width: 48px;
    height: 48px;
    border: 3px solid var(--bg-tertiary);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 600px) {
    .settings-page { padding: 1rem; }
    .settings-section { padding: 1rem; }
    .api-key-form { flex-direction: column; }
    .nexus-status-row { flex-direction: column; gap: 0.75rem; }
  }
</style>
