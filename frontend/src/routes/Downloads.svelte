<script lang="ts">
  import { installState, sendWs } from '../lib/stores/ws';
  import { api } from '../lib/api';

  interface Archive {
    name: string;
    source_type: string;
    size: number;
    status: 'done' | 'downloading' | 'failed' | 'pending';
  }

  type SortKey = 'name' | 'source_type' | 'size' | 'status';
  type SortDir = 'asc' | 'desc';

  let archives = $state<Archive[]>([]);
  let loading = $state(true);
  let error = $state('');
  let searchQuery = $state('');
  let sortKey = $state<SortKey>('name');
  let sortDir = $state<SortDir>('asc');

  // Auto-subscribe to install state (no leak)
  $effect(() => {
    const st = $installState;
    if (st?.archives) {
      archives = st.archives;
      loading = false;
    }
  });

  // Try fetching status on mount
  $effect(() => {
    api.installStatus().then((res: any) => {
      if (res.archives) {
        archives = res.archives;
      }
      loading = false;
    }).catch(() => {
      loading = false;
    });
  });

  let filtered = $derived(
    archives.filter(a =>
      a.name.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  let sorted = $derived((() => {
    const items = [...filtered];
    items.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortKey === 'source_type') cmp = a.source_type.localeCompare(b.source_type);
      else if (sortKey === 'size') cmp = (a.size ?? 0) - (b.size ?? 0);
      else if (sortKey === 'status') cmp = statusOrder(a.status) - statusOrder(b.status);
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return items;
  })());

  // Virtual scrolling
  const ROW_HEIGHT = 36;
  const ROW_BUFFER = 20;
  let dlScrollTop = $state(0);
  let dlContainerHeight = $state(500);
  let tableWrap: HTMLDivElement | undefined = $state();

  let dlVisibleStart = $derived(Math.max(0, Math.floor(dlScrollTop / ROW_HEIGHT) - ROW_BUFFER));
  let dlVisibleEnd = $derived(
    Math.min(sorted.length, Math.ceil((dlScrollTop + dlContainerHeight) / ROW_HEIGHT) + ROW_BUFFER)
  );
  let visibleRows = $derived(sorted.slice(dlVisibleStart, dlVisibleEnd));
  let topSpacerHeight = $derived(dlVisibleStart * ROW_HEIGHT);
  let bottomSpacerHeight = $derived(Math.max(0, (sorted.length - dlVisibleEnd) * ROW_HEIGHT));

  function handleTableScroll() {
    if (!tableWrap) return;
    dlScrollTop = tableWrap.scrollTop;
    dlContainerHeight = tableWrap.clientHeight;
  }

  let counts = $derived.by(() => {
    const c = { total: archives.length, done: 0, downloading: 0, failed: 0, pending: 0 };
    for (const a of archives) {
      if (a.status === 'done') c.done++;
      else if (a.status === 'downloading') c.downloading++;
      else if (a.status === 'failed') c.failed++;
      else if (a.status === 'pending') c.pending++;
    }
    return c;
  });

  function statusOrder(s: string): number {
    switch (s) {
      case 'downloading': return 0;
      case 'failed': return 1;
      case 'pending': return 2;
      case 'done': return 3;
      default: return 4;
    }
  }

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      sortDir = 'asc';
    }
  }

  function formatSize(bytes: number): string {
    if (!bytes || bytes === 0) return '--';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(2) + ' GB';
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' ^' : ' v';
  }

  function retryFailed() {
    const failed = archives.filter(a => a.status === 'failed').map(a => a.name);
    if (failed.length === 0) return;
    // Send retry via WS or API - use WS command
    sendWs({ type: 'retry_failed', names: failed });
  }

  function exportFailed() {
    const failed = archives.filter(a => a.status === 'failed');
    if (failed.length === 0) return;
    const text = failed.map(a => `${a.name}\t${a.source_type}\t${formatSize(a.size)}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'failed-downloads.txt';
    link.click();
    URL.revokeObjectURL(url);
  }
</script>

<div class="downloads-page">
  <div class="page-header">
    <div class="stat-badges">
      <span class="badge badge-accent">{counts.total} total</span>
      {#if counts.done > 0}
        <span class="badge badge-success">{counts.done} done</span>
      {/if}
      {#if counts.downloading > 0}
        <span class="badge badge-warning">{counts.downloading} active</span>
      {/if}
      {#if counts.failed > 0}
        <span class="badge badge-error">{counts.failed} failed</span>
      {/if}
      {#if counts.pending > 0}
        <span class="badge badge-neutral">{counts.pending} pending</span>
      {/if}
    </div>
  </div>

  <div class="toolbar">
    <div class="search-wrap">
      <label for="dl-search" class="sr-only">Filter archives</label>
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input
        id="dl-search"
        type="text"
        class="search-input"
        placeholder="Filter archives..."
        bind:value={searchQuery}
      />
    </div>
    <div class="toolbar-actions">
      <button
        class="btn btn-ghost btn-sm"
        onclick={retryFailed}
        disabled={counts.failed === 0}
      >
        Retry Failed
      </button>
      <button
        class="btn btn-ghost btn-sm"
        onclick={exportFailed}
        disabled={counts.failed === 0}
      >
        Export Failed
      </button>
    </div>
  </div>

  {#if loading}
    <div class="loading">Loading archive list...</div>
  {:else if archives.length === 0}
    <div class="empty">
      <p>No archives loaded</p>
      <p class="empty-hint">Start an installation to populate the download list.</p>
    </div>
  {:else}
    <div class="table-wrap" bind:this={tableWrap} onscroll={handleTableScroll}>
      <table class="dl-table">
        <thead>
          <tr>
            <th class="col-status" role="button" tabindex="0" aria-sort={sortKey === 'status' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onclick={() => toggleSort('status')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleSort('status')}>
              Status{sortIndicator('status')}
            </th>
            <th class="col-name" role="button" tabindex="0" aria-sort={sortKey === 'name' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onclick={() => toggleSort('name')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleSort('name')}>
              Name{sortIndicator('name')}
            </th>
            <th class="col-source" role="button" tabindex="0" aria-sort={sortKey === 'source_type' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onclick={() => toggleSort('source_type')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleSort('source_type')}>
              Source{sortIndicator('source_type')}
            </th>
            <th class="col-size" role="button" tabindex="0" aria-sort={sortKey === 'size' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} onclick={() => toggleSort('size')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleSort('size')}>
              Size{sortIndicator('size')}
            </th>
          </tr>
        </thead>
        <tbody>
          {#if topSpacerHeight > 0}
            <tr class="spacer"><td colspan="4" style="height: {topSpacerHeight}px; padding: 0; border: none;"></td></tr>
          {/if}
          {#each visibleRows as archive (archive.name)}
            <tr class="dl-row" class:row-failed={archive.status === 'failed'}>
              <td class="col-status">
                {#if archive.status === 'done'}
                  <span class="status-icon done" title="Complete">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
                  </span>
                {:else if archive.status === 'downloading'}
                  <span class="status-icon active" title="Downloading">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2.5">
                      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                    </svg>
                  </span>
                {:else if archive.status === 'failed'}
                  <span class="status-icon failed" title="Failed">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--error)" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  </span>
                {:else}
                  <span class="status-icon pending" title="Pending">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                  </span>
                {/if}
              </td>
              <td class="col-name" title={archive.name}>{archive.name}</td>
              <td class="col-source">
                <span class="source-badge">{archive.source_type}</span>
              </td>
              <td class="col-size">{formatSize(archive.size)}</td>
            </tr>
          {/each}
          {#if bottomSpacerHeight > 0}
            <tr class="spacer"><td colspan="4" style="height: {bottomSpacerHeight}px; padding: 0; border: none;"></td></tr>
          {/if}
        </tbody>
      </table>
    </div>

    <div class="table-footer">
      Showing {sorted.length} of {archives.length} archives
    </div>
  {/if}
</div>

<style>
  .downloads-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1.5rem;
    height: 100%;
    overflow: hidden;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  }

  .page-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .stat-badges {
    display: flex;
    gap: 0.375rem;
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    flex-shrink: 0;
  }

  .search-wrap {
    position: relative;
    flex: 1;
    max-width: 360px;
  }

  .search-icon {
    position: absolute;
    left: 0.625rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-secondary);
    pointer-events: none;
  }

  .search-input {
    padding-left: 2rem;
  }

  .toolbar-actions {
    display: flex;
    gap: 0.375rem;
  }

  .loading, .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: var(--text-secondary);
    gap: 0.25rem;
  }

  .empty-hint {
    font-size: 0.8rem;
    opacity: 0.6;
  }

  .table-wrap {
    flex: 1;
    overflow-y: auto;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--bg-secondary);
  }

  .dl-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.825rem;
  }

  .dl-table thead {
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .dl-table th {
    background: var(--bg-tertiary);
    padding: 0.5rem 0.75rem;
    text-align: left;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }

  .dl-table th:hover {
    color: var(--accent);
  }

  .dl-row {
    height: 36px;
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }

  .dl-row:hover {
    background: rgba(255, 255, 255, 0.02);
  }

  .dl-row.row-failed {
    background: rgba(248, 113, 113, 0.04);
  }

  .dl-table td {
    padding: 0.4rem 0.75rem;
    vertical-align: middle;
  }

  .col-status {
    width: 60px;
    text-align: center;
  }

  .col-name {
    max-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--font-mono);
    font-size: 0.8rem;
  }

  .col-source {
    width: 110px;
  }

  .col-size {
    width: 100px;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    text-align: right;
    color: var(--text-secondary);
  }

  .status-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .status-icon.active {
    animation: spin 1s linear infinite;
  }

  /* spin keyframe from global app.css */

  .source-badge {
    display: inline-block;
    padding: 0.1rem 0.4rem;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    background: var(--accent-dim);
    color: var(--accent);
    border-radius: var(--radius-sm);
  }

  .table-footer {
    text-align: right;
    font-size: 0.7rem;
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  @media (max-width: 600px) {
    .toolbar { flex-wrap: wrap; }
    .search-wrap { max-width: 100%; }
  }
</style>
