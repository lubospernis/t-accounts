"""
ledger.py — T-account state for all entities.
Each entity has Assets (left) and Liabilities+Equity (right).
"""
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

STATE_FILE = Path("taccounts_state.json")

@dataclass
class Entry:
    label: str
    amount: float
    counterparty: Optional[str] = None  # who is the other side

@dataclass
class Entity:
    name: str
    assets: list = field(default_factory=list)
    liabilities: list = field(default_factory=list)

    def add_asset(self, label: str, amount: float, counterparty=None):
        for e in self.assets:
            if e["label"] == label and e.get("counterparty") == counterparty:
                e["amount"] += amount
                return
        self.assets.append({"label": label, "amount": amount, "counterparty": counterparty})

    def add_liability(self, label: str, amount: float, counterparty=None):
        for e in self.liabilities:
            if e["label"] == label and e.get("counterparty") == counterparty:
                e["amount"] += amount
                return
        self.liabilities.append({"label": label, "amount": amount, "counterparty": counterparty})

    def remove_asset(self, label: str, amount: float):
        for e in self.assets:
            if e["label"] == label:
                e["amount"] -= amount
                if e["amount"] <= 0:
                    self.assets.remove(e)
                return True
        return False

    def remove_liability(self, label: str, amount: float):
        for e in self.liabilities:
            if e["label"] == label:
                e["amount"] -= amount
                if e["amount"] <= 0:
                    self.liabilities.remove(e)
                return True
        return False

    def total_assets(self):
        return sum(e["amount"] for e in self.assets)

    def total_liabilities(self):
        return sum(e["amount"] for e in self.liabilities)

    def is_balanced(self):
        return abs(self.total_assets() - self.total_liabilities()) < 0.0001


class Ledger:
    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.transactions: list[dict] = []  # for graph
        self.load()

    def save(self):
        data = {
            "entities": {
                name: {"name": e.name, "assets": e.assets, "liabilities": e.liabilities}
                for name, e in self.entities.items()
            },
            "transactions": self.transactions,
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))

    def load(self):
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            for name, ed in data.get("entities", {}).items():
                ent = Entity(name=ed["name"])
                ent.assets = ed["assets"]
                ent.liabilities = ed["liabilities"]
                self.entities[name] = ent
            self.transactions = data.get("transactions", [])

    def create(self, name: str, reserves: float):
        if name in self.entities:
            raise ValueError(f"Entity '{name}' already exists.")
        e = Entity(name=name)
        e.add_asset("cash", reserves)
        e.add_liability("equity", reserves)
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
