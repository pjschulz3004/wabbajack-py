<script lang="ts">
  import { api } from '../lib/api';

  interface ProfileInfo {
    title: string;
    version: string;
    game: string;
    output: string;
    archive_count: number;
    installed_at: string;
  }

  interface ProfilesResponse {
    active: string;
    shared_downloads: string;
    profiles: Record<string, ProfileInfo>;
  }

  let data: ProfilesResponse | null = $state(null);
  let loading: boolean = $state(true);
  let error: string = $state('');
  let switching: string = $state('');

  let profileEntries = $derived(
    data ? Object.entries(data.profiles) : []
  );

  async function load() {
    loading = true;
    error = '';
    try {
      data = await api.profiles();
    } catch (e: any) {
      error = e.message || 'Failed to load profiles';
    } finally {
      loading = false;
    }
  }

  async function switchTo(name: string) {
    switching = name;
    try {
      await api.switchProfile(name);
      await load();
    } catch (e: any) {
      error = e.message || 'Failed to switch profile';
    } finally {
      switching = '';
    }
  }

  function formatDate(iso: string): string {
    if (!iso) return 'Unknown';
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  $effect(() => {
    load();
  });
</script>

<div class="profiles-page">
  <header class="page-header">
    <div class="header-text">
      <h2>Profiles</h2>
      {#if data?.shared_downloads}
        <p class="shared-path">
          <span class="label">Shared downloads:</span>
          <code>{data.shared_downloads}</code>
        </p>
      {/if}
    </div>
    <button class="btn btn-ghost" onclick={load} disabled={loading}>
      {#if loading}
        Refreshing...
      {:else}
        Refresh
      {/if}
    </button>
  </header>

  {#if error}
    <div class="error-banner" role="alert">
      <span>{error}</span>
      <button class="btn btn-sm btn-ghost" onclick={() => { error = ''; }}>Dismiss</button>
    </div>
  {/if}

  {#if loading && !data}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading profiles...</p>
    </div>
  {:else if profileEntries.length === 0}
    <div class="empty-state">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2Z"/>
          <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
        </svg>
      </div>
      <p class="empty-title">No profiles</p>
      <p class="empty-detail">Install a modlist with <code>--profile</code> to create one.</p>
    </div>
  {:else}
    <div class="profile-grid">
      {#each profileEntries as [name, profile]}
        {@const isActive = data?.active === name}
        {@const isSwitching = switching === name}
        <div class="profile-card" class:active={isActive}>
          <div class="card-header">
            <div class="card-title-row">
              <h2 class="profile-name">{name}</h2>
              {#if isActive}
                <span class="badge badge-accent">Active</span>
              {/if}
            </div>
            <p class="modlist-title">{profile.title} <span class="version">v{profile.version}</span></p>
          </div>

          <div class="card-body">
            <div class="info-row">
              <span class="info-label">Game</span>
              <span class="info-value">{profile.game}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Output</span>
              <span class="info-value path-value" title={profile.output}>{profile.output}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Archives</span>
              <span class="info-value">{profile.archive_count.toLocaleString()}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Installed</span>
              <span class="info-value">{formatDate(profile.installed_at)}</span>
            </div>
          </div>

          <div class="card-footer">
            {#if isActive}
              <span class="active-label">Currently active</span>
            {:else}
              <button
                class="btn btn-primary btn-sm"
                onclick={() => switchTo(name)}
                disabled={isSwitching || switching !== ''}
              >
                {#if isSwitching}
                  Switching...
                {:else}
                  Switch
                {/if}
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .profiles-page {
    padding: 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
  }

  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 1.5rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .page-header h2 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .shared-path {
    margin-top: 0.375rem;
    font-size: 0.8rem;
    color: var(--text-secondary);
  }

  .shared-path .label {
    margin-right: 0.375rem;
  }

  .shared-path code {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    background: var(--bg-tertiary);
    padding: 0.125rem 0.375rem;
    border-radius: var(--radius-sm);
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

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 1rem;
    gap: 0.75rem;
  }

  .empty-icon {
    color: var(--text-secondary);
    opacity: 0.5;
    margin-bottom: 0.5rem;
  }

  .empty-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .empty-detail {
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .empty-detail code {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    background: var(--bg-tertiary);
    padding: 0.125rem 0.375rem;
    border-radius: var(--radius-sm);
    color: var(--accent);
  }

  .profile-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1rem;
  }

  .profile-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  .profile-card:hover {
    border-color: var(--accent);
  }

  .profile-card.active {
    border-color: var(--accent);
    box-shadow: 0 0 16px var(--accent-glow), 0 0 4px var(--accent-glow);
  }

  .card-header {
    padding: 1rem 1.25rem 0.75rem;
  }

  .card-title-row {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    margin-bottom: 0.25rem;
  }

  .profile-name {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .modlist-title {
    font-size: 0.8rem;
    color: var(--text-secondary);
  }

  .modlist-title .version {
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }

  .card-body {
    flex: 1;
    padding: 0 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.8rem;
    gap: 0.75rem;
  }

  .info-label {
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  .info-value {
    color: var(--text-primary);
    text-align: right;
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }

  .path-value {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 200px;
  }

  .card-footer {
    padding: 0.75rem 1.25rem;
    margin-top: 0.5rem;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: flex-end;
    align-items: center;
  }

  .active-label {
    font-size: 0.75rem;
    color: var(--accent);
    font-weight: 500;
  }
</style>
