<script lang="ts">
  interface Props {
    name: string;
    url: string;
    status?: 'waiting' | 'downloading' | 'complete';
  }

  let { name, url, status = 'waiting' }: Props = $props();

  function openInBrowser() {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
</script>

<div class="manual-card" class:pulse={status === 'waiting'} class:complete={status === 'complete'}>
  <div class="card-status">
    {#if status === 'waiting'}
      <span class="status-icon waiting-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
      </span>
    {:else if status === 'downloading'}
      <span class="status-icon spinner">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
        </svg>
      </span>
    {:else}
      <span class="status-icon check">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M20 6L9 17l-5-5"/>
        </svg>
      </span>
    {/if}
  </div>

  <div class="card-body">
    <p class="card-label">Manual Download Required</p>
    <p class="card-name" title={name}>{name}</p>
  </div>

  <div class="card-actions">
    {#if status !== 'complete'}
      <button class="btn btn-primary btn-sm" onclick={openInBrowser}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
          <polyline points="15 3 21 3 21 9"/>
          <line x1="10" y1="14" x2="21" y2="3"/>
        </svg>
        Open in Browser
      </button>
    {:else}
      <span class="badge badge-success">Done</span>
    {/if}
  </div>
</div>

<style>
  .manual-card {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--bg-secondary);
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    transition: all 0.2s;
  }

  .manual-card.pulse {
    animation: card-pulse 2.5s ease-in-out infinite;
    box-shadow: 0 0 12px var(--accent-glow);
  }

  .manual-card.complete {
    border-color: var(--success);
    opacity: 0.7;
  }

  @keyframes card-pulse {
    0%, 100% {
      box-shadow: 0 0 8px var(--accent-glow);
      border-color: var(--accent);
    }
    50% {
      box-shadow: 0 0 20px var(--accent-glow), 0 0 40px rgba(232, 146, 42, 0.1);
      border-color: var(--accent-hover);
    }
  }

  .card-status {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
  }

  .status-icon {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .waiting-icon {
    color: var(--accent);
    animation: pulse-opacity 2s ease-in-out infinite;
  }

  @keyframes pulse-opacity {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  .spinner {
    color: var(--accent);
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .check {
    color: var(--success);
  }

  .card-body {
    flex: 1;
    min-width: 0;
  }

  .card-label {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--accent);
    margin-bottom: 0.125rem;
  }

  .card-name {
    font-size: 0.85rem;
    font-family: var(--font-mono);
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-actions {
    flex-shrink: 0;
  }
</style>
