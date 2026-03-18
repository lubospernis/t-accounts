# taccounts 📊

A command-line T-account simulator for teaching monetary economics — stablecoins, bank money, payment flows, and the bridge between TradFi and crypto.

## Install

```bash
pip install typer rich
```

Run from the project directory:

```bash
python main.py --help
```

**PowerShell alias (optional):** add to your `$PROFILE`:

```powershell
function taccounts { python "C:\path\to\t-accounts\main.py" @args }
```

---

## All Commands

| Command | Description |
|---------|-------------|
| `new <entity> [--currency EUR]` | Create a blank balance sheet (defaults to USD) |
| `entry <entity> asset\|liability <label> <amount>` | Freely add any asset or liability |
| `create <entity> <reserves> [--currency EUR]` | Create entity with initial cash (defaults to USD) |
| `issue <entity> <token> <amount> --to <receiver>` | Issue a token — liability on issuer, asset on receiver |
| `pay <sender> <receiver> <amount> [--token <n>]` | Payment — intrabank, cash, or token (crypto) |
| `deposit <bank> <amount> --from <depositor>` | Deposit cash into a bank (0 = open empty account) |
| `withdraw <bank> <amount> --to <withdrawer>` | Withdraw cash from a bank |
| `borrow <entity> <amount> --from <lender>` | Create a loan (no cash moves) |
| `price <token> <amount> [--currency EUR]` | Set fiat price per token for trad world display |
| `worldswitch` | Toggle between trad and crypto world |
| `balancesheets show` | Display all T-accounts |
| `balancesheets export` | Write to `balancesheets.md` |
| `graph show` | Show payment graph (world-specific) |
| `reset --confirm` | Clear all state |

---

## Core Design Principles

**Equity is always computed, never stored.** `Assets = Liabilities + Equity` by construction. Equity is the residual, shown in magenta.

**Currency defaults to USD.** Every entity has a currency (`USD` or `EUR`). `create` and `new` both default to USD. Set EUR with `--currency EUR`.

**The payment graph tracks cash flows only (trad) or token flows only (crypto).** No mixing. Every arrow in the graph is a real settlement.

**All cash movements go through one function.** `transfer_cash()` validates, updates both balance sheets, and records the flow. No cash can move without appearing in the graph.

**Crypto write-back.** Token transfers in crypto world automatically update the trad balance sheets too. Both worlds stay in sync at all times.

**Two worlds, two graphs, one entity set.** All entities exist in both worlds but with separate balance sheet entries. The payment graph is also separate per world.

---

## Currency & Amount Formatting

All entities default to USD. Set EUR with `--currency EUR` at creation time only.

| Amount | USD display | EUR display |
|--------|-------------|-------------|
| 500 | `$500` | `€500` |
| 12,500 | `$12,500` | `€12,500` |
| 3,000,000 | `$3M` | `€3M` |
| 2,500,000,000 | `$2.5B` | `€2.5B` |

Equity always shows an explicit sign: `+$2.5B` or `-€100`.

---

## Token Prices in Trad World

Tokens appear on trad balance sheets with both quantity and fiat value:

```
tokenusd  $10 ← issuer ($10)     ← stablecoin: 1:1 automatic
tokeneth  $2 ← issuer ($4,000)   ← manual price set via `price` command
```

**Automatic stablecoin pegs:**
- `tokenusd` = 1 USD per token
- `tokeneur` = 1 EUR per token

**Manual prices for other tokens:**
```bash
python main.py price tokeneth 2000          # 1 tokeneth = $2,000
python main.py price tokenbtc 50000         # 1 tokenbtc = $50,000
python main.py price tokeneth 1850 --currency EUR
```

Tokens without a known price show quantity only (no fiat value in parentheses).

---

## Building Balance Sheets

```bash
# Generic — full control
python main.py new fed --currency USD
python main.py entry fed asset cash 500
python main.py entry fed asset bonds 12500
python main.py entry fed liability deposits 1000000

# Shortcut — cash asset, equity is residual
python main.py create bank 100              # USD by default
python main.py create ecb 100 --currency EUR
```

`entry` options:
- `--cp <n>` — tag a counterparty
- `--no-show` — suppress T-account print
- `--export` — write to `balancesheets.md` immediately

---

## Cash Payments (Trad World)

`pay` detects the settlement path automatically:

**Intrabank** — both hold deposits at the same bank:
```bash
python main.py pay alice bob 20
# → deposit balances swap at the bank, no cash moves, not in graph
```

