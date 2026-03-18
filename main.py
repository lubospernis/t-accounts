"""
main.py — taccounts CLI
A T-account simulator for teaching monetary economics.

Commands:
  new <entity>                                        — Create a blank balance sheet
  entry <entity> asset|liability <label> <amount>     — Add any asset or liability freely
  create <entity> <reserves>                          — Create entity with initial reserves
  issue <entity> <token> <amount>                     — Issue a liability token (e.g. stablecoin)
  pay <sender> <receiver> <instrument> <amount>       — Record a payment between entities
  deposit <entity> <asset> <amount> [--from <cp>]     — Add asset deposit
  borrow <entity> <amount> [--from <lender>]          — Borrow cash
  balancesheets show                                  — Display all T-accounts
  balancesheets export                                — Export to Markdown
  graph show                                          — Show payment flow graph
  reset                                               — Clear all state
"""

import typer
from typing import Optional
from rich.console import Console
from ledger import Ledger
from renderer import render_all, render_graph, console
from markdown_export import export

app = typer.Typer(
    name="taccounts",
    help="📊 T-Account simulator for teaching monetary economics",
    no_args_is_help=True,
)
balancesheets_app = typer.Typer(help="Balance sheet commands")
graph_app = typer.Typer(help="Payment graph commands")
app.add_typer(balancesheets_app, name="balancesheets")
app.add_typer(graph_app, name="graph")

ledger = Ledger()


# ── CREATE ──────────────────────────────────────────────────────────────────

@app.command()
def create(
    entity: str = typer.Argument(..., help="Entity name, e.g. 'stablecoin-issuer'"),
    reserves: float = typer.Argument(..., help="Initial cash/reserves"),
):
    """Create an entity with initial reserves (cash asset = equity liability)."""
    try:
        e = ledger.create(entity, reserves)
        console.print(f"[green]✓[/green] Created [bold yellow]{entity}[/bold yellow] with [bold]{reserves:,.0f}[/bold] reserves")
        from renderer import render_entity
        console.print(render_entity(e))
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)


# ── NEW (blank balance sheet) ────────────────────────────────────────────────

@app.command()
def new(
    entity: str = typer.Argument(..., help="Entity name, e.g. 'my-bank'"),
):
    """Create a blank balance sheet with no initial entries."""
    try:
        from ledger import Entity
        if entity in ledger.entities:
            raise ValueError(f"Entity '{entity}' already exists.")
        ledger.entities[entity] = Entity(name=entity)
        ledger.save()
        console.print(f"[green]✓[/green] Created blank balance sheet: [bold yellow]{entity}[/bold yellow]")
        console.print(f"[dim]Use: entry {entity} asset|liability <label> <amount>[/dim]")
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)


# ── ENTRY (generic asset or liability) ───────────────────────────────────────

@app.command()
def entry(
    entity: str = typer.Argument(..., help="Entity name"),
    side: str = typer.Argument(..., help="'asset' or 'liability'"),
    label: str = typer.Argument(..., help="Label, e.g. 'cash', 'bonds', 'deposits'"),
    amount: float = typer.Argument(..., help="Amount"),
    counterparty: Optional[str] = typer.Option(None, "--cp", help="Counterparty name (optional)"),
    show: bool = typer.Option(True, "--show/--no-show", help="Print T-account after entry"),
    export_md: bool = typer.Option(False, "--export", help="Also export to balancesheets.md"),
):
    """
    Freely add an asset or liability to any balance sheet.

    Examples:\n
      entry my-bank asset cash 100\n
      entry my-bank liability deposits 80\n
      entry my-bank asset bonds 50 --cp ecb\n
      entry my-bank liability equity 20 --export
    """
    side = side.lower()
    if side not in ("asset", "liability"):
        console.print("[red]Error:[/red] side must be 'asset' or 'liability'")
        raise typer.Exit(1)

    # Auto-create entity if it doesn't exist yet
    if entity not in ledger.entities:
        from ledger import Entity
        ledger.entities[entity] = Entity(name=entity)
        console.print(f"[dim]Auto-created balance sheet '{entity}'[/dim]")

    e = ledger.entities[entity]

    if side == "asset":
        e.add_asset(label, amount, counterparty=counterparty)
        side_label = "[green]ASSET[/green]"
    else:
        e.add_liability(label, amount, counterparty=counterparty)
        side_label = "[red]LIABILITY[/red]"

    ledger.save()

    cp_note = f" [dim](cp: {counterparty})[/dim]" if counterparty else ""
    console.print(
        f"[green]✓[/green] {side_label} [cyan]{label}[/cyan] [bold]{amount:,.0f}[/bold]"
        f" added to [bold yellow]{entity}[/bold yellow]{cp_note}"
    )

    if show:
        from renderer import render_entity
        console.print(render_entity(e))

    if export_md:
        path = export(ledger, append=True)
        console.print(f"[green]✓[/green] Exported to [bold]{path}[/bold]")


