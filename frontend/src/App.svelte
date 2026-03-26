<script lang="ts">
  import { connected, progress, installState, connectWs } from './lib/stores/ws';
  import Gallery from './routes/Gallery.svelte';
  import ModDetail from './routes/ModDetail.svelte';
  import Install from './routes/Install.svelte';
  import Downloads from './routes/Downloads.svelte';
  import Profiles from './routes/Profiles.svelte';
  import Settings from './routes/Settings.svelte';

  type Page = 'gallery' | 'moddetail' | 'install' | 'downloads' | 'profiles' | 'settings';

  let currentPage = $state<Page>('gallery');
  let selectedModlist = $state<any>(null);
  let sidebarOpen = $state(false);
  let appVersion = $state('');

  // Fetch version from OpenAPI metadata (lightweight, no git operations)
  $effect(() => {
    fetch('/openapi.json').then(r => r.json()).then(d => {
      if (d.info?.version) appVersion = d.info.version;
    }).catch(() => { appVersion = '?'; });
  });

  function openModDetail(modlist: any) {
    selectedModlist = modlist;
    currentPage = 'moddetail';
  }

  function navigateToInstall(modlist?: any) {
    selectedModlist = modlist ?? null;
    currentPage = 'install';
  }

  const navItems: { id: Page; label: string; icon: string }[] = [
    { id: 'gallery',   label: 'Gallery',   icon: 'M4 6h16M4 10h16M4 14h16M4 18h16' },
    { id: 'install',   label: 'Install',   icon: 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3' },
    { id: 'downloads', label: 'Downloads', icon: 'M12 2v20m0 0l-7-7m7 7l7-7' },
    { id: 'profiles',  label: 'Profiles',  icon: 'M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 3a4 4 0 100 8 4 4 0 000-8' },
    { id: 'settings',  label: 'Settings',  icon: 'M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09a1.65 1.65 0 00-1.08-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09a1.65 1.65 0 001.51-1.08 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001.08 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1.08z' },
  ];

  // Derive install-in-progress from the WS store
  let isInstalling = $derived(
    $installState?.type === 'state' && $installState?.state === 'installing'
  );

  let progressPercent = $derived(
    $progress?.percent ?? 0
  );

  $effect(() => {
    connectWs();
  });
</script>

<div class="app-shell">
  <!-- Sidebar -->
  {#if sidebarOpen}
    <div class="sidebar-overlay" onclick={() => sidebarOpen = false} role="presentation"></div>
  {/if}
  <aside class="sidebar" class:open={sidebarOpen}>
    <div class="sidebar-header">
      <div class="logo">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" aria-hidden="true">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
        <div class="logo-text">
          <span class="logo-name">wabbajack-py</span>
          <span class="logo-version">v{appVersion}</span>
        </div>
      </div>
    </div>

    <nav class="nav" aria-label="Main navigation">
      {#each navItems as item}
        <button
          class="nav-item"
          class:active={currentPage === item.id}
          aria-current={currentPage === item.id ? 'page' : undefined}
          onclick={() => { currentPage = item.id; sidebarOpen = false; }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d={item.icon} />
          </svg>
          <span>{item.label}</span>
        </button>
      {/each}
    </nav>

    <div class="sidebar-footer">
      <div class="ws-status" class:ws-connected={$connected}>
        <span class="ws-dot"></span>
        <span class="ws-label">{$connected ? 'Connected' : 'Disconnected'}</span>
      </div>
    </div>
  </aside>

  <!-- Main content -->
  <main class="main">
    <!-- Header bar -->
    <header class="header">
      <button class="hamburger" onclick={() => sidebarOpen = !sidebarOpen} aria-label="Toggle navigation">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <h2 class="page-title">{currentPage === 'moddetail' ? selectedModlist?.title ?? 'Modlist' : navItems.find(n => n.id === currentPage)?.label ?? ''}</h2>

      {#if isInstalling}
        <button class="install-indicator" onclick={() => currentPage = 'install'}>
          <span class="install-label">Installing...</span>
          <div class="mini-progress">
            <div class="mini-progress-bar" style:width="{progressPercent}%"></div>
          </div>
          <span class="install-pct">{progressPercent.toFixed(0)}%</span>
        </button>
      {/if}
    </header>

    <!-- Page content -->
    <div class="content">
      <!-- Gallery stays mounted to preserve filter/search/scroll state -->
      <div style:display={currentPage === 'gallery' ? 'contents' : 'none'}>
        <Gallery onSelect={openModDetail} />
      </div>
      {#if currentPage === 'moddetail' && selectedModlist}
        <ModDetail modlist={selectedModlist} onBack={() => currentPage = 'gallery'} onInstall={navigateToInstall} />
      {:else if currentPage === 'install'}
        <Install modlist={selectedModlist} />
      {:else if currentPage === 'downloads'}
        <Downloads />
      {:else if currentPage === 'profiles'}
        <Profiles />
      {:else if currentPage === 'settings'}
        <Settings />
      {/if}
    </div>
  </main>
</div>

<style>
  .app-shell {
    display: flex;
    height: 100vh;
    height: 100dvh;
    overflow: hidden;
  }

  /* ─── Sidebar ─── */
  .sidebar {
    width: 200px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
  }

  .sidebar-header {
    padding: 1rem 0.75rem;
    border-bottom: 1px solid var(--border);
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .logo-text {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
  }

  .logo-name {
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--text-primary);
  }

  .logo-version {
    font-size: 0.625rem;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }

  /* ─── Navigation ─── */
  .nav {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    padding: 0.5rem;
    flex: 1;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.5rem 0.625rem;
    min-height: 44px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.825rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    text-align: left;
    width: 100%;
  }

  .nav-item:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .nav-item.active {
    background: var(--accent-dim);
    color: var(--accent);
  }

  .nav-item.active svg {
    stroke: var(--accent);
  }

  /* ─── Sidebar footer ─── */
  .sidebar-footer {
    padding: 0.75rem;
    border-top: 1px solid var(--border);
  }

  .ws-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .ws-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--error);
    transition: background 0.3s;
  }

  .ws-connected .ws-dot {
    background: var(--success);
    box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
  }

  .ws-label {
    font-size: 0.7rem;
    color: var(--text-secondary);
  }

  /* ─── Main area ─── */
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-width: 0;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 1.25rem;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .page-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  /* ─── Install indicator ─── */
  .install-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-left: auto;
    padding: 0.375rem 0.75rem;
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    border-radius: var(--radius-sm);
    color: var(--accent);
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
  }

  .install-indicator:hover {
    background: var(--accent-glow);
  }

  .install-label {
    white-space: nowrap;
  }

  .mini-progress {
    width: 60px;
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: 2px;
    overflow: hidden;
  }

  .mini-progress-bar {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .install-pct {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    min-width: 2.5em;
    text-align: right;
  }

  /* ─── Hamburger ─── */
  .hamburger {
    display: none;
    align-items: center;
    justify-content: center;
    padding: 0.5rem;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: var(--radius-sm);
    min-height: 44px;
    min-width: 44px;
  }

  .hamburger:hover {
    color: var(--text-primary);
    background: var(--bg-tertiary);
  }

  .sidebar-overlay {
    display: none;
  }

  /* ─── Content area ─── */
  .content {
    flex: 1;
    overflow-y: auto;
    padding: 1rem 1.25rem;
  }

  @media (max-width: 768px) {
    .hamburger { display: flex; }

    .sidebar {
      position: fixed;
      left: 0;
      top: 0;
      bottom: 0;
      z-index: 100;
      transform: translateX(-100%);
      transition: transform 0.2s ease;
    }

    .sidebar.open {
      transform: translateX(0);
    }

    .sidebar-overlay {
      display: block;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.5);
      z-index: 99;
    }

    .content {
      padding: 0.75rem;
    }
  }

</style>
