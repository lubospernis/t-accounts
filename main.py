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
    currency: str = typer.Option("USD", "--currency", help="Currency: USD (default) or EUR"),
):
    """Create an entity with initial reserves. Defaults to USD."""
    if currency.upper() not in ("USD", "EUR"):
        console.print(f"[red]Error:[/red] Currency must be USD or EUR.")
        raise typer.Exit(1)
    try:
        e = ledger.create(entity, reserves, currency=currency.upper())
        console.print(f"[green]✓[/green] Created [bold yellow]{entity}[/bold yellow] with [bold]{reserves:,.0f}[/bold] reserves")
        console.print(render_entity(e, ledger=ledger))
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)


# ── NEW ──────────────────────────────────────────────────────────────────────

@app.command()
def new(
    entity: str = typer.Argument(..., help="Entity name, e.g. 'my-bank'"),
    currency: Optional[str] = typer.Option(None, "--currency", help="Currency: USD or EUR"),
):
    """
    Create a blank balance sheet with no initial entries.

    Optionally set a display currency — amounts will be shown with the
    corresponding symbol and scale (e.g. $1M, €1.5B). Currency can only
    be set at creation time via this command.

    Examples:
      new my-bank
      new fed --currency USD
      new ecb --currency EUR
    """
    try:
        from ledger import Entity
        if entity in ledger.entities:
            raise ValueError(f"Entity '{entity}' already exists.")
        if currency and currency.upper() not in ("USD", "EUR"):
            raise ValueError(f"Currency must be USD or EUR, got '{currency}'.")
        ent = Entity(name=entity)
        ent.currency = currency.upper() if currency else "USD"
        ledger.entities[entity] = ent
        ledger.save()
        cur_note = f" [dim]({currency.upper()})[/dim]" if currency else ""
        console.print(f"[green]✓[/green] Created blank balance sheet: [bold yellow]{entity}[/bold yellow]{cur_note}")
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
        console.print(render_entity(e, ledger=ledger))

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
    Issue a token. Updates both sides:

      Issuer:   token liability ↑  (owes the token to the receiver)
      Receiver: token asset ↑      (holds a claim on the issuer)

    Examples:
      issue stablecoin-issuer tokenusd 10 --to alice
      issue central-bank reserves 100 --to commercial-bank
    """
    try:
        issuer = ledger.get(entity)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    if not to:
        console.print("[red]Error:[/red] --to <receiver> is required. Use 'issue <entity> <token> <amount> --to <receiver>'.")
        raise typer.Exit(1)

    try:
        receiver = ledger.get(to)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Issuer: token is a liability (owes the token to the receiver)
    issuer.add_liability(token, amount, counterparty=to)

    # Receiver: token is an asset (holds a claim on the issuer)
    receiver.add_asset(token, amount, counterparty=entity)

    ledger.save()  # issue is not a payment — no graph entry

    # Build confirmation: "issued 10 tokenusd ($10)" where fiat value is shown if known
    fv = ledger.token_fiat_value(token, amount, issuer.currency)
    sym = "$" if issuer.currency == "USD" else "€"
    fv_note = f" [dim]({sym}{fv:,.0f})[/dim]" if fv is not None else ""
    console.print(
        f"[green]✓[/green] [bold yellow]{entity}[/bold yellow] issued "
        f"[bold]{amount:,.0f}[/bold] [cyan]{token}[/cyan]{fv_note} → [bold yellow]{to}[/bold yellow]"
    )
    console.print(render_entity(issuer, ledger=ledger))
    console.print(render_entity(receiver, ledger=ledger))



# ── REDEEM ───────────────────────────────────────────────────────────────────

@app.command()
def redeem(
    redeemer: str = typer.Argument(..., help="Entity redeeming the token"),
    token: str = typer.Argument(..., help="Token to redeem, e.g. 'tokenusd'"),
    amount: float = typer.Argument(..., help="Amount to redeem"),
    to: str = typer.Option(..., "--to", help="Issuer entity (who originally issued the token)"),
):
    """
    Redeem tokens against the issuer. Trad world only.

    Two things happen simultaneously:

      Burn:
        Redeemer:  token asset ↓       (tokens destroyed)
        Issuer:    token liability ↓   (supply shrinks)

      Cash settlement:
        Issuer:    cash asset ↓        (pays out reserves)
        Redeemer:  cash asset ↑        (receives cash)

    Both sides of the issuer's balance sheet shrink equally.
    The redeemer does a pure asset swap: token out, cash in. Equity unchanged.

    Example:
      redeem bob tokenusd 5 --to circle
    """
    if ledger.world == "crypto":
        console.print("[red]Error:[/red] redeem is a trad world operation only.")
        raise typer.Exit(1)

    try:
        red = ledger.get(redeemer)
        issuer = ledger.get(to)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    # Validate redeemer holds enough of the token
    token_entry = next((e for e in red.assets if e["label"] == token), None)
    if token_entry is None:
        console.print(f"[red]Error:[/red] [bold yellow]{redeemer}[/bold yellow] holds no [cyan]{token}[/cyan].")
        raise typer.Exit(1)
    if token_entry["amount"] < amount:
        console.print(
            f"[red]Error:[/red] [bold yellow]{redeemer}[/bold yellow] only holds "
            f"[bold]{token_entry['amount']:,.0f}[/bold] [cyan]{token}[/cyan], "
            f"cannot redeem [bold]{amount:,.0f}[/bold]."
        )
        raise typer.Exit(1)

    # Validate issuer has enough token liability outstanding
    liab_entry = next((e for e in issuer.liabilities if e["label"] == token), None)
    if liab_entry is None or liab_entry["amount"] < amount:
        outstanding = liab_entry["amount"] if liab_entry else 0
        console.print(
            f"[red]Error:[/red] [bold yellow]{to}[/bold yellow] only has "
            f"[bold]{outstanding:,.0f}[/bold] [cyan]{token}[/cyan] outstanding, "
            f"cannot redeem [bold]{amount:,.0f}[/bold]."
        )
        raise typer.Exit(1)

    # Validate issuer can pay — either cash or a shared deposit account
    issuer_cash = next((e for e in issuer.assets if e["label"] == "cash"), None)
    issuer_deposits = {
        e["label"].removeprefix("deposit@"): e
        for e in issuer.assets if e["label"].startswith("deposit@")
    }
    redeemer_deposits = {
        e["label"].removeprefix("deposit@"): e
        for e in red.assets if e["label"].startswith("deposit@")
    }
    shared_banks = set(issuer_deposits) & set(redeemer_deposits)
    can_intrabank = any(issuer_deposits[b]["amount"] >= amount for b in shared_banks)
    can_cash = issuer_cash is not None and issuer_cash["amount"] >= amount

    if not can_intrabank and not can_cash:
        avail_cash = issuer_cash["amount"] if issuer_cash else 0
        console.print(
            f"[red]Error:[/red] [bold yellow]{to}[/bold yellow] cannot settle "
            f"[bold]{amount:,.0f}[/bold]: no shared deposit account with [bold yellow]{redeemer}[/bold yellow] "
            f"and only [bold]{avail_cash:,.0f}[/bold] cash available."
        )
        raise typer.Exit(1)

    # ── Burn ─────────────────────────────────────────────────────────────────
    # Redeemer: token asset shrinks
    token_entry["amount"] -= amount
    if token_entry["amount"] == 0:
        red.assets.remove(token_entry)

    # Issuer: token liability shrinks (supply burned)
    liab_entry["amount"] -= amount
    if liab_entry["amount"] == 0:
        issuer.liabilities.remove(liab_entry)

    # ── Settlement — intrabank or cash ────────────────────────────────────────
    try:
        path = ledger.settle(to, redeemer, amount, tx_type="redeem", is_payment=False)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    fv = ledger.token_fiat_value(token, amount, issuer.currency)
    sym = "$" if issuer.currency == "USD" else "€"
    fv_note = f" [dim]({sym}{fv:,.0f})[/dim]" if fv is not None else ""
    path_note = f" [dim](settled at shared bank)[/dim]" if path == "intrabank" else ""
    console.print(
        f"[green]✓[/green] [bold yellow]{redeemer}[/bold yellow] redeemed "
        f"[bold]{amount:,.0f}[/bold] [cyan]{token}[/cyan]{fv_note} → "
        f"[bold]{sym}{amount:,.0f}[/bold] from [bold yellow]{to}[/bold yellow]{path_note}"
    )
    console.print(render_entity(red, ledger=ledger))
    console.print(render_entity(issuer, ledger=ledger))


# ── PAY ──────────────────────────────────────────────────────────────────────

@app.command()
def pay(
    sender: str = typer.Argument(..., help="Sending entity"),
    receiver: str = typer.Argument(..., help="Receiving entity"),
    amount: float = typer.Argument(..., help="Amount to transfer"),
    token: Optional[str] = typer.Option(None, "--token", help="Token to use (crypto world; auto-detected if unambiguous)"),
):
    """
    Payment between two entities.

    TRAD WORLD — two cases:
      Intrabank: both hold deposits at the same bank → swap deposit balances, no cash, not in graph
      Cash: direct cash transfer → recorded in graph

    CRYPTO WORLD — token payment only:
      Sender must hold the token as an asset.
      Auto-detected if sender holds exactly one token type.
      Use --token <name> if ambiguous.
      Intrabank token settlement works the same as trad.

    Examples:
      pay alice bob 30
      pay alice bob 10 --token tokenusd
    """
    try:
        s = ledger.get(sender)
        r = ledger.get(receiver)
    except ValueError as ex:
        console.print(f"[red]Error:[/red] {ex}")
        raise typer.Exit(1)

    if ledger.world == "crypto":
        # ── Crypto world: direct P2P token transfer, always in graph ──────────
        if not token:
            sender_tokens = [e["label"] for e in s.assets]
            if len(sender_tokens) == 0:
                console.print(f"[red]Error:[/red] [bold cyan]{sender}[/bold cyan] holds no tokens.")
                raise typer.Exit(1)
            if len(sender_tokens) > 1:
                console.print(
                    f"[red]Error:[/red] [bold cyan]{sender}[/bold cyan] holds multiple tokens "
                    f"({', '.join(sender_tokens)}). Use --token <n>."
                )
                raise typer.Exit(1)
            token = sender_tokens[0]

        try:
            ledger.transfer_token(sender, receiver, token, amount, tx_type="payment")
        except ValueError as ex:
            console.print(f"[red]Error:[/red] {ex}")
            raise typer.Exit(1)

        from ledger import token_emoji
        emoji = token_emoji(token)
        console.print(
            f"[green]✓[/green] [bold cyan]{sender}[/bold cyan] paid "
            f"[bold]{amount:,.0f}[/bold] {emoji} [cyan]{token}[/cyan] → [bold cyan]{receiver}[/bold cyan]"
        )
        console.print(render_entity(ledger.get(sender)))
        console.print(render_entity(ledger.get(receiver)))

    else:
        # ── Trad world: intrabank or cash via settle() ────────────────────────
        try:
            path = ledger.settle(sender, receiver, amount, tx_type="payment")
        except ValueError as ex:
            console.print(f"[red]Error:[/red] {ex}")
            raise typer.Exit(1)

        if path == "intrabank":
            console.print(
                f"[green]✓[/green] [bold yellow]{sender}[/bold yellow] paid "
                f"[bold]{amount:,.0f}[/bold] → [bold yellow]{receiver}[/bold yellow] "
                f"[dim](settled intrabank, no cash moved)[/dim]"
            )
        else:
            console.print(
                f"[green]✓[/green] [bold yellow]{sender}[/bold yellow] paid "
                f"[bold]{amount:,.0f}[/bold] cash → [bold yellow]{receiver}[/bold yellow]"
            )
        console.print(render_entity(ledger.get(sender), ledger=ledger))
        console.print(render_entity(ledger.get(receiver), ledger=ledger))


# ── DEPOSIT ──────────────────────────────────────────────────────────────────

@app.command()
def deposit(
    bank: str = typer.Argument(..., help="The bank receiving the deposit"),
    amount: float = typer.Argument(0.0, help="Amount of cash to deposit (omit or 0 = open empty account)"),
    from_: Optional[str] = typer.Option(None, "--from", help="Depositor entity"),
):
    """
    Deposit cash into a bank, or open an empty deposit account.

    With amount > 0 (cash deposit):
      Depositor: cash down, deposit@bank up  (equity unchanged)
      Bank:      cash up, deposit-<n> up     (equity unchanged)
      Recorded in payment graph.

    With amount = 0 (open account):
      Creates the deposit@bank / deposit-<n> relationship with zero balance.
      No cash moves, not in graph. Useful to set up an account before
      receiving intrabank payments.

    Examples:
      deposit bank 10 --from alice     (cash deposit)
      deposit bank --from alice        (open empty account)
      deposit bank 0 --from alice      (same as above)
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

    # Check if account already exists
    existing_claim = next((e for e in depositor.assets if e["label"] == f"deposit@{bank}"), None)
    if existing_claim is not None and amount == 0:
        console.print(
            f"[yellow]Note:[/yellow] [bold yellow]{from_}[/bold yellow] already has "
            f"a deposit account at [bold yellow]{bank}[/bold yellow]."
        )
        raise typer.Exit(0)

    if amount > 0:
        # Cash moves — validated and recorded in graph
        try:
            ledger.transfer_cash(from_, bank, amount, tx_type="deposit", record=False)
        except ValueError as ex:
            console.print(f"[red]Error:[/red] {ex}")
            raise typer.Exit(1)

    # Create or update deposit claim on depositor side
    if existing_claim:
        existing_claim["amount"] += amount
    else:
        depositor.assets.append({"label": f"deposit@{bank}", "amount": amount, "counterparty": bank})

    # Create or update deposit liability on bank side
    dep_label = f"deposit-{from_}"
    dep_liab = next((e for e in b.liabilities if e["label"] == dep_label), None)
    if dep_liab:
        dep_liab["amount"] += amount
    else:
        b.liabilities.append({"label": dep_label, "amount": amount, "counterparty": from_})

    ledger.save()

    if amount > 0:
        console.print(
            f"[green]✓[/green] [bold yellow]{from_}[/bold yellow] deposited "
            f"[bold]{depositor.fmt(amount)}[/bold] into [bold yellow]{bank}[/bold yellow]"
        )
    else:
        console.print(
            f"[green]✓[/green] Opened empty deposit account for [bold yellow]{from_}[/bold yellow] "
            f"at [bold yellow]{bank}[/bold yellow]"
        )
    console.print(render_entity(depositor, ledger=ledger))
    console.print(render_entity(b, ledger=ledger))


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
        ledger.transfer_cash(bank, to, amount, tx_type="withdrawal", record=False)
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
    console.print(render_entity(withdrawer, ledger=ledger))
    console.print(render_entity(b, ledger=ledger))


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

    console.print(render_entity(borrower, ledger=ledger))
    console.print(render_entity(lender, ledger=ledger))


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


