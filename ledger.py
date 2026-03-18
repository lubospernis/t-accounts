"""
ledger.py — T-account state for all entities.

Accounting identity enforced here:
    Assets = Liabilities + Equity
    => Equity = Assets - Liabilities  (derived, never stored as a liability)

All cash movements go through transfer_cash(), which validates balances
and records the transaction in the graph regardless of which command triggered it.
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

    # Labels that always aggregate regardless of counterparty
    FUNGIBLE = {"cash"}

    # ── asset helpers ────────────────────────────────────────────────────────

    def add_asset(self, label: str, amount: float, counterparty=None):
        for e in self.assets:
            if e["label"] == label and (
                label in self.FUNGIBLE or e.get("counterparty") == counterparty
            ):
                e["amount"] += amount
                return
        cp = None if label in self.FUNGIBLE else counterparty
        self.assets.append({"label": label, "amount": amount, "counterparty": cp})

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
            return  # equity is computed, never stored
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
        return sum(e["amount"] for e in self.liabilities)

    def equity(self) -> float:
        return self.total_assets() - self.total_explicit_liabilities()

    def total_liabilities_and_equity(self) -> float:
        return self.total_explicit_liabilities() + self.equity()

    def is_balanced(self) -> bool:
        return True  # always true by construction


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

    def transfer_cash(self, sender: str, receiver: str, amount: float, tx_type: str = "payment"):
        """
        The single authoritative cash transfer function.
        Validates both sides, moves cash, and records the transaction.
        Raises ValueError with a descriptive message on any validation failure.
        """
        s = self.get(sender)
        r = self.get(receiver)

        sender_cash = next((e for e in s.assets if e["label"] == "cash"), None)
        if sender_cash is None:
            raise ValueError(f"'{sender}' has no cash asset.")
        if sender_cash["amount"] < amount:
            raise ValueError(
                f"'{sender}' has insufficient cash: "
                f"{sender_cash['amount']:,.0f} available, {amount:,.0f} requested."
            )

        # Receiver gets cash whether or not they had it before
        sender_cash["amount"] -= amount
        if sender_cash["amount"] == 0:
            s.assets.remove(sender_cash)

        r.add_asset("cash", amount)

        self.record_transaction(sender, receiver, "cash", amount, tx_type)
        self.save()

    def reset(self):
        self.entities = {}
        self.transactions = []
        if STATE_FILE.exists():
            STATE_FILE.unlink()
