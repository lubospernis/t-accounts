# taccounts 📊

A command-line T-account simulator for teaching monetary economics — stablecoins, bank money, payment flows.

## Install

```bash
pip install typer rich
```

Run from the project directory:

```bash
python main.py --help
```

**PowerShell alias (optional):** add to your `$PROFILE` for convenience:

```powershell
function taccounts { python "C:\path\to\t-accounts\main.py" @args }
```

---

## All Commands

| Command | Description |
|---------|-------------|
| `new <entity>` | Create a blank balance sheet |
| `entry <entity> asset\|liability <label> <amount>` | Freely add any asset or liability |
| `create <entity> <reserves>` | Create entity with initial cash (equity is residual) |
| `issue <entity> <token> <amount> [--to <receiver>]` | Issue a token as a liability |
| `pay <sender> <receiver> <amount>` | Cash payment — updates both sheets and the graph |
| `deposit <bank> <amount> --from <depositor>` | Deposit cash into a bank |
| `withdraw <bank> <amount> --to <withdrawer>` | Withdraw cash from a bank |
| `borrow <entity> <amount> --from <lender>` | Borrow from a lender (bank or direct) |
| `balancesheets show` | Display all T-accounts |
| `balancesheets export` | Write to `balancesheets.md` |
| `graph show` | Show payment graph (cash flows only) |
| `reset --confirm` | Clear all state |

---

## Core Design Principles

**Equity is always computed, never stored.** Every balance sheet satisfies `Assets = Liabilities + Equity` by construction. Equity is the residual — it absorbs any change to assets or liabilities automatically. It is shown in magenta to distinguish it from explicit liabilities.

**The payment graph tracks cash flows only.** `graph show` shows only transactions where cash physically moved between entities. Bank lending (which creates a deposit without moving cash) is intentionally excluded. Every arrow in the graph corresponds to a real cash transfer.

**All cash movements go through one function.** `pay`, `deposit`, `withdraw`, and direct `borrow` all call the same internal `transfer_cash()` which validates balances, updates both balance sheets, and records the flow. There is no way to move cash without it appearing in the graph.

---

## Building Balance Sheets

**Generic — full control:**
```bash
python main.py new my-bank
python main.py entry my-bank asset cash 100
python main.py entry my-bank asset bonds 50 --cp ecb
python main.py entry my-bank liability deposits 80
```
Equity is computed automatically: `100 + 50 - 80 = 70`.

**Shortcut — cash only, equity follows:**
```bash
python main.py create my-bank 100
# cash asset = 100, equity = 100 (no liabilities yet)
```

`entry` options:
- `--cp <name>` — tag a counterparty (`← name` on assets, `→ name` on liabilities)
- `--no-show` — suppress T-account print (useful when scripting sequences)
- `--export` — write to `balancesheets.md` immediately after the entry

---

## Cash Payments

`pay` is the **cash leg only**. The sender must have a `cash` asset with sufficient funds. The receiver's cash increases. Both sheets update and the flow is recorded in the graph.

```bash
python main.py pay alice bob 30
```

What `pay` does *not* model is what was exchanged — a good, service, or token. That is recorded separately with `entry` or `issue`. Keeping the two sides explicit is the teaching point.

---

## Deposits and Withdrawals

A deposit swaps the depositor's cash for a claim on the bank. A withdrawal is the exact reverse.

```bash
python main.py deposit bank 10 --from alice
# Alice: cash ↓ 10, deposit@bank ↑ 10  (equity unchanged)
# Bank:  cash ↑ 10, deposit-alice ↑ 10  (equity unchanged)

python main.py withdraw bank 6 --to alice
# Alice: deposit@bank ↓ 6, cash ↑ 6  (equity unchanged)
# Bank:  cash ↓ 6, deposit-alice ↓ 6  (equity unchanged)
```

Both commands validate that the depositor/withdrawer has sufficient funds and the bank has sufficient cash. Both record a cash flow in the graph.