# ── ISSUE ───────────────────────────────────────────────────────────────────

@app.command()
def issue(
    entity: str = typer.Argument(..., help="Issuing entity"),
    token: str = typer.Argument(..., help="Token/instrument name, e.g. 'tokenusd'"),
    amount: float = typer.Argument(..., help="Amount to issue"),
    to: Optional[str] = typer.Option(None, "--to", help="Receiver entity (optional)"),
):
    """
    Issue a token/liability. Adds a liability on the issuer.
    If --to is given, also adds the token as an asset to the receiver
    and removes cash from issuer (settlement).
    """
    try:
        issuer = ledger.get(entity)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Issuer: token issued → new liability
    issuer.add_liability(token, amount, counterparty=to)

    if to:
        # Issuer pays out cash (or we can model as direct token credit)
        # Model: issuer's cash backs the token; receiver gets the token as asset
        try:
            receiver = ledger.get(to)
        except ValueError as ex:
            console.print(f"[red]Error:[/red] {ex}")
            raise typer.Exit(1)
        receiver.add_asset(token, amount, counterparty=entity)
        ledger.record_transaction(entity, to, token, amount, "issue")
        console.print(f"[green]✓[/green] [bold yellow]{entity}[/bold yellow] issued [bold]{amount:,.0f}[/bold] [cyan]{token}[/cyan] → [bold yellow]{to}[/bold yellow]")
    else:
        console.print(f"[green]✓[/green] [bold yellow]{entity}[/bold yellow] issued [bold]{amount:,.0f}[/bold] [cyan]{token}[/cyan] (outstanding)")

    ledger.save()
    from renderer import render_entity
    console.print(render_entity(issuer))


# ── PAY ─────────────────────────────────────────────────────────────────────

@app.command()
def pay(
    sender: str = typer.Argument(..., help="Sending entity"),
    receiver: str = typer.Argument(..., help="Receiving entity"),
    amount: float = typer.Argument(..., help="Amount of cash to transfer"),
):
    """
    Cash payment between two entities. Both must have a cash asset entry;
    sender must have sufficient cash. Updates both balance sheets.

    Example: pay alice bob 30
    """
    try:
        s = ledger.get(sender)
        r = ledger.get(receiver)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Check sender has a cash asset
    sender_cash = next((e for e in s.assets if e["label"] == "cash"), None)
    if sender_cash is None:
        console.print(
            f"[red]Error:[/red] [bold yellow]{sender}[/bold yellow] has no cash asset. "
            f"Only cash payments are supported."
        )
        raise typer.Exit(1)

    # Check receiver has a cash asset (or at least exists — we'll create the entry)
    receiver_cash = next((e for e in r.assets if e["label"] == "cash"), None)
    if receiver_cash is None:
        console.print(
            f"[red]Error:[/red] [bold yellow]{receiver}[/bold yellow] has no cash asset. "
            f"Add one first with: entry {receiver} asset cash <amount>"
        )
        raise typer.Exit(1)

    # Check sender has sufficient cash
    if sender_cash["amount"] < amount:
        console.print(
            f"[red]Error:[/red] [bold yellow]{sender}[/bold yellow] has insufficient cash: "
            f"[bold]{sender_cash['amount']:,.0f}[/bold] available, "
            f"[bold]{amount:,.0f}[/bold] requested."
        )
        raise typer.Exit(1)

    # --- Execute the cash transfer ---
    # Sender: cash asset decreases
    sender_cash["amount"] -= amount
    if sender_cash["amount"] == 0:
        s.assets.remove(sender_cash)

    # Receiver: cash asset increases
    receiver_cash["amount"] += amount

    ledger.record_transaction(sender, receiver, "cash", amount, "payment")
    ledger.save()

    from renderer import render_entity
    console.print(
        f"[green]✓[/green] [bold yellow]{sender}[/bold yellow] paid "
        f"[bold]{amount:,.0f}[/bold] cash → [bold yellow]{receiver}[/bold yellow]"
    )
    console.print(render_entity(s))
    console.print(render_entity(r))


