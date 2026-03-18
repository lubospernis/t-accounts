"""
main.py — taccounts CLI
A T-account simulator for teaching monetary economics.

All cash movements go through ledger.transfer_cash(), which validates,
updates both balance sheets, and records the transaction in the graph.

Commands:
  new <entity>                                        — Create a blank balance sheet
  entry <entity> asset|liability <label> <amount>     — Add any asset or liability freely
  create <entity> <reserves>                          — Create entity with initial reserves
  issue <entity> <token> <amount>                     — Issue a liability token (e.g. stablecoin)
  pay <sender> <receiver> <amount>                    — Cash payment (updates graph)
  deposit <bank> <amount> --from <depositor>          — Deposit cash into a bank
  withdraw <bank> <amount> --to <withdrawer>          — Withdraw cash from a bank
  borrow <entity> <amount> --from <lender>            — Borrow (bank: deposit created; direct: cash moves)
  balancesheets show                                  — Display all T-accounts
  balancesheets export                                — Export to Markdown
  graph show                                          — Show payment flow graph
  reset                                               — Clear all state
"""

import typer
from typing import Optional
from ledger import Ledger
from renderer import render_all, render_graph, render_entity, console
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


# ── CREATE ───────────────────────────────────────────────────────────────────

@app.command()
def create(
    entity: str = typer.Argument(..., help="Entity name, e.g. 'stablecoin-issuer'"),
    reserves: float = typer.Argument(..., help="Initial cash/reserves"),
):
    """Create an entity with initial reserves (cash asset, equity is residual)."""
    try:
        e = ledger.create(entity, reserves)
        console.print(f"[green]✓[/green] Created [bold yellow]{entity}[/bold yellow] with [bold]{reserves:,.0f}[/bold] reserves")
        console.print(render_entity(e))
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)


# ── NEW ──────────────────────────────────────────────────────────────────────

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


# ── ENTRY ────────────────────────────────────────────────────────────────────

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
        console.print(render_entity(e))

    if export_md:
        path = export(ledger, append=True)
        console.print(f"[green]✓[/green] Exported to [bold]{path}[/bold]")


# ── ISSUE ────────────────────────────────────────────────────────────────────

@app.command()
def issue(
    entity: str = typer.Argument(..., help="Issuing entity"),
    token: str = typer.Argument(..., help="Token/instrument name, e.g. 'tokenusd'"),
    amount: float = typer.Argument(..., help="Amount to issue"),
    to: Optional[str] = typer.Option(None, "--to", help="Receiver entity (optional)"),
):
    """
    Issue a token/liability. Adds a liability on the issuer.
    If --to is given, the receiver gets the token as an asset.
    """
    try:
        issuer = ledger.get(entity)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    issuer.add_liability(token, amount, counterparty=to)

    if to:
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
    console.print(render_entity(issuer))


# ── PAY ──────────────────────────────────────────────────────────────────────

