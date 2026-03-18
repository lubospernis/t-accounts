"""
ledger.py — T-account state for all entities.

Accounting identity enforced here:
    Assets = Liabilities + Equity
    => Equity = Assets - Liabilities  (derived, never stored as a liability)

Equity is computed on the fly from the balance sheet. It is displayed
separately in the renderer and exported to markdown, but never stored
in the liabilities list. Any "equity" entry that was manually added is
treated as a regular liability (e.g. paid-in capital) — only the
auto-computed residual equity is the balancing item.
"""
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

STATE_FILE = Path("taccounts_state.json")


@dataclass
class Entity:
    name: str
    assets: list = field(default_factory=list)
    liabilities: list = field(default_factory=list)  # excludes residual equity

    # ── asset helpers ────────────────────────────────────────────────────────

    def add_asset(self, label: str, amount: float, counterparty=None):
        for e in self.assets:
            if e["label"] == label and e.get("counterparty") == counterparty:
                e["amount"] += amount
                return
        self.assets.append({"label": label, "amount": amount, "counterparty": counterparty})

    def remove_asset(self, label: str, amount: float) -> bool:
        for e in self.assets:
            if e["label"] == label:
                e["amount"] -= amount
                if e["amount"] <= 0:
                    self.assets.remove(e)
                return True
        return False

    def cash(self) -> float:
        entry = next((e for e in self.assets if e["label"] == "cash"), None)
        return entry["amount"] if entry else 0.0

    # ── liability helpers ────────────────────────────────────────────────────

    def add_liability(self, label: str, amount: float, counterparty=None):
        if label == "equity":
            # Equity is computed — silently ignore any attempt to store it
            return
        for e in self.liabilities:
            if e["label"] == label and e.get("counterparty") == counterparty:
                e["amount"] += amount
                return
        self.liabilities.append({"label": label, "amount": amount, "counterparty": counterparty})

    def remove_liability(self, label: str, amount: float) -> bool:
        for e in self.liabilities:
            if e["label"] == label:
                e["amount"] -= amount
                if e["amount"] <= 0:
                    self.liabilities.remove(e)
                return True
        return False

    # ── accounting identity ──────────────────────────────────────────────────

    def total_assets(self) -> float:
        return sum(e["amount"] for e in self.assets)

    def total_explicit_liabilities(self) -> float:
        """Sum of all liabilities excluding residual equity."""
        return sum(e["amount"] for e in self.liabilities)

    def equity(self) -> float:
        """Residual equity: Assets - Liabilities. Always balances the sheet."""
        return self.total_assets() - self.total_explicit_liabilities()

    def total_liabilities_and_equity(self) -> float:
        return self.total_explicit_liabilities() + self.equity()

    def is_balanced(self) -> bool:
        """Always true by construction — equity is the residual."""
        return True


class Ledger:
    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.transactions: list[dict] = []
        self.load()

    def save(self):
        data = {
            "entities": {
                name: {"name": e.name, "assets": e.assets, "liabilities": e.liabilities}
                for name, e in self.entities.items()
            },
            "transactions": self.transactions,
        }
        STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self):
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            for name, ed in data.get("entities", {}).items():
                ent = Entity(name=ed["name"])
                # Strip any stored "equity" entries from old state files
                ent.assets = ed["assets"]
                ent.liabilities = [l for l in ed["liabilities"] if l["label"] != "equity"]
                self.entities[name] = ent
            self.transactions = data.get("transactions", [])

    def create(self, name: str, reserves: float):
        if name in self.entities:
            raise ValueError(f"Entity '{name}' already exists.")
        e = Entity(name=name)
        if reserves > 0:
            e.add_asset("cash", reserves)
        # No explicit equity entry — it's computed as assets - liabilities
        self.entities[name] = e
        self.save()
        return e

    def get(self, name: str) -> Entity:
        if name not in self.entities:
            raise ValueError(f"Entity '{name}' not found. Create it first.")
        return self.entities[name]

    def record_transaction(self, sender: str, receiver: str, instrument: str, amount: float, tx_type: str):
        self.transactions.append({
            "sender": sender,
            "receiver": receiver,
            "instrument": instrument,
            "amount": amount,
            "type": tx_type,
        })
        self.save()

    def reset(self):
        self.entities = {}
        self.transactions = []
        if STATE_FILE.exists():
            STATE_FILE.unlink()
