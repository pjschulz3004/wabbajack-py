<script lang="ts">
  import type { WsMessage } from '../stores/ws';

  interface Props {
    logs: WsMessage[];
  }

  let { logs }: Props = $props();

  type LogLevel = 'info' | 'warning' | 'error' | 'debug';

  let autoScroll = $state(true);
  let activeFilters = $state<Set<LogLevel>>(new Set(['info', 'warning', 'error', 'debug']));
  let scrollContainer: HTMLDivElement | undefined = $state();

  // Virtual scrolling
  const LINE_HEIGHT = 20;
  const BUFFER = 20;
  let scrollTop = $state(0);
  let containerHeight = $state(400);

  let filteredLogs = $derived(
    logs.filter(log => activeFilters.has((log.level as LogLevel) ?? 'info'))
  );

  let visibleStart = $derived(Math.max(0, Math.floor(scrollTop / LINE_HEIGHT) - BUFFER));
  let visibleEnd = $derived(
    Math.min(filteredLogs.length, Math.ceil((scrollTop + containerHeight) / LINE_HEIGHT) + BUFFER)
  );
  let visibleLogs = $derived(filteredLogs.slice(visibleStart, visibleEnd));
  let totalHeight = $derived(filteredLogs.length * LINE_HEIGHT);
  let offsetY = $derived(visibleStart * LINE_HEIGHT);

  function toggleFilter(level: LogLevel) {
    const next = new Set(activeFilters);
    if (next.has(level)) {
      if (next.size > 1) next.delete(level);
    } else {
      next.add(level);
    }
    activeFilters = next;
  }

  function handleScroll() {
    if (!scrollContainer) return;
    scrollTop = scrollContainer.scrollTop;
    containerHeight = scrollContainer.clientHeight;
    const atBottom = scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight < 40;
    autoScroll = atBottom;
  }

  function scrollToBottom() {
    autoScroll = true;
    scrollContainer?.scrollTo({ top: scrollContainer.scrollHeight, behavior: 'smooth' });
  }

  function levelColor(level: string): string {
    switch (level) {
      case 'error': return 'var(--error)';
      case 'warning': return 'var(--warning)';
      case 'debug': return 'var(--text-secondary)';
      default: return 'var(--text-primary)';
    }
  }

  function levelTag(level: string): string {
    switch (level) {
      case 'error': return 'ERR';
      case 'warning': return 'WRN';
      case 'debug': return 'DBG';
      default: return 'INF';
    }
  }

  $effect(() => {
    // Re-run whenever filteredLogs changes (length tracked by access)
    filteredLogs.length;
    if (autoScroll && scrollContainer) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
  });
</script>

<div class="log-viewer">
  <div class="log-toolbar">
    <div class="filter-group">
      {#each ['info', 'warning', 'error', 'debug'] as level}
        <button
          class="filter-btn"
          class:active={activeFilters.has(level as LogLevel)}
          class:filter-info={level === 'info'}
          class:filter-warning={level === 'warning'}
          class:filter-error={level === 'error'}
          class:filter-debug={level === 'debug'}
          aria-pressed={activeFilters.has(level as LogLevel)}
          onclick={() => toggleFilter(level as LogLevel)}
        >
          {level}
        </button>
      {/each}
    </div>

    <div class="toolbar-right">
      <span class="log-count">{filteredLogs.length.toLocaleString()} lines</span>
      {#if !autoScroll}
        <button class="btn btn-sm btn-ghost scroll-btn" onclick={scrollToBottom}>
          Auto-scroll
        </button>
      {/if}
    </div>
  </div>

  <div
    class="log-scroll"
    bind:this={scrollContainer}
    onscroll={handleScroll}
  >
    {#if filteredLogs.length > 0}
      <div class="log-spacer" style="height: {totalHeight}px; position: relative;">
        <div style="position: absolute; top: {offsetY}px; left: 0; right: 0;">
          {#each visibleLogs as entry, i (visibleStart + i)}
            <div class="log-line" style="color: {levelColor(entry.level ?? 'info')}">
              {#if entry.timestamp}
                <span class="log-ts">{entry.timestamp}</span>
              {/if}
              <span class="log-level" style="color: {levelColor(entry.level ?? 'info')}">
                [{levelTag(entry.level ?? 'info')}]
              </span>
              <span class="log-msg">{entry.message ?? ''}</span>
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <div class="log-empty">No log entries{activeFilters.size < 4 ? ' matching filter' : ''}</div>
    {/if}
  </div>
</div>

<style>
  .log-viewer {
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    height: 100%;
    min-height: 200px;
  }

  .log-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .filter-group {
    display: flex;
    gap: 0.25rem;
    flex-shrink: 0;
  }

  .filter-btn {
    padding: 0.375rem 0.625rem;
    min-height: 32px;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: opacity 0.15s, color 0.15s, border-color 0.15s;
    opacity: 0.5;
  }

  .filter-btn.active {
    opacity: 1;
  }

  .filter-btn.active.filter-info {
    border-color: var(--text-primary);
    color: var(--text-primary);
  }
  .filter-btn.active.filter-warning {
    border-color: var(--warning);
    color: var(--warning);
  }
  .filter-btn.active.filter-error {
    border-color: var(--error);
    color: var(--error);
  }
  .filter-btn.active.filter-debug {
    border-color: var(--text-secondary);
    color: var(--text-secondary);
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .log-count {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  .scroll-btn {
    animation: pulse 2s ease-in-out infinite;
  }

  .log-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    line-height: 1.6;
  }

  .log-line {
    display: flex;
    gap: 0.5rem;
    padding: 0 0.25rem;
    border-radius: 2px;
    white-space: nowrap;
    overflow: hidden;
    height: 20px;
    align-items: center;
  }

  .log-line:hover {
    background: rgba(255, 255, 255, 0.03);
  }

  .log-ts {
    color: var(--text-secondary);
    opacity: 0.6;
    flex-shrink: 0;
    font-size: 0.7rem;
  }

  .log-level {
    flex-shrink: 0;
    font-weight: 700;
    font-size: 0.7rem;
    min-width: 3.5ch;
  }

  .log-msg {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .log-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-secondary);
    font-style: italic;
    font-family: var(--font-mono);
  }
</style>
