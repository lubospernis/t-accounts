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
| `redeem <redeemer> <token> <amount> --to <issuer>` | Burn tokens and receive cash (trad world only) |
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

**Currency defaults to USD.** Every entity has a currency (`USD` or `EUR`). `create` and `new` both default to USD. Set EUR with `--currency EUR` at creation time only.

**The payment graph tracks cash flows only (trad) or token flows only (crypto).** Every arrow is a real settlement. Intrabank settlements and bank lending do not appear.

**All cash movements go through one function.** `transfer_cash()` validates, updates both balance sheets, and records the flow.

**Crypto write-back.** Token transfers in crypto world automatically update trad balance sheets too. Both worlds stay in sync at all times.

**Token liabilities aggregate on the issuer.** The issuer tracks total supply outstanding, not individual holders. Holders track which issuer their token came from.

**Two worlds, two graphs, one entity set.** All entities exist in both worlds with separate balance sheet entries and separate payment graphs.

---

## Currency & Amount Formatting

| Amount | USD display | EUR display |
|--------|-------------|-------------|
| 500 | `$500` | `€500` |
| 12,500 | `$12,500` | `€12,500` |
| 3,000,000 | `$3M` | `€3M` |
| 2,500,000,000 | `$2.5B` | `€2.5B` |

Equity always shows an explicit sign: `+$2.5B` or `-€100`.

---

## Token Prices in Trad World

Tokens show both quantity and fiat value on trad balance sheets:

```
tokenusd  10 ← circle ($10)     ← stablecoin: 1:1 automatic
tokeneth   2 ← circle ($4,000)  ← manual price set via `price` command
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

**Intrabank** — both hold deposits at the same bank, not in graph:
```bash
python main.py pay alice bob 20
# deposit balances swap at the bank, no cash moves
```

**Cash** — fallback, recorded in graph:
```bash
python main.py pay alice bob 20
```

---

## Deposits, Withdrawals, Borrowing

```bash
# Open empty account first (no cash moves)
python main.py deposit bank --from alice

# Deposit cash
python main.py deposit bank 50 --from alice

# Withdraw
python main.py withdraw bank 20 --to alice

# Borrow (credit only — no cash moves, not in graph)
python main.py borrow startup 50 --from bank
# Draw cash separately:
python main.py withdraw bank 50 --to startup
```

---

## Token Issuance and Redemption

### Issue

```bash
python main.py issue circle tokenusd 10 --to alice
```

- Circle: `tokenusd liability ↑ 10` (total supply grows, no per-holder breakdown)
- Alice: `tokenusd asset ↑ 10 ← circle` (knows her issuer)

### Redeem (trad world only)

```bash
python main.py redeem alice tokenusd 10 --to circle
```

Two things happen simultaneously:

**Burn:**
- Alice: `tokenusd asset ↓ 10`
- Circle: `tokenusd liability ↓ 10` (supply shrinks)

**Cash settlement:**
- Circle: `cash ↓ 10`
- Alice: `cash ↑ 10`

Circle's balance sheet shrinks on both sides equally. Alice does a pure asset swap — equity unchanged. Circle must have enough cash to honour the redemption; if it lent out reserves it cannot redeem. This is the stablecoin reserve adequacy lesson.

Three validations:
1. Redeemer must hold enough tokens
2. Issuer must have that token outstanding
3. Issuer must have enough cash (reserve check)

---

## Two Worlds

### Trad World 🏦
- Yellow borders, green assets, red liabilities
- Cash-based, full T-accounts with equity
- Tokens show quantity + fiat value: `tokenusd 10 ← circle ($10)`
- Token liabilities show aggregate supply only: `tokenusd 25 ($25)`
- Graph shows cash flows only (intrabank and lending excluded)

### Crypto World ⛓️
- Cyan borders, blue assets, yellow liabilities
- Token-only — no cash concept
- Only token-holding entities visible (issuers and banks stay in trad)
- Tokens are bearer assets — no counterparty annotation
- Per-token net position replaces aggregate equity:
  ```
  tokenusd 💵    net +10  ✓
  tokeneth Ξ     net -3   ⚠ short
  ```
- Graph shows fully labelled token flows: `alice ──tokenusd 💵 30──▶ bob`

```bash
python main.py worldswitch    # toggle, shows all sheets immediately
```

---

## The Bridge: Trad ↔ Crypto

Tokens enter the crypto world via `issue` in trad world. On `worldswitch`:
- Issued tokens carry over to crypto sheets automatically
- Counterparty annotations stripped (bearer assets in crypto)
- Issuers and banks hidden in crypto world

Crypto token transfers write back to trad balance sheets automatically — both worlds stay in sync.

```bash
# Trad: Circle issues USDC to alice and bob
python main.py create circle 1000
python main.py create alice 0
python main.py create bob 0
python main.py issue circle tokenusd 100 --to alice
python main.py issue circle tokenusd 50 --to bob

# Crypto: alice pays bob 30 tokens
python main.py worldswitch
python main.py pay alice bob 30
# → alice: tokenusd 💵 70   bob: tokenusd 💵 80

# Back to trad: balances updated automatically
python main.py worldswitch
# → alice: tokenusd 70 ($70)   bob: tokenusd 80 ($80)

# Trad: bob redeems 20 tokens
python main.py redeem bob tokenusd 20 --to circle
# → bob: cash $20, tokenusd 60 ($60)
# → circle: cash $980, tokenusd 130 ($130) outstanding
```

---

## T-Account Structure

**Trad world:**
```
╭──────────────── circle USD ─────────────────╮
│  ASSETS              LIABILITIES            │
│  ─────────────────────────────────────────  │
│  cash  $980          tokenusd  130 ($130)   │  ← total supply, no breakdown
│                      equity  +$850          │
│  ──────────────────  ──────────────────     │
│  TOTAL  $980         TOTAL  $980  ✓         │
╰─────────────────────────────────────────────╯
```

**Crypto world:**
```
╭──────────────── alice ⛓ ────────────────────╮
│  ASSETS              LIABILITIES            │
│  ─────────────────────────────────────────  │
│  tokenusd  💵 70                            │
│  ──────────────────  ──────────────────     │
│  tokenusd 💵          net +70  ✓            │
╰─────────────────────────────────────────────╯
```

---

## Payment Graphs

**Trad graph** — cash flows, arrows labelled with instrument and amount:
```
alice ────▶ bank          (deposit: cash)
circle ────▶ bob          (redeem: cash payout)
```

**Crypto graph** — token flows, fully labelled:
```
alice ──tokenusd 💵 30──▶ bob
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

- Add `repay` — inverse of `borrow` (reduces loan-payable, cash moves back to lender)
- Add `graph credits` — credit relationship graph separate from cash payments
- Add FX rates between USD and EUR for cross-currency token valuation
- Add `scenario` — replay a sequence of steps from a `.txt` file
- Use `Textual` for an interactive TUI with live-updating T-accounts