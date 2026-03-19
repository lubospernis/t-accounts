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
| `new <entity> [--currency EUR] [--address]` | Create a blank balance sheet |
| `entry <entity> asset\|liability <label> <amount>` | Freely add any asset or liability |
| `create <entity> <reserves> [--currency EUR] [--address]` | Create entity with initial cash |
| `issue <entity> <token> <amount> --to <receiver>` | Issue a token |
| `redeem <redeemer> <token> <amount> --to <issuer>` | Burn tokens and receive settlement |
| `pay <sender> <receiver> <amount> [--token <n>]` | Payment — intrabank, cash, or token |
| `deposit <bank> <amount> --from <depositor>` | Deposit cash (0 = open empty account) |
| `withdraw <bank> <amount> --to <withdrawer>` | Withdraw cash from a bank |
| `borrow <entity> <amount> --from <lender>` | Create a loan (no cash moves) |
| `price <token> <amount> [--currency EUR]` | Set fiat price per token |
| `fxrate <pair> <rate>` | Set FX rate (e.g. `fxrate EURUSD 1.08`) |
| `worldswitch` | Toggle between trad and crypto world |
| `balancesheets show` | Display all T-accounts |
| `balancesheets export` | Write to `balancesheets.md` |
| `graph show` | Show payment graph (world-specific) |
| `reset --confirm` | Clear all state |

---

## Core Design Principles

**Equity is always computed.** `Assets = Liabilities + Equity` by construction. Equity is the residual, shown in magenta.

**Currency defaults to USD.** Every entity has a currency (`USD` or `EUR`). Set EUR with `--currency EUR` at creation time only.

**Address = crypto presence.** An entity only appears in crypto world if it has a wallet address. Assign one with `--address` at creation. Without an address, the entity is trad-only — invisible on-chain.

**The payment graph is strict.** Only direct cash transfers between parties (`pay` with no shared bank) and on-chain token transfers appear. Deposits, withdrawals, issuances, redemptions, and intrabank settlements do not — they are balance sheet restructurings, not payments.

**Crypto write-back.** Token transfers in crypto world update trad balance sheets automatically.

**Token liabilities aggregate on the issuer.** The issuer tracks total supply, not individual holders.

**Redemption requires currency match.** A EUR-denominated entity cannot redeem a USD-pegged token at a USD issuer.

---

## Currency, FX & Token Prices

All entities default to USD. EUR entities holding USD-pegged tokens need an FX rate to show values in EUR.

```bash
python main.py fxrate EURUSD 1.08     # 1 EUR = 1.08 USD

python main.py price tokeneth 2000    # 1 tokeneth = $2,000
python main.py price tokeneth 1850 --currency EUR
```

**Automatic stablecoin pegs:** `tokenusd` = 1 USD, `tokeneur` = 1 EUR.

Trad balance sheets show token quantity + fiat value:
```
tokenusd  10 ← circle ($10)      ← USD entity, direct peg
tokenusd  10 ← circle (€9)       ← EUR entity, converted via EURUSD rate
```

---

## Wallet Addresses

An address is a short random hex string (`0x3f7a1c2b`) assigned at creation. It:
- Makes the entity visible in crypto world
- Appears in the panel title in crypto world
- Enables trad balance sheet write-back from crypto transfers
- Is required to appear in the crypto payment graph

```bash
python main.py create circle 100 --address       # 0x1bb18e0e
python main.py new charlie --currency EUR --address  # 0xd6f2b126
python main.py new bank                          # no address — trad only
```

In crypto world:
```
╭── alice ⛓ 0x5871065b ──╮    ╭── charlie ⛓ 0xd6f2b126 ──╮
│  tokenusd  💵 15       │    │  tokenusd  💵 15          │
│  tokenusd 💵  net +15  │    │  tokenusd 💵  net +15     │
╰────────────────────────╯    ╰───────────────────────────╯
```
`bank` (no address) is invisible.

---

## Building Balance Sheets

```bash
# With crypto address
python main.py create circle 100 --address
python main.py new charlie --currency EUR --address

# Without — trad only
python main.py new bank
python main.py create ecb 1000 --currency EUR
```

`entry` options: `--cp <n>`, `--no-show`, `--export`

---

## Token Issuance and Redemption

```bash
# Issue
python main.py issue circle tokenusd 10 --to alice
# circle: tokenusd liability ↑ 10 (total supply, no holder breakdown)
# alice:  tokenusd asset ↑ 10 ← circle

# Redeem (trad world only, currency must match)
python main.py redeem alice tokenusd 5 --to circle   # ✓ both USD
python main.py redeem charlie tokenusd 5 --to circle # ✗ charlie is EUR
```

Redemption: burn + cash settlement simultaneously. Circle's balance sheet shrinks both sides. Redeemer does a pure asset swap.

---

## Two Worlds

### Trad World 🏦
- Yellow borders, USD/EUR denominated
- Full T-accounts with equity
- Token quantities + fiat values: `tokenusd 10 ← circle ($10)`
- All entities visible regardless of address
- Graph: direct cash payments only

### Crypto World ⛓️
- Cyan borders, address shown in title
- **Only entities with a wallet address are visible**
- Token-only, no cash, no currency denomination
- Per-token net positions replace aggregate equity
- `⚠ short` flag when net is negative
- Graph: labelled token flows only — `alice ──tokenusd 💵 5──▶ charlie`

```bash
python main.py worldswitch   # toggle, shows all sheets immediately
```

---

## The Bridge: Issue → Worldswitch

```bash
# Trad: Circle issues USDC
python main.py create circle 1000 --address
python main.py create alice 0 --address
python main.py new charlie --currency EUR --address   # EUR wallet
python main.py fxrate EURUSD 1.08

python main.py issue circle tokenusd 100 --to alice
python main.py issue circle tokenusd 50 --to charlie

# Trad: charlie sees EUR value
# tokenusd  50 ← circle (€46)

# Crypto: alice pays charlie
python main.py worldswitch
python main.py pay alice charlie 20
# alice: tokenusd 💵 80   charlie: tokenusd 💵 70

# Back to trad: write-back applied
python main.py worldswitch
# alice: tokenusd 80 ($80)   charlie: tokenusd 70 (€65)

# alice redeems (USD ✓)
python main.py redeem alice tokenusd 10 --to circle

# charlie cannot redeem at circle (EUR ✗)
python main.py redeem charlie tokenusd 5 --to circle
# Error: charlie is EUR-denominated but tokenusd settles in USD
```

---

## Payment Graph

The graph only records genuine settlements:

| Operation | In graph? | Why |
|-----------|-----------|-----|
| `issue` | No | Creates credit, not a payment |
| `deposit` | No | Asset swap (cash ↔ deposit claim) |
| `withdraw` | No | Asset swap (deposit claim ↔ cash) |
| `redeem` | No | Burn + asset swap |
| `borrow` | No | Credit creation |
| `pay` intrabank | No | Internal ledger entry |
| `pay` direct cash | **Yes** | Final settlement in base money |
| `pay` token (crypto) | **Yes** | On-chain token transfer |

The graph being empty in most scenarios is the lesson: most economic activity is balance sheet restructuring, not payment.

---

## State & Git Workflow

```bash
python main.py balancesheets export
git add taccounts_state.json balancesheets.md
git commit -m "scenario: <step>"
```

---

## Extending

- Add `repay` — inverse of `borrow`
- Add `graph credits` — credit relationship graph
- Add EUR-denominated stablecoin issuer scenario (`tokeneur`)
- Add FX swap: charlie converts tokenusd → tokeneur via an exchange entity
- Use `Textual` for an interactive TUI