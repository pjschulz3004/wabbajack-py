<script lang="ts">
  import GameBadge from '../lib/components/GameBadge.svelte';

  let { modlist, onBack, onInstall }: {
    modlist: any;
    onBack: () => void;
    onInstall: (modlist: any) => void;
  } = $props();

  let readmeHtml = $state('');
  let readmeLoading = $state(false);
  let readmeError = $state(false);

  function formatSize(bytes: number): string {
    if (!bytes || bytes <= 0) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const val = bytes / Math.pow(1024, i);
    return `${val.toFixed(val >= 100 ? 0 : 1)} ${units[i]}`;
  }

  function formatDate(iso: string): string {
    if (!iso || iso.startsWith('1970')) return '—';
    try {
      return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch { return '—'; }
  }

  let dm = $derived(modlist.download_metadata ?? {});
  let links = $derived(modlist.links ?? {});

  // Fetch and render readme
  $effect(() => {
    const url = links.readme;
    if (!url) return;
    readmeLoading = true;
    readmeError = false;

    // If it's a raw GitHub markdown URL, fetch and render
    if (url.includes('raw.githubusercontent.com') && url.endsWith('.md')) {
      fetch(url).then(r => {
        if (!r.ok) throw new Error('Failed');
        return r.text();
      }).then(md => {
        // Basic markdown to HTML (headings, bold, links, lists, code blocks, paragraphs)
        readmeHtml = renderMarkdown(md);
      }).catch(() => {
        readmeError = true;
      }).finally(() => {
        readmeLoading = false;
      });
    } else {
      // It's a website URL, don't try to fetch (CORS)
      readmeLoading = false;
    }
  });

  function renderMarkdown(md: string): string {
    return md
      // Code blocks
      .replace(/```[\s\S]*?```/g, m => {
        const content = m.slice(3).replace(/^[^\n]*\n/, '').replace(/\n?```$/, '');
        return `<pre><code>${escHtml(content)}</code></pre>`;
      })
      // Inline code
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Images
      .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:8px;margin:0.5rem 0" loading="lazy" />')
      // Links
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      // Headings
      .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      // Bold
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      // Italic
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      // Horizontal rules
      .replace(/^---+$/gm, '<hr />')
      // Unordered lists
      .replace(/^[*-] (.+)$/gm, '<li>$1</li>')
      // Wrap consecutive <li> in <ul>
      .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
      // Paragraphs (double newline)
      .replace(/\n\n+/g, '</p><p>')
      .replace(/^/, '<p>')
      .replace(/$/, '</p>')
      // Clean up empty paragraphs
      .replace(/<p>\s*<\/p>/g, '')
      .replace(/<p>(<h[1-4]>)/g, '$1')
      .replace(/(<\/h[1-4]>)<\/p>/g, '$1')
      .replace(/<p>(<pre>)/g, '$1')
      .replace(/(<\/pre>)<\/p>/g, '$1')
      .replace(/<p>(<ul>)/g, '$1')
      .replace(/(<\/ul>)<\/p>/g, '$1')
      .replace(/<p>(<hr \/>)/g, '$1')
      .replace(/(<hr \/>)<\/p>/g, '$1');
  }

  function escHtml(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
</script>

<div class="detail">
  <!-- Back button -->
  <button class="back-btn" onclick={onBack}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
    Back to Gallery
  </button>

  <!-- Banner -->
  {#if links.image}
    <div class="banner">
      <img src={links.image} alt={modlist.title} />
    </div>
  {/if}

  <!-- Header -->
  <div class="header">
    <div class="header-main">
      <h1 class="title">{modlist.title}</h1>
      <div class="meta">
        <span class="author">by {modlist.author ?? 'Unknown'}</span>
        {#if modlist.game}
          <GameBadge game={modlist.game} />
        {/if}
        {#if modlist.version}
          <span class="version">v{modlist.version}</span>
        {/if}
        {#if modlist.nsfw}
          <span class="badge badge-error">NSFW</span>
        {/if}
        {#if modlist.official}
          <span class="badge badge-success">Official</span>
        {/if}
      </div>
    </div>
    <button class="btn btn-primary install-btn" onclick={() => onInstall(modlist)}>
      Install This Modlist
    </button>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat">
      <span class="stat-value">{formatSize(dm.SizeOfArchives)}</span>
      <span class="stat-label">Download</span>
    </div>
    <div class="stat">
      <span class="stat-value">{formatSize(dm.SizeOfInstalledFiles)}</span>
      <span class="stat-label">Install Size</span>
    </div>
    <div class="stat">
      <span class="stat-value">{(dm.NumberOfArchives ?? 0).toLocaleString()}</span>
      <span class="stat-label">Archives</span>
    </div>
    <div class="stat">
      <span class="stat-value">{(dm.NumberOfInstalledFiles ?? 0).toLocaleString()}</span>
      <span class="stat-label">Files</span>
    </div>
    {#if modlist.dateUpdated && !modlist.dateUpdated.startsWith('1970')}
      <div class="stat">
        <span class="stat-value">{formatDate(modlist.dateUpdated)}</span>
        <span class="stat-label">Updated</span>
      </div>
    {/if}
  </div>

  <!-- Description -->
  {#if modlist.description}
    <p class="description">{modlist.description}</p>
  {/if}

  <!-- Tags -->
  {#if (modlist.tags ?? []).length > 0}
    <div class="tags">
      {#each modlist.tags as tag}
        <span class="tag">{tag}</span>
      {/each}
    </div>
  {/if}

  <!-- Links -->
  <div class="links">
    {#if links.websiteURL}
      <a href={links.websiteURL} target="_blank" rel="noopener" class="link-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
        Website
      </a>
    {/if}
    {#if links.discordURL}
      <a href={links.discordURL} target="_blank" rel="noopener" class="link-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.3 5.8a18.4 18.4 0 00-4.5-1.4 12.7 12.7 0 00-.6 1.2 17 17 0 00-5.1 0 12.7 12.7 0 00-.6-1.2A18.3 18.3 0 005 5.8 19.5 19.5 0 001.7 17a18.5 18.5 0 005.6 2.9 13.7 13.7 0 001.2-2 12 12 0 01-1.9-.9l.4-.3a13.2 13.2 0 0011.4 0l.5.3a12 12 0 01-2 .9 13.7 13.7 0 001.2 2 18.5 18.5 0 005.7-2.9A19.4 19.4 0 0020.3 5.8z"/><circle cx="9" cy="13" r="1.5"/><circle cx="15" cy="13" r="1.5"/></svg>
        Discord
      </a>
    {/if}
    {#if links.readme && !links.readme.includes('raw.githubusercontent.com')}
      <a href={links.readme} target="_blank" rel="noopener" class="link-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        Readme
      </a>
    {/if}
    {#if links.readme?.includes('github.com') || links.readme?.includes('raw.githubusercontent.com')}
      {@const repoUrl = links.readme.replace('raw.githubusercontent.com', 'github.com').replace(/\/main\/.*/, '').replace(/\/refs\/.*/, '')}
      <a href={repoUrl} target="_blank" rel="noopener" class="link-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.9a3.4 3.4 0 00-1-2.6c3.2-.4 6.5-1.6 6.5-7A5.4 5.4 0 0020 4.8a5 5 0 00-.1-3.7s-1.2-.4-3.9 1.5a13.4 13.4 0 00-7 0C6.3.7 5.1 1.1 5.1 1.1a5 5 0 00-.1 3.7A5.4 5.4 0 003.5 9c0 5.4 3.3 6.6 6.4 7a3.4 3.4 0 00-1 2.1V22"/></svg>
        GitHub
      </a>
    {/if}
  </div>

  <!-- Readme content -->
  {#if readmeLoading}
    <div class="readme-section">
      <div class="readme-loading">Loading readme...</div>
    </div>
  {:else if readmeHtml}
    <div class="readme-section">
      <h2 class="readme-title">Readme</h2>
      <div class="readme-content">
        {@html readmeHtml}
      </div>
    </div>
  {:else if links.readme && !links.readme.includes('raw.githubusercontent.com')}
    <div class="readme-section">
      <h2 class="readme-title">Readme</h2>
      <p class="readme-external">
        This modlist's readme is hosted externally.
        <a href={links.readme} target="_blank" rel="noopener">Open in browser</a>
      </p>
    </div>
  {/if}
</div>

<style>
  .detail {
    max-width: 900px;
    margin: 0 auto;
    padding: 1rem 0;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 0.8rem;
    cursor: pointer;
    padding: 0.375rem 0;
    transition: color 0.15s;
    align-self: flex-start;
  }
  .back-btn:hover { color: var(--accent); }

  .banner {
    border-radius: var(--radius-lg);
    overflow: hidden;
    aspect-ratio: 21 / 9;
  }
  .banner img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .title {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    flex-wrap: wrap;
    margin-top: 0.375rem;
  }

  .author {
    font-size: 0.875rem;
    color: var(--text-secondary);
  }

  .version {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-secondary);
    background: var(--bg-tertiary);
    padding: 0.125rem 0.5rem;
    border-radius: var(--radius-sm);
  }

  .install-btn {
    padding: 0.625rem 1.5rem;
    font-size: 0.9rem;
    font-weight: 600;
    flex-shrink: 0;
  }

  /* Stats */
  .stats {
    display: flex;
    gap: 0;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }

  .stat {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.875rem 0.5rem;
    border-right: 1px solid var(--border);
  }
  .stat:last-child { border-right: none; }

  .stat-value {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-primary);
    font-family: var(--font-mono);
  }

  .stat-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    margin-top: 0.125rem;
  }

  .description {
    font-size: 0.9rem;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .tag {
    padding: 0.25rem 0.625rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 0.7rem;
    color: var(--text-secondary);
  }

  /* Links */
  .links {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .link-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.875rem;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-weight: 500;
    text-decoration: none;
    transition: border-color 0.15s, color 0.15s;
  }
  .link-btn:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  /* Readme */
  .readme-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
  }

  .readme-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border);
  }

  .readme-loading {
    color: var(--text-secondary);
    font-style: italic;
  }

  .readme-external {
    color: var(--text-secondary);
    font-size: 0.875rem;
  }
  .readme-external a {
    color: var(--accent);
  }

  .readme-content {
    font-size: 0.875rem;
    line-height: 1.7;
    color: var(--text-primary);
  }

  .readme-content :global(h1) { font-size: 1.4rem; margin: 1.5rem 0 0.75rem; font-weight: 700; color: var(--text-primary); }
  .readme-content :global(h2) { font-size: 1.15rem; margin: 1.25rem 0 0.625rem; font-weight: 700; color: var(--text-primary); }
  .readme-content :global(h3) { font-size: 1rem; margin: 1rem 0 0.5rem; font-weight: 600; color: var(--text-primary); }
  .readme-content :global(h4) { font-size: 0.9rem; margin: 0.75rem 0 0.375rem; font-weight: 600; color: var(--text-secondary); }
  .readme-content :global(p) { margin: 0.5rem 0; }
  .readme-content :global(a) { color: var(--accent); }
  .readme-content :global(code) { font-family: var(--font-mono); font-size: 0.8rem; background: var(--bg-tertiary); padding: 0.125rem 0.375rem; border-radius: 3px; }
  .readme-content :global(pre) { background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0.75rem; overflow-x: auto; margin: 0.75rem 0; }
  .readme-content :global(pre code) { background: none; padding: 0; font-size: 0.8rem; }
  .readme-content :global(ul) { padding-left: 1.5rem; margin: 0.5rem 0; }
  .readme-content :global(li) { margin: 0.25rem 0; }
  .readme-content :global(hr) { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }
  .readme-content :global(img) { max-width: 100%; border-radius: var(--radius); }
  .readme-content :global(strong) { color: var(--text-primary); }

  @media (max-width: 768px) {
    .stats { flex-wrap: wrap; }
    .stat { min-width: 33%; }
    .title { font-size: 1.25rem; }
    .install-btn { width: 100%; }
  }
</style>