@app.command()
def pay(
    sender: str = typer.Argument(..., help="Sending entity"),
    receiver: str = typer.Argument(..., help="Receiving entity"),
    amount: float = typer.Argument(..., help="Amount to transfer"),
):
    """
    Payment between two entities. Two cases:

    INTRABANK — both hold deposits at the same institution:
      Sender:   deposit@bank ↓
      Receiver: deposit@bank ↑
      Bank:     deposit-sender ↓, deposit-receiver ↑
      (no cash moves, not recorded in payment graph)

    CASH — sender holds cash directly:
      Sender:   cash ↓
      Receiver: cash ↑
      (recorded in payment graph)

    Intrabank is detected automatically. If both share a deposit institution
    and sender has enough there, it settles intrabank. Otherwise falls back
    to a direct cash payment.

    Example: pay alice bob 30
    """
    try:
        s = ledger.get(sender)
        r = ledger.get(receiver)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Detect shared deposit institution
    sender_deposits = {
        e["label"].removeprefix("deposit@"): e
        for e in s.assets if e["label"].startswith("deposit@")
    }
    receiver_deposits = {
        e["label"].removeprefix("deposit@"): e
        for e in r.assets if e["label"].startswith("deposit@")
    }
    shared = set(sender_deposits) & set(receiver_deposits)

    # Pick the first shared bank where sender has enough
    intrabank = next(
        (bank for bank in shared if sender_deposits[bank]["amount"] >= amount),
        None
    )

    if intrabank:
        # ── Intrabank settlement — no cash moves, not in graph ────────────────
        try:
            bank_entity = ledger.get(intrabank)
        except ValueError as ex:
            console.print(f"[red]Error:[/red] {ex}")
            raise typer.Exit(1)

        # Sender: deposit claim shrinks
        sd = sender_deposits[intrabank]
        sd["amount"] -= amount
        if sd["amount"] == 0:
            s.assets.remove(sd)

        # Receiver: deposit claim grows
        receiver_deposits[intrabank]["amount"] += amount

        # Bank: rebalance deposit liabilities
        dep_sender = next((e for e in bank_entity.liabilities if e["label"] == f"deposit-{sender}"), None)
        dep_receiver = next((e for e in bank_entity.liabilities if e["label"] == f"deposit-{receiver}"), None)
        if dep_sender:
            dep_sender["amount"] -= amount
            if dep_sender["amount"] == 0:
                bank_entity.liabilities.remove(dep_sender)
        if dep_receiver:
            dep_receiver["amount"] += amount

        ledger.save()

        console.print(
            f"[green]✓[/green] [bold yellow]{sender}[/bold yellow] paid "
            f"[bold]{amount:,.0f}[/bold] → [bold yellow]{receiver}[/bold yellow] "
            f"[dim](settled at {intrabank}, no cash moved)[/dim]"
        )
        console.print(render_entity(s))
        console.print(render_entity(r))
        console.print(render_entity(bank_entity))

    else:
        # ── Cash payment — recorded in graph ─────────────────────────────────
        try:
            ledger.transfer_cash(sender, receiver, amount, tx_type="payment")
        except ValueError as ex:
            console.print(f"[red]Error:[/red] {ex}")
            raise typer.Exit(1)

        console.print(
            f"[green]✓[/green] [bold yellow]{sender}[/bold yellow] paid "
            f"[bold]{amount:,.0f}[/bold] cash → [bold yellow]{receiver}[/bold yellow]"
        )
        console.print(render_entity(ledger.get(sender)))
        console.print(render_entity(ledger.get(receiver)))


# ── DEPOSIT ──────────────────────────────────────────────────────────────────

@app.command()
def deposit(
    bank: str = typer.Argument(..., help="The bank receiving the deposit"),
    amount: float = typer.Argument(...),
    from_: Optional[str] = typer.Option(None, "--from", help="Depositor entity (must have enough cash)"),
):
    """
    Deposit cash from a depositor into a bank. Models both sides:

      Depositor: cash ↓, deposit@bank asset ↑  (equity unchanged)
      Bank:      cash ↑, deposit-<name> liability ↑  (equity unchanged)

    Cash movement goes through transfer_cash and is recorded in the graph.

    Example: deposit bank 10 --from alice
    """
    if not from_:
        console.print("[red]Error:[/red] --from <depositor> is required.")
        raise typer.Exit(1)

    try:
        b = ledger.get(bank)
        depositor = ledger.get(from_)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Cash moves from depositor to bank (validates + records in graph)
    try:
        ledger.transfer_cash(from_, bank, amount, tx_type="deposit")
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Swap depositor's cash entry for a deposit claim
    dep_cash = next((e for e in depositor.assets if e["label"] == "cash"), None)
    # transfer_cash already moved the cash to the bank — now adjust depositor's asset side:
    # cash was reduced by transfer_cash; add deposit claim in its place
    depositor.add_asset(f"deposit@{bank}", amount, counterparty=bank)

    # Bank already gained cash via transfer_cash; add the matching deposit liability
    b.add_liability(f"deposit-{from_}", amount, counterparty=from_)

    # But transfer_cash also added cash to the bank's asset — we need to undo the
    # intermediate step where transfer_cash gave the receiver raw cash, since
    # the bank's cash asset is already correct from transfer_cash.
    # The depositor's cash was already reduced. Now remove the plain cash the
    # transfer_cash added to the bank (it's correct) but we need to also
    # remove the cash that transfer_cash added to the depositor's side... 
    # Actually: transfer_cash(from_, bank) already:
    #   - reduced depositor cash by amount  ✓
    #   - increased bank cash by amount     ✓
    # We just need the extra accounting entries on top:
    #   - depositor gains deposit@bank      ✓ (done above)
    #   - bank gains deposit liability      ✓ (done above)
    # But transfer_cash already called record_transaction, so graph is updated. Good.

    ledger.save()

    console.print(
        f"[green]✓[/green] [bold yellow]{from_}[/bold yellow] deposited "
        f"[bold]{amount:,.0f}[/bold] cash into [bold yellow]{bank}[/bold yellow]"
    )
    console.print(render_entity(depositor))
    console.print(render_entity(b))


# ── WITHDRAW ─────────────────────────────────────────────────────────────────