# ── PRICE ────────────────────────────────────────────────────────────────────

@app.command()
def price(
    token: str = typer.Argument(..., help="Token name, e.g. 'tokeneth'"),
    amount: float = typer.Argument(..., help="Fiat value per token"),
    currency: str = typer.Option("USD", "--currency", help="Currency of the price (USD or EUR)"),
):
    """
    Set the fiat price of a token for trad world display.

    Stablecoins (tokenusd, tokeneur) are pegged automatically and don't
    need this command. Use it for other tokens like tokeneth or tokenbtc.

    Examples:
      price tokeneth 2000          (1 tokeneth = $2000)
      price tokenbtc 50000         (1 tokenbtc = $50,000)
      price tokeneth 1850 --currency EUR
    """
    if currency.upper() not in ("USD", "EUR"):
        console.print(f"[red]Error:[/red] Currency must be USD or EUR.")
        raise typer.Exit(1)
    ledger.set_token_price(token, amount, currency.upper())
    sym = "$" if currency.upper() == "USD" else "€"
    console.print(
        f"[green]✓[/green] [cyan]{token}[/cyan] = [bold]{sym}{amount:,.0f}[/bold] per token"
    )


# ── WORLDSWITCH ───────────────────────────────────────────────────────────────

@app.command()
def worldswitch():
    """
    Toggle between trad and crypto world.

    Trad world:   cash-based, full T-accounts, yellow borders
    Crypto world: token-only, no cash concept, cyan borders + emojis

    Crypto balance sheets start empty — only tokens issued via 'issue'
    appear. All entities exist in both worlds. Switching immediately
    shows all balance sheets in the new world.

    Example:
      worldswitch   (trad → crypto)
      worldswitch   (crypto → trad)
    """
    new_world = ledger.switch_world()
    label = "⛓️  [bold cyan]CRYPTO WORLD[/bold cyan]" if new_world == "crypto" else "🏦 [bold yellow]TRAD WORLD[/bold yellow]"
    console.print(f"\n[bold]Switched to {label}[/bold]\n")
    render_all(ledger)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()