**Cash** — fallback when no shared institution:
```bash
python main.py pay alice bob 20
# → cash transfers directly, recorded in graph
```

---

## Deposits, Withdrawals, Borrowing

```bash
# Open an account with no initial balance
python main.py deposit bank --from alice

# Deposit cash
python main.py deposit bank 50 --from alice
# Alice: cash ↓, deposit@bank ↑ | Bank: cash ↑, deposit-alice ↑

# Withdraw
python main.py withdraw bank 20 --to alice
# Alice: deposit@bank ↓, cash ↑ | Bank: cash ↓, deposit-alice ↓

# Borrow (credit only — no cash moves)
python main.py borrow startup 50 --from bank
# Startup: deposit@bank ↑, loan-payable ↑ | Bank: loan-receivable ↑, deposit-startup ↑
# Then draw cash:
python main.py withdraw bank 50 --to startup
```

---

## Two Worlds

### Trad World 🏦
- Yellow borders, green assets, red liabilities
- Cash-based, full T-accounts with equity
- Tokens show with fiat value: `tokenusd $10 ($10)`
- Graph shows cash flows only

### Crypto World ⛓️
- Cyan borders, blue assets, yellow liabilities
- Token-only — no cash concept
- Only token-holding entities are visible (issuers and banks stay in trad)
- Tokens are bearer assets — no counterparty annotation
- Per-token net position instead of aggregate equity:
  ```
  tokenusd 💵    net +10  ✓
  tokeneth Ξ     net -3   ⚠ short
  ```
- Graph shows labelled token flows: `alice ──tokenusd 💵 30──▶ bob`

```bash
python main.py worldswitch    # toggle, shows all sheets immediately
python main.py worldswitch    # toggle back
```

---

## The Bridge: Issue → Worldswitch

Tokens enter the crypto world via `issue` in trad world. On `worldswitch`:
- Issued tokens carry over to crypto sheets automatically
- Counterparty annotations are stripped (bearer assets)
- Issuers and banks are hidden in crypto world

```bash
# Trad world: Circle issues USDC
python main.py create circle 1000000
python main.py create alice 0
python main.py issue circle tokenusd 10000 --to alice

# Worldswitch: Alice appears with her wallet balance
python main.py worldswitch
# → alice ⛓: tokenusd 💵 10,000  net +10,000 ✓
# → circle: invisible in crypto world

# Crypto payment: alice pays bob
python main.py create bob 0    # bob exists from trad world
python main.py worldswitch     # back to trad to issue to bob first
python main.py issue circle tokenusd 5000 --to bob
python main.py worldswitch     # to crypto
python main.py pay alice bob 1000

# Back to trad — alice's balance reflects the crypto payment
python main.py worldswitch
# → alice: tokenusd $9,000 ($9,000)
# → bob:   tokenusd $6,000 ($6,000)
```

---

## T-Account Structure

**Trad world:**
```
╭──────────────── alice USD ─────────────────╮
│  ASSETS                  LIABILITIES       │
│  ────────────────────────────────────────  │
│  cash  $500                                │
│  tokenusd  $10 ← issuer ($10)              │
│  tokeneth  $2 ← issuer ($4,000)            │
│                          equity  +$4,510   │
│  ────────────────────    ────────────────  │
│  TOTAL  $4,510           TOTAL  $4,510  ✓  │
╰────────────────────────────────────────────╯
```

**Crypto world:**
```
╭──────────────── alice ⛓ ───────────────────╮
│  ASSETS                  LIABILITIES       │
│  ────────────────────────────────────────  │
│  tokenusd  💵 10                           │
│  tokeneth  Ξ 2                             │
│  ────────────────────    ────────────────  │
│  tokenusd 💵             net +10  ✓        │
│  tokeneth Ξ              net +2   ✓        │
╰────────────────────────────────────────────╯
```

---

## Payment Graphs

**Trad graph** — cash flows, unlabelled:
```
alice ────▶ bank          (deposit)
bank ────▶ startup        (withdrawal after borrow)
```

**Crypto graph** — token flows, fully labelled:
```
alice ──tokenusd 💵 1,000──▶ bob
bob ──tokeneth Ξ 0.5──▶ carol
```

---

## State & Git Workflow

- `taccounts_state.json` — full ledger state (both worlds), saved after every command
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
- Add `graph credits` — credit relationship graph separate from payments
- Add `scenario` — replay a sequence from a `.txt` file
- Add FX rates between USD and EUR for cross-currency token valuation
- Use `Textual` for an interactive TUI with live-updating T-accounts