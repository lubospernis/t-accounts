"""
renderer.py — Beautiful T-account display using Rich.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box
from ledger import Entity, Ledger

console = Console()


def render_entity(entity: Entity) -> Panel:
    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        expand=True,
        padding=(0, 1),
    )
    table.add_column("ASSETS", style="green", justify="left")
    table.add_column("LIABILITIES & EQUITY", style="red", justify="left")

    # Zip assets and liabilities side by side
    assets = entity.assets
    liabs = entity.liabilities
    max_rows = max(len(assets), len(liabs), 1)

    for i in range(max_rows):
        a_cell = ""
        l_cell = ""
        if i < len(assets):
            a = assets[i]
            a_cell = f"{a['label']}  [bold]{a['amount']:,.0f}[/bold]"
            if a.get("counterparty"):
                a_cell += f" [dim]← {a['counterparty']}[/dim]"
        if i < len(liabs):
            l = liabs[i]
            l_cell = f"{l['label']}  [bold]{l['amount']:,.0f}[/bold]"
            if l.get("counterparty"):
                l_cell += f" [dim]→ {l['counterparty']}[/dim]"
        table.add_row(a_cell, l_cell)

    # Totals row
    table.add_row("─" * 20, "─" * 20)
    balanced = entity.is_balanced()
    bal_icon = "✓" if balanced else "✗ UNBALANCED"
    bal_style = "green" if balanced else "bold red"
    table.add_row(
        f"[bold]TOTAL  {entity.total_assets():,.0f}[/bold]",
        f"[bold]TOTAL  {entity.total_liabilities():,.0f}[/bold]  [{bal_style}]{bal_icon}[/{bal_style}]",
    )

    return Panel(table, title=f"[bold yellow]{entity.name}[/bold yellow]", border_style="yellow")


def render_all(ledger: Ledger):
    if not ledger.entities:
        console.print("[dim]No entities yet. Use 'create <name> <reserves>' to start.[/dim]")
        return
    panels = [render_entity(e) for e in ledger.entities.values()]
    console.print(Columns(panels, equal=True, expand=True))


def render_graph(ledger: Ledger):
    """Render payment flow graph as ASCII in terminal."""
    if not ledger.transactions:
        console.print("[dim]No transactions recorded yet.[/dim]")
        return

    # Build adjacency: sender → {receiver: [(instrument, amount)]}
    graph: dict[str, dict] = {}
    for tx in ledger.transactions:
        s, r = tx["sender"], tx["receiver"]
        if s not in graph:
            graph[s] = {}
        if r not in graph[s]:
            graph[s][r] = []
        graph[s][r].append((tx["instrument"], tx["amount"], tx["type"]))

    lines = []
    seen_nodes = set()

    for sender, targets in graph.items():
        for receiver, flows in targets.items():
            seen_nodes.add(sender)
            seen_nodes.add(receiver)
            for instrument, amount, tx_type in flows:
                arrow = f"[cyan]{sender}[/cyan] [dim]──[{instrument} {amount:,.0f}]──▶[/dim] [cyan]{receiver}[/cyan]"
                lines.append(arrow)

    # Also show entities with no transactions
    lonely = set(ledger.entities.keys()) - seen_nodes
    if lonely:
        lines.append("")
        for node in lonely:
            lines.append(f"[cyan]{node}[/cyan]  [dim](no transactions)[/dim]")

    panel_content = "\n".join(lines) if lines else "[dim]empty[/dim]"
    console.print(Panel(panel_content, title="[bold magenta]Payment Flow Graph[/bold magenta]", border_style="magenta"))
