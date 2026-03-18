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

Then use `taccounts` instead of `python main.py`.

---

## All Commands

| Command | Description |
|---------|-------------|
| `new <entity>` | Create a blank balance sheet |
| `entry <entity> asset\|liability <label> <amount>` | Freely add any asset or liability |
| `create <entity> <reserves>` | Create entity with cash + equity (shortcut) |
| `issue <entity> <token> <amount> [--to <receiver>]` | Issue a token as a liability |
| `pay <sender> <receiver> <amount>` | Cash payment — updates both balance sheets |
| `deposit <entity> <asset> <amount> [--from <cp>]` | Add an asset deposit |
| `borrow <entity> <amount> [--from <lender>]` | Borrow cash (loan payable) |
| `balancesheets show` | Display all T-accounts |
| `balancesheets export` | Write to `balancesheets.md` |
| `graph show` | Show payment flow graph |
| `reset --confirm` | Clear all state |

---

## Building Balance Sheets

There are two ways to create an entity:

**Generic — full control:**
```bash
python main.py new my-bank
python main.py entry my-bank asset cash 100
python main.py entry my-bank asset bonds 50 --cp ecb
python main.py entry my-bank liability deposits 80
python main.py entry my-bank liability equity 70
```

**Shortcut — cash + equity in one step:**
```bash
python main.py create my-bank 100
# equivalent to: new + entry asset cash 100 + entry liability equity 100
```

`entry` options:
- `--cp <name>` — tag a counterparty (shown as `← name` on assets, `→ name` on liabilities)
- `--no-show` — suppress T-account print (useful when scripting sequences)
- `--export` — immediately write to `balancesheets.md` after the entry

---

## Cash Payments

`pay` is the **cash leg only**. Both entities must have a `cash` asset and the sender must have sufficient funds. It updates both balance sheets immediately.

```bash
python main.py pay alice bob 30
```

Errors caught:
- Sender has no `cash` asset → tells you to add one first
- Receiver has no `cash` asset → tells you to add one first
- Sender has insufficient cash → shows available vs requested

**Why only cash?** A payment in accounting terms is the cash leg. What the sender received in return (a good, service, or token) is a separate entry — recorded with `entry` or `issue`. Keeping the two sides explicit is the teaching point.

---

## Quickstart: Stablecoin Scenario

```bash
# Step 1 — issuer starts with reserves
python main.py create stablecoin-issuer 10
python main.py balancesheets export
git add . && git commit -m "step 1: issuer setup"

# Step 2 — issue tokenusd as outstanding liability
python main.py issue stablecoin-issuer tokenusd 10
python main.py balancesheets export
git add . && git commit -m "step 2: token issued"

# Step 3 — alice buys tokens by paying cash to the issuer
python main.py create alice 10
python main.py pay alice stablecoin-issuer 10
python main.py entry alice asset tokenusd 10 --cp stablecoin-issuer
python main.py balancesheets export
git add . && git commit -m "step 3: alice buys tokenusd"

# Step 4 — view the payment graph
python main.py graph show
```

---

## Quickstart: Bank Money Scenario

```bash
python main.py create central-bank 100
python main.py create commercial-bank 0
python main.py borrow commercial-bank 20 --from central-bank
python main.py balancesheets show
python main.py graph show
python main.py balancesheets export
git add . && git commit -m "scenario: CB lends reserves to commercial bank"
```

---

## T-Account Structure

```
╭──────────────── stablecoin-issuer ─────────────────╮
│  ASSETS                   LIABILITIES & EQUITY      │
│  ─────────────────────────────────────────────────  │
│  cash  10                 equity  10                │
│                           tokenusd  10 → alice      │
│  ────────────────────     ────────────────────      │
│  TOTAL  10                TOTAL  20  ✗ UNBALANCED   │
╰────────────────────────────────────────────────────╯
```

The **✗ UNBALANCED** flag is intentional for teaching: it shows when a scenario is incomplete — e.g. tokens issued without recording what the issuer received in return. Students must figure out what the missing entry is.

---

## Payment Flow Graph

```
alice ──[cash 10]──▶ stablecoin-issuer
commercial-bank ──[loan 20]──▶ central-bank
```

---

## State & Git Workflow

- `taccounts_state.json` — full ledger state, updated after every command
- `balancesheets.md` — markdown export, appended each time you run `balancesheets export`

Commit after each scenario step to build a git history students can step through:

```bash
python main.py balancesheets export
git add taccounts_state.json balancesheets.md
git commit -m "scenario: <describe the step>"
```

---

## Extending

- Add `settlement.py` to model netting across a payment system
- Add a `scenario` command to replay a sequence of steps from a `.txt` file
- Use the `Textual` library to build an interactive TUI with live-updating T-accounts
- Add a `redeem` command as the inverse of `issue` (burns tokens, releases reserves)