@app.command()
def withdraw(
    bank: str = typer.Argument(..., help="The bank being withdrawn from"),
    amount: float = typer.Argument(...),
    to: str = typer.Option(..., "--to", help="Withdrawing entity"),
):
    """
    Withdraw cash from a bank. Exact mirror of deposit:

      Withdrawer: deposit@bank asset ↓, cash ↑  (equity unchanged)
      Bank:       cash ↓, deposit liability ↓    (equity unchanged)

    Cash movement goes through transfer_cash and is recorded in the graph.

    Example: withdraw bank 10 --to alice
    """
    try:
        b = ledger.get(bank)
        withdrawer = ledger.get(to)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Validate deposit claim
    claim_label = f"deposit@{bank}"
    claim = next((e for e in withdrawer.assets if e["label"] == claim_label), None)
    if claim is None:
        console.print(
            f"[red]Error:[/red] [bold yellow]{to}[/bold yellow] has no deposit claim at "
            f"[bold yellow]{bank}[/bold yellow]. Did they deposit first?"
        )
        raise typer.Exit(1)
    if claim["amount"] < amount:
        console.print(
            f"[red]Error:[/red] [bold yellow]{to}[/bold yellow] only has "
            f"[bold]{claim['amount']:,.0f}[/bold] deposited at [bold yellow]{bank}[/bold yellow], "
            f"cannot withdraw [bold]{amount:,.0f}[/bold]."
        )
        raise typer.Exit(1)

    # Cash moves from bank to withdrawer (validates bank cash + records in graph)
    try:
        ledger.transfer_cash(bank, to, amount, tx_type="withdrawal")
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Reduce the deposit claim on the withdrawer side
    claim["amount"] -= amount
    if claim["amount"] == 0:
        withdrawer.assets.remove(claim)

    # Reduce the deposit liability on the bank side
    dep_label = f"deposit-{to}"
    dep_liab = next((e for e in b.liabilities if e["label"] == dep_label), None)
    if dep_liab:
        dep_liab["amount"] -= amount
        if dep_liab["amount"] == 0:
            b.liabilities.remove(dep_liab)

    ledger.save()

    console.print(
        f"[green]✓[/green] [bold yellow]{to}[/bold yellow] withdrew "
        f"[bold]{amount:,.0f}[/bold] cash from [bold yellow]{bank}[/bold yellow]"
    )
    console.print(render_entity(withdrawer))
    console.print(render_entity(b))


# ── BORROW ───────────────────────────────────────────────────────────────────

@app.command()
def borrow(
    entity: str = typer.Argument(..., help="The borrowing entity"),
    amount: float = typer.Argument(...),
    from_: str = typer.Option(..., "--from", help="Lending entity"),
):
    """
    Create a loan between borrower and lender. No cash moves.

    Both sides get updated:
      Borrower: deposit@lender ↑, loan-payable ↑
      Lender:   loan-receivable ↑, deposit-<borrower> ↑

    This applies to all lenders — banks and non-banks alike. Cash is only
    released when the borrower calls 'withdraw'. This models the credit
    creation step separately from the cash settlement step.

    Examples:
      borrow startup 50 --from bank
      borrow startup 50 --from investor
      # then: withdraw bank 50 --to startup  (or: withdraw investor 50 --to startup)
    """
    try:
        borrower = ledger.get(entity)
        lender = ledger.get(from_)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Borrow always creates the credit relationship only — no cash moves.
    # The borrower gets a deposit@lender claim; the lender records a deposit liability.
    # Cash is only released when the borrower calls withdraw.
    borrower.add_asset(f"deposit@{from_}", amount, counterparty=from_)
    borrower.add_liability("loan-payable", amount, counterparty=from_)
    lender.add_asset("loan-receivable", amount, counterparty=entity)
    lender.add_liability(f"deposit-{entity}", amount, counterparty=entity)

    ledger.save()

    console.print(
        f"[green]✓[/green] [bold yellow]{from_}[/bold yellow] lent "
        f"[bold]{amount:,.0f}[/bold] to [bold yellow]{entity}[/bold yellow] "
        f"[dim]— deposit created, no cash moved. Use 'withdraw {from_} {amount} --to {entity}' to draw cash.[/dim]"
    )

    console.print(render_entity(borrower))
    console.print(render_entity(lender))


# ── BALANCESHEETS ─────────────────────────────────────────────────────────────

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


# ── GRAPH ─────────────────────────────────────────────────────────────────────

@graph_app.command("show")
def graph_show():
    """Show payment flow graph between entities."""
    render_graph(ledger)


# ── RESET ─────────────────────────────────────────────────────────────────────

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


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
