"""
renderer.py — T-account display using Rich.

Trad world:  yellow borders, green assets, red liabilities
Crypto world: cyan borders, blue assets, yellow liabilities, token emojis
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box
from ledger import Entity, Ledger, token_emoji

console = Console()

WORLD_STYLES = {
    "trad": {
        "border": "yellow",
        "title": "bold yellow",
        "asset_col": "green",
        "liab_col": "red",
        "equity_col": "magenta",
        "header": "bold cyan",
    },
    "crypto": {
        "border": "cyan",
        "title": "bold cyan",
        "asset_col": "blue",
        "liab_col": "yellow",
        "equity_col": "magenta",
        "header": "bold blue",
    },
}


def world_banner(world: str) -> str:
    if world == "crypto":
        return "⛓️  [bold cyan]CRYPTO WORLD[/bold cyan] — token balances only  ⛓️"
    return "🏦 [bold yellow]TRAD WORLD[/bold yellow] — cash & deposits"


# Labels that are fiat-denominated in trad world (use currency symbol)
_FIAT_LABELS = {"cash"}


def _is_token_entry(label: str) -> bool:
    """True if this label is a token (not cash/deposit/loan plumbing)."""
    if label in _FIAT_LABELS:
        return False
    if label.startswith("deposit@") or label.startswith("deposit-"):
        return False
    if label in ("loan-payable", "loan-receivable", "equity"):
        return False
    return True


def _fmt_entry(entity: Entity, entry: dict) -> str:
    """Format a single entry amount.
    - Trad world, fiat entries (cash, deposits): currency symbol + amount
    - Trad world, token entries: plain quantity (fiat value shown separately in parentheses)
    - Crypto world: token emoji + amount
    """
    label = entry["label"]
    amount = entry["amount"]
    if entity._world == "crypto":
        tok = label.replace("deposit@", "").replace("deposit-", "")
        return entity.fmt(amount, label=tok)
    else:
        if _is_token_entry(label):
            # Plain quantity — no currency symbol; fiat value added separately
            return f"{amount:,.0f}"
        return entity.fmt(amount)


def render_entity(entity: Entity, ledger=None) -> Panel:
    s = WORLD_STYLES[entity._world]
    f = entity.fmt

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style=s["header"],
        expand=True,
        padding=(0, 1),
    )
    table.add_column("ASSETS", style=s["asset_col"], justify="left")
    table.add_column("LIABILITIES & EQUITY", style=s["liab_col"], justify="left")

    assets = entity.assets
    liabs = entity.liabilities
    max_rows = max(len(assets), len(liabs), 1)

    for i in range(max_rows):
        a_cell = ""
        l_cell = ""
        if i < len(assets):
            a = assets[i]
            a_cell = f"{a['label']}  [bold]{_fmt_entry(entity, a)}[/bold]"
            if a.get("counterparty"):
                a_cell += f" [dim]← {a['counterparty']}[/dim]"
            # In trad world, show fiat value next to token quantities
            if entity._world == "trad" and ledger and a["label"] not in ("cash",) and not a["label"].startswith("deposit"):
                fv = ledger.token_fiat_value(a["label"], a["amount"], entity.currency)
                if fv is not None:
                    sym = "$" if entity.currency == "USD" else "€"
                    fv_str = f"{fv:,.0f}" if fv == int(fv) else f"{fv:,.2f}".rstrip("0").rstrip(".")
                    a_cell += f" [dim green]({sym}{fv_str})[/dim green]"
        if i < len(liabs):
            l = liabs[i]
            l_cell = f"{l['label']}  [bold]{_fmt_entry(entity, l)}[/bold]"
            if l.get("counterparty"):
                l_cell += f" [dim]→ {l['counterparty']}[/dim]"
            if entity._world == "trad" and ledger and not l["label"].startswith("deposit") and l["label"] not in ("loan-payable", "loan-receivable", "equity"):
                fv = ledger.token_fiat_value(l["label"], l["amount"], entity.currency)
                if fv is not None:
                    sym = "$" if entity.currency == "USD" else "€"
                    fv_str = f"{fv:,.0f}" if fv == int(fv) else f"{fv:,.2f}".rstrip("0").rstrip(".")
                    l_cell += f" [dim red]({sym}{fv_str})[/dim red]"
        table.add_row(a_cell, l_cell)

    table.add_row("─" * 20, "─" * 20)

    if entity._world == "crypto":
        # Per-token net position: held - owed, one row per token
        # Collect held (assets) and owed (liabilities) per token
        held: dict[str, float] = {}
        owed: dict[str, float] = {}
        for e in entity.assets:
            held[e["label"]] = held.get(e["label"], 0) + e["amount"]
        for e in entity.liabilities:
            owed[e["label"]] = owed.get(e["label"], 0) + e["amount"]

        all_tokens = sorted(set(list(held.keys()) + list(owed.keys())))
        if all_tokens:
            for tok in all_tokens:
                emoji = token_emoji(tok)
                h = held.get(tok, 0)
                o = owed.get(tok, 0)
                net = h - o
                net_str = f"+{net:,.0f}" if net > 0 else f"{net:,.0f}"
                flag = "  [bold red]⚠ short[/bold red]" if net < 0 else "  [green]✓[/green]"
                table.add_row(
                    f"[bold]{tok} {emoji}[/bold]",
                    f"[bold {s['equity_col']}]net {net_str}[/bold {s['equity_col']}]{flag}",
                )
        else:
            table.add_row("[dim]empty[/dim]", "")
    else:
        # Trad world: equity and totals, FX-adjusted if ledger is available.
        # For entities holding foreign-currency tokens, use the converted fiat
        # value rather than the raw quantity so equity and totals are meaningful.
        if ledger:
            def _fiat_sum(entries: list) -> float:
                total = 0.0
                for e in entries:
                    label = e["label"]
                    amount = e["amount"]
                    fv = ledger.token_fiat_value(label, amount, entity.currency)
                    if fv is not None:
                        total += fv  # use converted value
                    else:
                        total += amount  # cash, deposits — already in entity currency
                return total

            fiat_assets = _fiat_sum(entity.assets_trad)
            fiat_liabs  = _fiat_sum(entity.liabilities_trad)
            fiat_equity = fiat_assets - fiat_liabs
            eq_fmt = f(fiat_equity, signed=True)
            total_a = fiat_assets
            total_l = fiat_assets  # always balanced by construction
        else:
            eq = entity.equity()
            eq_fmt = f(eq, signed=True)
            total_a = entity.total_assets()
            total_l = entity.total_liabilities_and_equity()

        table.add_row(
            "",
            f"[bold {s['equity_col']}]equity  {eq_fmt}[/bold {s['equity_col']}]  "
            f"[dim {s['equity_col']}](= A − L)[/dim {s['equity_col']}]"
        )
        table.add_row(
            f"[bold]TOTAL  {f(total_a)}[/bold]",
            f"[bold]TOTAL  {f(total_l)}[/bold]  [green]✓[/green]",
        )

    # Hide currency denomination in crypto world — it's irrelevant there
    cur_label = f" [dim]{entity.currency}[/dim]" if (entity.currency and entity._world == "trad") else ""
    if entity._world == "crypto" and entity.address:
        world_tag = f" [dim cyan]⛓ {entity.address}[/dim cyan]"
    elif entity._world == "crypto":
        world_tag = " [dim cyan]⛓[/dim cyan]"
    else:
        world_tag = ""
    title = f"[{s['title']}]{entity.name}[/{s['title']}]{cur_label}{world_tag}"
    return Panel(table, title=title, border_style=s["border"])


def _has_tokens(entity) -> bool:
    """True if entity holds any token assets (non-cash, non-deposit@ entries)."""
    return any(
        not e["label"].startswith("deposit@") and e["label"] != "cash"
        for e in entity.assets
    )


def _visible_in_crypto(entity) -> bool:
    """An entity is visible in crypto world if it has a wallet address."""
    return entity.has_address


def render_all(ledger: Ledger):
    if not ledger.entities:
        console.print("[dim]No entities yet.[/dim]")
        return
    console.print(world_banner(ledger.world))
    if ledger.world == "crypto":
        # Only show entities with a wallet address
        visible = [e for e in ledger.entities.values() if _visible_in_crypto(e)]
        if not visible:
            console.print("[dim cyan]No entities with a crypto address yet. Use --address when creating entities.[/dim cyan]")
            return
    else:
        visible = list(ledger.entities.values())
    panels = [render_entity(e, ledger=ledger) for e in visible]
    console.print(Columns(panels, equal=True, expand=True))


def render_graph(ledger: Ledger):
    if not ledger.transactions:
        console.print("[dim]No transactions recorded yet.[/dim]")
        return

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

    if ledger.world == "crypto":
        # Crypto: labelled P2P token arrows, only token holders as nodes
        token_holders = {
            name for name, e in ledger.entities.items() if _visible_in_crypto(e)
        }
        for sender, targets in graph.items():
            for receiver, flows in targets.items():
                if sender not in token_holders and receiver not in token_holders:
                    continue
                seen_nodes.add(sender)
                seen_nodes.add(receiver)
                for instrument, amount, tx_type in flows:
                    emoji = token_emoji(instrument)
                    lines.append(
                        f"[cyan]{sender}[/cyan] "
                        f"[dim]──[/dim][bold cyan]{instrument} {emoji} {amount:,.0f}[/bold cyan][dim]──▶[/dim] "
                        f"[cyan]{receiver}[/cyan]"
                    )
        lonely = token_holders - seen_nodes
        if lonely:
            lines.append("")
            for node in sorted(lonely):
                lines.append(f"[cyan]{node}[/cyan]  [dim](no transactions)[/dim]")
    else:
        # Trad: unlabelled cash arrows
        for sender, targets in graph.items():
            for receiver, flows in targets.items():
                seen_nodes.add(sender)
                seen_nodes.add(receiver)
                for instrument, amount, tx_type in flows:
                    lines.append(
                        f"[cyan]{sender}[/cyan] [dim]──[{instrument} {amount:,.0f}]──▶[/dim] [cyan]{receiver}[/cyan]"
                    )
        lonely = set(ledger.entities.keys()) - seen_nodes
        if lonely:
            lines.append("")
            for node in sorted(lonely):
                lines.append(f"[cyan]{node}[/cyan]  [dim](no transactions)[/dim]")

    world_str = "⛓️  Crypto" if ledger.world == "crypto" else "🏦 Trad"
    border = "cyan" if ledger.world == "crypto" else "magenta"
    panel_content = "\n".join(lines) if lines else "[dim]empty[/dim]"
    console.print(Panel(
        panel_content,
        title=f"[bold {border}]{world_str} Payment Flow Graph[/bold {border}]",
        border_style=border,
    ))