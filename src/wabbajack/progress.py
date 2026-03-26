"""Rich progress display for downloads and installation."""
import logging

log = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def print_modlist_info(summary):
    """Print modlist info with rich formatting if available."""
    if not HAS_RICH:
        log.info(f"Name:       {summary['name']}")
        log.info(f"Version:    {summary['version']}")
        log.info(f"Author:     {summary['author']}")
        log.info(f"Game:       {summary['game']}")
        log.info(f"Archives:   {summary['archives']}")
        log.info(f"Directives: {summary['directives']}")
        return

    console = Console()
    table = Table(title=f"{summary['name']} v{summary['version']}", show_header=False, border_style="blue")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Author", summary['author'])
    table.add_row("Game", summary['game'])
    table.add_row("NSFW", str(summary['nsfw']))
    table.add_row("Archives", str(summary['archives']))
    table.add_row("Directives", str(summary['directives']))
    console.print(table)

    if summary.get('directive_types'):
        dt = Table(title="Directive Types", show_header=True, border_style="dim")
        dt.add_column("Type", style="cyan")
        dt.add_column("Count", style="white", justify="right")
        for t, c in sorted(summary['directive_types'].items(), key=lambda x: -x[1]):
            dt.add_row(t, str(c))
        console.print(dt)

    if summary.get('archive_types'):
        at = Table(title="Archive Sources", show_header=True, border_style="dim")
        at.add_column("Source", style="cyan")
        at.add_column("Count", style="white", justify="right")
        for t, c in sorted(summary['archive_types'].items(), key=lambda x: -x[1]):
            at.add_row(t, str(c))
        console.print(at)


def print_install_complete(stats, hash_mismatches=None):
    """Print installation completion summary."""
    if not HAS_RICH:
        return

    console = Console()
    pct = stats['ok'] / max(1, stats['ok'] + stats['fail']) * 100
    color = "green" if pct > 95 else "yellow" if pct > 80 else "red"
    panel = Panel(
        f"[bold]Files placed:[/bold]    {stats['ok']}\n"
        f"[bold]Failed:[/bold]          {stats['fail']}\n"
        f"[bold]BSAs needed:[/bold]     {stats.get('bsa', 0)}\n"
        f"[bold]Extracted:[/bold]       {stats.get('archives_extracted', 0)}\n"
        f"[bold]Success rate:[/bold]    [{color}]{pct:.1f}%[/{color}]"
        + (f"\n[bold yellow]Hash mismatches:[/bold yellow] {len(hash_mismatches)}" if hash_mismatches else ""),
        title="Installation Complete",
        border_style=color,
    )
    console.print(panel)
