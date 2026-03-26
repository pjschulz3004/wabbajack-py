<script lang="ts">
  import { api } from '../lib/api';
  import ModCard from '../lib/components/ModCard.svelte';

  let modlists = $state<any[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let searchQuery = $state('');
  let gameFilter = $state('all');
  let showNsfw = $state(false);

  type SortKey = 'recommended' | 'updated' | 'install_size' | 'download_size' | 'mod_count' | 'name';
  let sortKey = $state<SortKey>('recommended');

  $effect(() => {
    fetchGallery();
  });

  async function fetchGallery() {
    loading = true;
    error = null;
    try {
      modlists = await api.gallery();
    } catch (e: any) {
      error = e.message ?? 'Failed to fetch modlist gallery';
    } finally {
      loading = false;
    }
  }

  let games = $derived.by(() => {
    const set = new Set<string>();
    for (const m of modlists) {
      if (m.game) set.add(m.game);
    }
    return Array.from(set).sort();
  });

  function getDm(m: any) { return m.download_metadata ?? {}; }

  let filtered = $derived.by(() => {
    let result = modlists;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(m =>
        (m.title?.toLowerCase().includes(q)) ||
        (m.author?.toLowerCase().includes(q)) ||
        (m.description?.toLowerCase().includes(q))
      );
    }

    if (gameFilter !== 'all') {
      result = result.filter(m => m.game === gameFilter);
    }

    if (!showNsfw) {
      result = result.filter(m => !m.nsfw);
    }

    // Sort
    const sorted = [...result];
    switch (sortKey) {
      case 'recommended':
        sorted.sort((a, b) => {
          // Official first, then by dateUpdated descending
          const ao = a.official ? 1 : 0, bo = b.official ? 1 : 0;
          if (ao !== bo) return bo - ao;
          const ad = a.dateUpdated ?? '', bd = b.dateUpdated ?? '';
          return bd.localeCompare(ad);
        });
        break;
      case 'updated':
        sorted.sort((a, b) => (b.dateUpdated ?? '').localeCompare(a.dateUpdated ?? ''));
        break;
      case 'install_size':
        sorted.sort((a, b) => (getDm(b).SizeOfInstalledFiles ?? 0) - (getDm(a).SizeOfInstalledFiles ?? 0));
        break;
      case 'download_size':
        sorted.sort((a, b) => (getDm(b).SizeOfArchives ?? 0) - (getDm(a).SizeOfArchives ?? 0));
        break;
      case 'mod_count':
        sorted.sort((a, b) => (getDm(b).NumberOfArchives ?? 0) - (getDm(a).NumberOfArchives ?? 0));
        break;
      case 'name':
        sorted.sort((a, b) => (a.title ?? '').localeCompare(b.title ?? ''));
        break;
    }
    return sorted;
  });

  let { onInstall }: { onInstall?: (modlist: any) => void } = $props();

  function handleSelect(modlist: any) {
    onInstall?.(modlist);
  }
</script>