# ── DEPOSIT ─────────────────────────────────────────────────────────────────

@app.command()
def deposit(
    entity: str = typer.Argument(...),
    asset: str = typer.Argument(..., help="Asset label, e.g. 'cash', 'bonds'"),
    amount: float = typer.Argument(...),
    from_: Optional[str] = typer.Option(None, "--from", help="Counterparty"),
):
    """Add an asset to an entity (e.g. external deposit of cash)."""
    try:
        e = ledger.get(entity)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    e.add_asset(asset, amount, counterparty=from_)
    # Auto-balance: add matching liability (deposit liability to counterparty)
    if from_:
        e.add_liability(f"deposit-{from_}", amount, counterparty=from_)
        ledger.record_transaction(from_, entity, asset, amount, "deposit")

    ledger.save()
    console.print(f"[green]✓[/green] Deposited [bold]{amount:,.0f}[/bold] [cyan]{asset}[/cyan] into [bold yellow]{entity}[/bold yellow]")


# ── BORROW ──────────────────────────────────────────────────────────────────

@app.command()
def borrow(
    entity: str = typer.Argument(...),
    amount: float = typer.Argument(...),
    from_: Optional[str] = typer.Option(None, "--from", help="Lender entity"),
):
    """Entity borrows cash: gains cash asset, gains loan liability."""
    try:
        borrower = ledger.get(entity)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    borrower.add_asset("cash", amount, counterparty=from_)
    borrower.add_liability("loan-payable", amount, counterparty=from_)

    if from_:
        try:
            lender = ledger.get(from_)
            lender.remove_asset("cash", amount)
            lender.add_asset("loan-receivable", amount, counterparty=entity)
        except ValueError:
            pass  # lender not in ledger, that's OK
        ledger.record_transaction(from_, entity, "loan", amount, "borrow")

    ledger.save()
    console.print(f"[green]✓[/green] [bold yellow]{entity}[/bold yellow] borrowed [bold]{amount:,.0f}[/bold]" +
                  (f" from [bold yellow]{from_}[/bold yellow]" if from_ else ""))


# ── BALANCESHEETS ────────────────────────────────────────────────────────────

@balancesheets_app.command("show")
def balancesheets_show():
    """Display all T-accounts side by side."""
    render_all(ledger)


@balancesheets_app.command("export")
def balancesheets_export(
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite instead of append"),
):
    """Export current balance sheets to balancesheets.md (for git)."""
    path = export(ledger, append=not overwrite)
    console.print(f"[green]✓[/green] Exported to [bold]{path}[/bold]")


# ── GRAPH ────────────────────────────────────────────────────────────────────

@graph_app.command("show")
def graph_show():
    """Show payment flow graph between entities."""
    render_graph(ledger)


# ── RESET ────────────────────────────────────────────────────────────────────

@app.command()
def reset(
    confirm: bool = typer.Option(False, "--confirm", help="Actually reset"),
):
    """Clear all entities and transactions."""
    if not confirm:
        console.print("[yellow]Add --confirm to actually reset.[/yellow]")
        return
    ledger.reset()
    console.print("[red]✓ Reset complete.[/red]")


# ── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