---

## Borrowing

`borrow` handles two cases automatically based on whether the lender has deposit liabilities:

**Bank lending — no cash moves, deposit is created:**
```bash
python main.py borrow startup 15 --from bank
# Startup: deposit@bank ↑ 15, loan-payable ↑ 15
# Bank:    loan-receivable ↑ 15, deposit-startup ↑ 15
# → Not in payment graph (no cash moved)
```

**Direct lending — cash changes hands:**
```bash
python main.py borrow startup 20 --from investor
# Startup:  cash ↑ 20, loan-payable ↑ 20
# Investor: cash ↓ 20, loan-receivable ↑ 20
# → Recorded in payment graph
```

The bank lending case illustrates money creation: the bank's balance sheet expands on both sides without any cash moving. The direct lending case is a pure cash transfer.

---

## Payment Graph

`graph show` displays only cash flows — every arrow is a real transfer of cash between entities.

```
alice ────▶ bank          (deposit)
bank ────▶ alice          (withdrawal)
investor ────▶ startup    (direct loan)
```

Bank lending does **not** appear here. If startup later uses its `deposit@bank` to make a payment, that cash flow will appear.

---

## T-Account Structure

```
╭──────────────── bank ──────────────────╮
│  ASSETS                LIABILITIES     │
│  ────────────────────────────────────  │
│  cash  10              deposit-alice 10│
│  loan-receivable 15    deposit-strt  15│
│                        equity  +0      │  ← magenta, always computed
│  ────────────────      ────────────    │
│  TOTAL  25             TOTAL  25  ✓    │
╰────────────────────────────────────────╯
```

Equity is always the last row on the right, shown in magenta, labelled `(= A − L)`. The sheet always balances — ✓ is always shown.

---

## Quickstart: Stablecoin Scenario

```bash
# Issuer starts with reserves
python main.py create stablecoin-issuer 10
git add . && git commit -m "step 1: issuer setup"

# Issue tokenusd as an outstanding liability
python main.py issue stablecoin-issuer tokenusd 10
git add . && git commit -m "step 2: token issued"

# Alice buys tokens by paying cash to the issuer
python main.py create alice 10
python main.py pay alice stablecoin-issuer 10
python main.py entry alice asset tokenusd 10 --cp stablecoin-issuer
python main.py balancesheets export
git add . && git commit -m "step 3: alice buys tokenusd"

python main.py graph show
# alice ────▶ stablecoin-issuer
```

---

## Quickstart: Bank Money Scenario

```bash
# Alice deposits cash at the bank
python main.py create alice 100
python main.py create bank 0
python main.py deposit bank 100 --from alice
git add . && git commit -m "step 1: alice deposits"

# Bank lends to startup (money creation — no cash moves, not in graph)
python main.py create startup 0
python main.py borrow startup 50 --from bank
git add . && git commit -m "step 2: bank lends to startup"

# Startup pays alice (cash now moves — appears in graph)
python main.py withdraw bank 50 --to startup   # startup gets cash first
python main.py pay startup alice 50
python main.py graph show
git add . && git commit -m "step 3: startup pays alice"
```

---

## State & Git Workflow

- `taccounts_state.json` — full ledger state, saved after every command
- `balancesheets.md` — appended each time you run `balancesheets export`

```bash
python main.py balancesheets export
git add taccounts_state.json balancesheets.md
git commit -m "scenario: <describe the step>"
```

---

## Extending

- Add a `repay` command as the inverse of `borrow` (reduces loan-payable, moves cash back)
- Add a `redeem` command as the inverse of `issue` (burns tokens, releases reserves)
- Add a `scenario` command to replay a sequence of steps from a `.txt` file
- Add a credit graph (`graph credits`) separate from the payment graph, showing loan relationships
- Use the `Textual` library to build an interactive TUI with live-updating T-accounts
