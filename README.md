# taccounts 📊

A command-line T-account simulator for teaching monetary economics — stablecoins, bank money, payment flows.

## Install

```bash
pip install typer rich
```

Then alias it for convenience:

```bash
alias taccounts="python /path/to/taccounts/main.py"
```

Or install as a proper CLI tool:

```bash
pip install typer[all] rich
# from the project directory:
python main.py --help
```

## Quickstart: Stablecoin Scenario

```bash
# 1. Create the issuer with 10 in initial reserves
python main.py create stablecoin-issuer 10

# 2. Issue 10 tokenusd as an outstanding liability
python main.py issue stablecoin-issuer tokenusd 10

# 3. Or issue directly to a holder
python main.py create alice 0
python main.py issue stablecoin-issuer tokenusd 10 --to alice

# 4. Show all balance sheets
python main.py balancesheets show

# 5. Alice pays Bob
python main.py create bob 0
python main.py pay alice bob tokenusd 5

# 6. Show payment graph
python main.py graph show

# 7. Export to markdown (for git)
python main.py balancesheets export
git add balancesheets.md && git commit -m "step: stablecoin issuance"
```

## All Commands

| Command | Description |
|---------|-------------|
| `create <entity> <reserves>` | Create entity with initial cash + equity |
| `issue <entity> <token> <amount> [--to <receiver>]` | Issue a token/liability |
| `pay <sender> <receiver> <instrument> <amount>` | Payment between entities |
| `deposit <entity> <asset> <amount> [--from <counterparty>]` | Add asset deposit |
| `borrow <entity> <amount> [--from <lender>]` | Borrow cash (loan payable) |
| `balancesheets show` | Display all T-accounts |
| `balancesheets export` | Write to `balancesheets.md` |
| `graph show` | Show payment flow graph |
| `reset --confirm` | Clear all state |

## State & Git Workflow

State is saved to `taccounts_state.json` after every command.
Balance sheets are exported to `balancesheets.md`.

Recommended git workflow:
```bash
python main.py create central-bank 100
python main.py balancesheets export
git add . && git commit -m "scenario: initial CB setup"

python main.py create commercial-bank 0
python main.py borrow commercial-bank 20 --from central-bank
python main.py balancesheets export
git add . && git commit -m "scenario: commercial bank borrows reserves"
```

## T-Account Structure

```
╭──────── stablecoin-issuer ────────╮
│ ASSETS          LIABILITIES       │
│ ──────────────────────────────    │
│ cash  10        equity  10        │
│                 tokenusd  10      │
│ TOTAL  10       TOTAL  20  ✗      │  ← unbalanced = teaching moment!
╰───────────────────────────────────╯
```

The ✗ UNBALANCED flag is intentional for teaching: it shows students when a scenario is incomplete (e.g. tokens issued without recording what the issuer received in return).

## Payment Graph

```
stablecoin-issuer ──[tokenusd 10]──▶ alice
alice ──[tokenusd 5]──▶ bob
```

## Extending

- Add `settlement.py` to model netting across a payment system
- Add `--scenario` flag to replay a sequence of commands from a `.txt` file
- Use `Textual` library to build an interactive TUI with live-updating T-accounts
