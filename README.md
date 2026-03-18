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
| `new <entity> [--currency USD\|EUR]` | Create a blank balance sheet, optionally with a currency |
| `entry <entity> asset\|liability <label> <amount>` | Freely add any asset or liability |
| `create <entity> <reserves>` | Create entity with initial cash (equity is residual) |
| `issue <entity> <token> <amount> [--to <receiver>]` | Issue a token as a liability |
| `pay <sender> <receiver> <amount>` | Payment — intrabank (no cash) or cash |
| `deposit <bank> <amount> --from <depositor>` | Deposit cash into a bank |
| `withdraw <bank> <amount> --to <withdrawer>` | Withdraw cash from a bank |
| `borrow <entity> <amount> --from <lender>` | Create a loan (no cash moves) |
| `balancesheets show` | Display all T-accounts |
| `balancesheets export` | Write to `balancesheets.md` |
| `graph show` | Show payment graph (cash flows only) |
| `reset --confirm` | Clear all state |

---

## Core Design Principles

**Equity is always computed, never stored.** Every balance sheet satisfies `Assets = Liabilities + Equity` by construction. Equity is the residual — shown in magenta, always labelled `(= A − L)`, always up to date.

**The payment graph tracks cash flows only.** `graph show` shows only transactions where cash physically moved. Intrabank settlements and bank lending are excluded. Every arrow = a real cash transfer.

**All cash movements go through one function.** `pay`, `deposit`, `withdraw` all call the same internal `transfer_cash()` which validates, updates both balance sheets, and records the flow.

**Currency is set once at creation.** Only `new --currency` can assign a display currency to an entity. It cannot be changed after creation.

---

## Building Balance Sheets

**Generic — full control, with optional currency:**
```bash
python main.py new fed --currency USD
python main.py entry fed asset cash 500
python main.py entry fed asset bonds 12500
python main.py entry fed asset reserves 3000000
python main.py entry fed liability deposits 1000000
```

**Shortcut — cash only, no currency:**
```bash
python main.py create my-bank 100
```

`entry` options:
- `--cp <name>` — tag a counterparty (`← name` on assets, `→ name` on liabilities)
- `--no-show` — suppress T-account print after the entry
- `--export` — write to `balancesheets.md` immediately

---

## Currency & Amount Formatting

Currency is optional and only set via `new --currency`. Supported: `USD` (`$`) and `EUR` (`€`).

Amounts scale automatically based on magnitude:

| Amount | USD display | No currency |
|--------|-------------|-------------|
| 500 | `$500` | `500` |
| 12,500 | `$12,500` | `12,500` |
| 3,000,000 | `$3M` | `3M` |
| 3,013,000 | `$3.01M` | `3.01M` |
| 2,500,000,000 | `$2.5B` | `2.5B` |

Equity always shows an explicit sign: `+$2.5B` or `-€100`.

---

## Cash Payments

`pay` detects the settlement path automatically:

**Intrabank** — both sender and receiver hold deposits at the same bank, and sender has enough there:
```bash
python main.py pay alice bob 20
# → settled at bank, no cash moves, not in graph
# Alice: deposit@bank ↓  Bob: deposit@bank ↑  Bank: rebalances liabilities
```

**Cash** — fallback when no shared institution is found:
```bash
python main.py pay alice bob 20
# → cash transfers directly, recorded in graph
```

The path is chosen automatically. No flag needed.

---

## Deposits and Withdrawals

```bash
python main.py deposit bank 10 --from alice
# Alice: cash ↓ 10, deposit@bank ↑ 10
# Bank:  cash ↑ 10, deposit-alice ↑ 10

python main.py withdraw bank 6 --to alice
# Alice: deposit@bank ↓ 6, cash ↑ 6
# Bank:  cash ↓ 6, deposit-alice ↓ 6
```

Both record a cash flow in the graph.

---

## Borrowing

`borrow` always creates the credit relationship only — no cash ever moves:

```bash
python main.py borrow startup 50 --from bank
# Startup: deposit@bank ↑ 50, loan-payable ↑ 50
# Bank:    loan-receivable ↑ 50, deposit-startup ↑ 50
# → not in payment graph
```

This works the same whether the lender is a bank or a non-bank (investor, central bank, etc.). To actually receive the cash, the borrower withdraws:

```bash
python main.py withdraw bank 50 --to startup
# Now cash moves → recorded in graph
```

---

## Payment Graph

`graph show` displays only cash flows:

```
alice ────▶ bank          (deposit)
bank ────▶ alice          (withdrawal)
investor ────▶ startup    (withdraw after borrow)
```

**Not shown:** intrabank settlements, bank lending (borrow without withdraw).

---

## T-Account Structure

```
╭──────────────── fed USD ───────────────╮
│  ASSETS              LIABILITIES       │
│  ──────────────────────────────────    │
│  cash  $500          deposits  $1M     │
│  bonds  $12,500                        │
│  reserves  $3M                         │
│  securities  $2.5B                     │
│                      equity  +$2.5B    │  ← magenta, computed
│  ────────────────    ────────────────  │
│  TOTAL  $2.5B        TOTAL  $2.5B  ✓  │
╰────────────────────────────────────────╯
```

---

## Quickstart: Stablecoin Scenario

```bash
python main.py new stablecoin-issuer --currency USD
python main.py entry stablecoin-issuer asset cash 10
python main.py issue stablecoin-issuer tokenusd 10
git add . && git commit -m "step 1: issuer setup + token issued"

python main.py new alice --currency USD
python main.py entry alice asset cash 10
python main.py pay alice stablecoin-issuer 10
python main.py entry alice asset tokenusd 10 --cp stablecoin-issuer
python main.py balancesheets export
git add . && git commit -m "step 2: alice buys tokenusd"

python main.py graph show
# alice ────▶ stablecoin-issuer
```

---

## Quickstart: Bank Money Scenario

```bash
# Alice deposits at the bank
python main.py new alice --currency EUR
python main.py entry alice asset cash 100
python main.py new bank --currency EUR
python main.py deposit bank 100 --from alice
git add . && git commit -m "step 1: alice deposits"

# Bank lends to startup (credit creation — no cash, not in graph)
python main.py new startup --currency EUR
python main.py borrow startup 50 --from bank
git add . && git commit -m "step 2: bank lends to startup"

# Startup draws the cash (now it moves → in graph)
python main.py withdraw bank 50 --to startup
git add . && git commit -m "step 3: startup draws loan"

# Startup pays alice — both at bank, settles intrabank
python main.py pay startup alice 30
git add . && git commit -m "step 4: intrabank payment"

python main.py graph show
# alice ────▶ bank      (deposit)
# bank ────▶ startup    (withdrawal)
```

---

## State & Git Workflow

- `taccounts_state.json` — full ledger state, saved after every command
- `balancesheets.md` — appended each time you run `balancesheets export`

```bash
python main.py balancesheets export
git add taccounts_state.json balancesheets.md
git commit -m "scenario: <step description>"
```

---

## Extending

- Add `repay` — inverse of `borrow` (reduces loan, moves cash back)
- Add `redeem` — inverse of `issue` (burns tokens, releases reserves)
- Add `graph credits` — separate graph showing loan relationships (no cash)
- Add `scenario` — replay a sequence of steps from a `.txt` file
- Use `Textual` for an interactive TUI with live-updating T-accounts