<div class="gallery">
  <div class="toolbar">
    <div class="search-wrap">
      <label for="gallery-search" class="sr-only">Search modlists</label>
      <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        id="gallery-search"
        type="text"
        placeholder="Search modlists..."
        bind:value={searchQuery}
        class="search-input"
      />
    </div>

    <label for="gallery-game-filter" class="sr-only">Filter by game</label>
    <select id="gallery-game-filter" bind:value={gameFilter} class="game-select">
      <option value="all">All Games</option>
      {#each games as game}
        <option value={game}>{game}</option>
      {/each}
    </select>

    <label for="gallery-sort" class="sr-only">Sort by</label>
    <select id="gallery-sort" bind:value={sortKey} class="sort-select">
      <option value="recommended">Recommended</option>
      <option value="updated">Recently Updated</option>
      <option value="install_size">Install Size</option>
      <option value="download_size">Download Size</option>
      <option value="mod_count">Mod Count</option>
      <option value="name">A — Z</option>
    </select>

    <button
      class="nsfw-toggle"
      class:active={showNsfw}
      aria-pressed={showNsfw}
      onclick={() => showNsfw = !showNsfw}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        {#if showNsfw}
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        {:else}
          <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" />
          <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" />
          <line x1="1" y1="1" x2="23" y2="23" />
        {/if}
      </svg>
      NSFW
    </button>

    <span class="result-count">{filtered.length} lists</span>
  </div>

  {#if loading}
    <div class="grid">
      {#each Array(9) as _}
        <div class="skeleton-card">
          <div class="skeleton-banner"></div>
          <div class="skeleton-body">
            <div class="skeleton-line w-75"></div>
            <div class="skeleton-line w-50"></div>
            <div class="skeleton-line w-full"></div>
          </div>
        </div>
      {/each}
    </div>
  {:else if error}
    <div class="error-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="12" cy="12" r="10" />
        <line x1="15" y1="9" x2="9" y2="15" />
        <line x1="9" y1="9" x2="15" y2="15" />
      </svg>
      <h3>Failed to load gallery</h3>
      <p>{error}</p>
      <button class="btn btn-primary" onclick={fetchGallery}>Retry</button>
    </div>
  {:else if filtered.length === 0}
    <div class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
        <line x1="8" y1="11" x2="14" y2="11" />
      </svg>
      <h3>No modlists found</h3>
      <p>Try adjusting your search or filters</p>
    </div>
  {:else}
    <div class="grid">
      {#each filtered as modlist (modlist.links?.machineURL ?? modlist.title)}
        <ModCard {modlist} onselect={handleSelect} />
      {/each}
    </div>
  {/if}
</div>

<style>
  .gallery {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .search-wrap {
    position: relative;
    flex: 1;
    min-width: 200px;
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

  .game-select, .sort-select {
    width: auto;
    min-width: 140px;
  }

  .nsfw-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    letter-spacing: 0.03em;
  }

  .nsfw-toggle:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .nsfw-toggle.active {
    background: rgba(248, 113, 113, 0.1);
    border-color: var(--error);
    color: var(--error);
  }

  .result-count {
    font-size: 0.75rem;
    color: var(--text-secondary);
    white-space: nowrap;
    margin-left: auto;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    align-content: start;
  }

  @media (max-width: 1200px) {
    .grid { grid-template-columns: repeat(2, 1fr); }
  }

  @media (max-width: 900px) {
    .grid { grid-template-columns: 1fr; }
  }

  @media (max-width: 768px) {
    .toolbar { flex-direction: column; align-items: stretch; }
    .result-count { margin-left: 0; }
  }

  /* Skeleton cards */
  .skeleton-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }

  .skeleton-banner {
    aspect-ratio: 16 / 9;
    background: linear-gradient(110deg, var(--bg-tertiary) 8%, var(--bg-secondary) 18%, var(--bg-tertiary) 33%);
    background-size: 200% 100%;
    animation: shimmer 1.5s linear infinite;
  }

  .skeleton-body {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.75rem;
  }

  .skeleton-line {
    height: 0.75rem;
    border-radius: var(--radius-sm);
    background: linear-gradient(110deg, var(--bg-tertiary) 8%, var(--bg-secondary) 18%, var(--bg-tertiary) 33%);
    background-size: 200% 100%;
    animation: shimmer 1.5s linear infinite;
  }

  .w-75 { width: 75%; }
  .w-50 { width: 50%; }
  .w-full { width: 100%; }

  /* Empty / error states */
  .error-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 3rem 1rem;
    text-align: center;
  }

  .error-state svg { color: var(--error); }
  .empty-state svg { color: var(--text-secondary); }

  .error-state h3,
  .empty-state h3 {
    font-size: 1rem;
    color: var(--text-primary);
  }

  .error-state p,
  .empty-state p {
    font-size: 0.85rem;
    color: var(--text-secondary);
    max-width: 360px;
  }
</style>
