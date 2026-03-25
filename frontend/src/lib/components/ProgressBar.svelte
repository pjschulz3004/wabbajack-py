<script lang="ts">
  interface Props {
    current: number;
    total: number;
    phase: string;
    speed: string;
    eta: string;
  }

  let { current, total, phase, speed, eta }: Props = $props();

  let percentage = $derived(total > 0 ? Math.min(100, (current / total) * 100) : 0);
  let isActive = $derived(current > 0 && current < total);
  let displayPercent = $derived(percentage.toFixed(1));
</script>

<div class="progress-wrapper">
  <div class="progress-header">
    <span class="phase-label">{phase}</span>
    <span class="stats">
      {#if speed}
        <span class="speed">{speed}</span>
      {/if}
      {#if eta}
        <span class="eta">ETA {eta}</span>
      {/if}
    </span>
  </div>

  <div class="progress-track">
    <div
      class="progress-fill"
      class:active={isActive}
      style="width: {percentage}%"
    >
      {#if percentage > 8}
        <span class="progress-text-inner">{displayPercent}%</span>
      {/if}
    </div>
    {#if percentage <= 8}
      <span class="progress-text-outer">{displayPercent}%</span>
    {/if}
  </div>

  <div class="progress-footer">
    <span class="count">{current.toLocaleString()} / {total.toLocaleString()}</span>
  </div>
</div>

<style>
  .progress-wrapper {
    width: 100%;
    padding: 1rem 0;
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .phase-label {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent);
  }

  .stats {
    display: flex;
    gap: 1rem;
    font-size: 0.75rem;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }

  .speed {
    color: var(--success);
  }

  .eta {
    color: var(--warning);
  }

  .progress-track {
    position: relative;
    width: 100%;
    height: 28px;
    background: var(--bg-tertiary);
    border-radius: var(--radius);
    overflow: hidden;
    border: 1px solid var(--border);
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent-hover));
    border-radius: var(--radius);
    transition: width 0.4s ease;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 0.5rem;
    min-width: 0;
    position: relative;
    overflow: hidden;
  }

  .progress-fill.active {
    animation: bar-pulse 2s ease-in-out infinite;
  }

  .progress-fill.active::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.12) 50%,
      transparent 100%
    );
    animation: shimmer 1.8s ease-in-out infinite;
  }

  @keyframes bar-pulse {
    0%, 100% { filter: brightness(1); }
    50% { filter: brightness(1.15); }
  }

  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }

  .progress-text-inner {
    font-size: 0.75rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: #000;
    position: relative;
    z-index: 1;
  }

  .progress-text-outer {
    position: absolute;
    left: 0.5rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.75rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  .progress-footer {
    margin-top: 0.375rem;
    text-align: right;
  }

  .count {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }
</style>
