<script lang="ts">
  let { game }: { game: string } = $props();

  const colorMap: Record<string, { bg: string; fg: string }> = {
    skyrimse:          { bg: 'rgba(96, 165, 250, 0.15)',  fg: '#60a5fa' },
    skyrim:            { bg: 'rgba(96, 165, 250, 0.15)',  fg: '#60a5fa' },
    skyrimspecialedition: { bg: 'rgba(96, 165, 250, 0.15)', fg: '#60a5fa' },
    fallout4:          { bg: 'rgba(74, 222, 128, 0.15)',  fg: '#4ade80' },
    fallout4vr:        { bg: 'rgba(74, 222, 128, 0.15)',  fg: '#4ade80' },
    falloutnewvegas:   { bg: 'rgba(74, 222, 128, 0.15)',  fg: '#4ade80' },
    baldursgate3:      { bg: 'rgba(251, 191, 36, 0.15)',  fg: '#fbbf24' },
    enderal:           { bg: 'rgba(192, 132, 252, 0.15)', fg: '#c084fc' },
    enderalse:         { bg: 'rgba(192, 132, 252, 0.15)', fg: '#c084fc' },
    oblivion:          { bg: 'rgba(248, 113, 113, 0.15)', fg: '#f87171' },
    morrowind:         { bg: 'rgba(45, 212, 191, 0.15)',  fg: '#2dd4bf' },
    starfield:         { bg: 'rgba(165, 180, 252, 0.15)', fg: '#a5b4fc' },
    cyberpunk2077:     { bg: 'rgba(251, 146, 60, 0.15)',  fg: '#fb923c' },
  };

  const fallback = { bg: 'rgba(136, 136, 160, 0.15)', fg: '#8888a0' };

  let colors = $derived(colorMap[game.toLowerCase().replace(/[\s\-:]/g, '')] ?? fallback);

  let label = $derived.by(() => {
    const map: Record<string, string> = {
      skyrimse: 'Skyrim SE',
      skyrimspecialedition: 'Skyrim SE',
      skyrim: 'Skyrim',
      fallout4: 'Fallout 4',
      fallout4vr: 'Fallout 4 VR',
      falloutnewvegas: 'Fallout NV',
      baldursgate3: 'BG3',
      enderal: 'Enderal',
      enderalse: 'Enderal SE',
      oblivion: 'Oblivion',
      morrowind: 'Morrowind',
      starfield: 'Starfield',
      cyberpunk2077: 'Cyberpunk',
    };
    const key = game.toLowerCase().replace(/[\s\-:]/g, '');
    return map[key] ?? game;
  });
</script>

<span
  class="game-badge"
  style:background={colors.bg}
  style:color={colors.fg}
>
  {label}
</span>

<style>
  .game-badge {
    display: inline-block;
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
  }
</style>
