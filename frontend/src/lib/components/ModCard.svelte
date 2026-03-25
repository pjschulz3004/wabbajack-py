<script lang="ts">
  import GameBadge from './GameBadge.svelte';

  let { modlist, onselect }: { modlist: any; onselect?: (modlist: any) => void } = $props();

  let imgLoaded = $state(false);
  let imgError = $state(false);

  function formatSize(bytes: number): string {
    if (!bytes || bytes <= 0) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const val = bytes / Math.pow(1024, i);
    return `${val.toFixed(val >= 100 ? 0 : 1)} ${units[i]}`;
  }

  let tags = $derived((modlist.tags ?? []).slice(0, 4));
</script>

<button class="mod-card" onclick={() => onselect?.(modlist)}>
  <div class="banner">
    {#if !imgLoaded && !imgError}
      <div class="skeleton animate-pulse"></div>
    {/if}
    {#if imgError}
      <div class="img-fallback">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path d="M21 15l-5-5L5 21" />
        </svg>
      </div>
    {:else}
      <img
        src={modlist.links?.imageUri ?? modlist.image}
        alt={modlist.title}
        loading="lazy"
        class:loaded={imgLoaded}
        onload={() => imgLoaded = true}
        onerror={() => imgError = true}
      />
    {/if}
  </div>

  <div class="body">
    <h3 class="title">{modlist.title}</h3>

    <div class="meta-row">
      <span class="author">{modlist.author ?? 'Unknown'}</span>
      {#if modlist.game}
        <GameBadge game={modlist.game} />
      {/if}
    </div>

    {#if modlist.description}
      <p class="description">{modlist.description}</p>
    {/if}

    {#if tags.length > 0}
      <div class="tags">
        {#each tags as tag}
          <span class="tag">{tag}</span>
        {/each}
      </div>
    {/if}

    <div class="sizes">
      {#if modlist.downloadSize ?? modlist.download_size}
        <span class="size-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          {formatSize(modlist.downloadSize ?? modlist.download_size)}
        </span>
      {/if}
      {#if modlist.installSize ?? modlist.install_size}
        <span class="size-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
          </svg>
          {formatSize(modlist.installSize ?? modlist.install_size)}
        </span>
      {/if}
    </div>
  </div>
</button>

<style>
  .mod-card {
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
    text-align: left;
    color: inherit;
    font: inherit;
    width: 100%;
    padding: 0;
  }

  .mod-card:hover {
    border-color: var(--accent);
    box-shadow: 0 0 20px var(--accent-glow), 0 8px 32px rgba(0, 0, 0, 0.3);
    transform: translateY(-2px);
  }

  .banner {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: var(--bg-tertiary);
  }

  .banner img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity 0.3s ease;
  }

  .banner img.loaded {
    opacity: 1;
  }

  .skeleton {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      110deg,
      var(--bg-tertiary) 8%,
      var(--bg-secondary) 18%,
      var(--bg-tertiary) 33%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s linear infinite;
  }

  @keyframes shimmer {
    to { background-position: -200% 0; }
  }

  .img-fallback {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
  }

  .body {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    padding: 0.75rem;
    flex: 1;
  }

  .title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .author {
    font-size: 0.75rem;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .description {
    font-size: 0.75rem;
    color: var(--text-secondary);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin-top: auto;
  }

  .tag {
    display: inline-block;
    padding: 0.0625rem 0.375rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 0.625rem;
    color: var(--text-secondary);
    white-space: nowrap;
  }

  .sizes {
    display: flex;
    gap: 0.75rem;
    padding-top: 0.375rem;
    border-top: 1px solid var(--border);
    margin-top: 0.375rem;
  }

  .size-item {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.7rem;
    color: var(--text-secondary);
  }

  .size-item svg {
    flex-shrink: 0;
    opacity: 0.7;
  }
</style>
