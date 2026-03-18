"""
ledger.py — T-account state for all entities.

Two worlds: "trad" (default) and "crypto".
  - trad:   cash-based, full T-accounts
  - crypto: token-only, no cash concept, sheets start empty

Each entity holds separate asset/liability lists per world.
The active world is set on Ledger; entity.assets / entity.liabilities
always return the active world's lists via the Ledger.active_world property.

Accounting identity: Assets = Liabilities + Equity (equity is always residual).
All cash movements go through transfer_cash() in trad world.
All token movements go through transfer_token() in crypto world.
"""
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

STATE_FILE = Path("taccounts_state.json")

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€"}

# Token emoji lookup for crypto world display
TOKEN_EMOJI = {
    "tokenusd": "💵",
    "tokeneur": "💶",
    "tokenbtc": "₿",
    "tokeneth": "Ξ",
}
DEFAULT_TOKEN_EMOJI = "🪙"


def token_emoji(label: str) -> str:
    return TOKEN_EMOJI.get(label.lower(), DEFAULT_TOKEN_EMOJI)


def fmt_amount(amount: float, currency: Optional[str] = None, signed: bool = False,
               world: str = "trad", token_label: Optional[str] = None) -> str:
    """Format a number with optional currency symbol/token emoji and scale suffix.
    In crypto world, currency symbols are suppressed — only token emojis apply."""
    if world == "crypto":
        # Never show fiat symbols in crypto world
        symbol = (token_emoji(token_label) + " ") if token_label else ""
    else:
        symbol = CURRENCY_SYMBOLS.get(currency, "") if currency else ""

    abs_amount = abs(amount)
    neg = amount < 0

    if abs_amount >= 1_000_000_000:
        scaled = f"{abs_amount / 1_000_000_000:.2f}".rstrip("0").rstrip(".")
        text = f"{symbol}{scaled}B"
    elif abs_amount >= 1_000_000:
        scaled = f"{abs_amount / 1_000_000:.2f}".rstrip("0").rstrip(".")
        text = f"{symbol}{scaled}M"
    else:
        text = f"{symbol}{abs_amount:,.0f}"

    if neg:
        return "-" + text
    if signed:
        return "+" + text
    return text


@dataclass
class Entity:
    name: str
    assets_trad: list = field(default_factory=list)
    liabilities_trad: list = field(default_factory=list)
    assets_crypto: list = field(default_factory=list)
    liabilities_crypto: list = field(default_factory=list)
    currency: Optional[str] = None

    # Active world — set by Ledger when loading/switching
    _world: str = field(default="trad", repr=False)

    FUNGIBLE_TRAD = {"cash"}

    @property
    def FUNGIBLE(self):
        if self._world == "crypto":
            # In crypto world all tokens aggregate (no counterparty tracking on token balances)
            return None  # handled in add_asset
        return self.FUNGIBLE_TRAD

    @property
    def assets(self) -> list:
        return self.assets_crypto if self._world == "crypto" else self.assets_trad

    @property
    def liabilities(self) -> list:
        return self.liabilities_crypto if self._world == "crypto" else self.liabilities_trad

    def fmt(self, amount: float, signed: bool = False, label: Optional[str] = None) -> str:
        return fmt_amount(amount, self.currency, signed=signed,
                          world=self._world, token_label=label)

    # ── asset helpers ────────────────────────────────────────────────────────

    def add_asset(self, label: str, amount: float, counterparty=None):
        lst = self.assets  # uses active world
        fungible = self.FUNGIBLE
        # In crypto world: tokens (non-deposit@) always aggregate regardless of counterparty
        is_fungible = (fungible is None and not label.startswith("deposit@")) or (fungible and label in fungible)
        for e in lst:
            if e["label"] == label and (is_fungible or e.get("counterparty") == counterparty):
                e["amount"] += amount
                return
        cp = None if is_fungible else counterparty
        lst.append({"label": label, "amount": amount, "counterparty": cp})

    def remove_asset(self, label: str, amount: float) -> bool:
        lst = self.assets
        for e in lst:
            if e["label"] == label:
                e["amount"] -= amount
                if e["amount"] <= 0:
                    lst.remove(e)
                return True
        return False

    def cash(self) -> float:
        entry = next((e for e in self.assets if e["label"] == "cash"), None)
        return entry["amount"] if entry else 0.0

    # ── liability helpers ────────────────────────────────────────────────────

    def add_liability(self, label: str, amount: float, counterparty=None):
        if label == "equity":
            return
        lst = self.liabilities
        for e in lst:
            if e["label"] == label and e.get("counterparty") == counterparty:
                e["amount"] += amount
                return
        lst.append({"label": label, "amount": amount, "counterparty": counterparty})

    def remove_liability(self, label: str, amount: float) -> bool:
        lst = self.liabilities
        for e in lst:
            if e["label"] == label:
                e["amount"] -= amount
                if e["amount"] <= 0:
                    lst.remove(e)
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
        return True


class Ledger:
    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.transactions_trad: list[dict] = []
        self.transactions_crypto: list[dict] = []
        self.world: str = "trad"
        self.load()

    @property
    def transactions(self) -> list:
        return self.transactions_crypto if self.world == "crypto" else self.transactions_trad

    def _set_world(self, world: str):
        self.world = world
        for e in self.entities.values():
            e._world = world

    def save(self):
        data = {
            "world": self.world,
            "entities": {
                name: {
                    "name": e.name,
                    "assets_trad": e.assets_trad,
                    "liabilities_trad": [l for l in e.liabilities_trad if l["label"] != "equity"],
                    "assets_crypto": e.assets_crypto,
                    "liabilities_crypto": [l for l in e.liabilities_crypto if l["label"] != "equity"],
                    "currency": e.currency,
                }
                for name, e in self.entities.items()
            },
            "transactions_trad": self.transactions_trad,
            "transactions_crypto": self.transactions_crypto,
        }
        STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self):
        if not STATE_FILE.exists():
            return
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        self.world = data.get("world", "trad")
        for name, ed in data.get("entities", {}).items():
            ent = Entity(name=ed["name"])
            # Support old state files that used assets/liabilities (trad only)
            ent.assets_trad = ed.get("assets_trad", ed.get("assets", []))
            ent.liabilities_trad = [l for l in ed.get("liabilities_trad", ed.get("liabilities", [])) if l["label"] != "equity"]
            ent.assets_crypto = ed.get("assets_crypto", [])
            ent.liabilities_crypto = [l for l in ed.get("liabilities_crypto", []) if l["label"] != "equity"]
            ent.currency = ed.get("currency")
            ent._world = self.world
            self.entities[name] = ent
        self.transactions_trad = data.get("transactions_trad", data.get("transactions", []))
        self.transactions_crypto = data.get("transactions_crypto", [])

    def create(self, name: str, reserves: float):
        if name in self.entities:
            raise ValueError(f"Entity '{name}' already exists.")
        if self.world == "crypto":
            raise ValueError("Use 'new' to create entities in crypto world. 'create' is trad-only (requires cash).")
        e = Entity(name=name)
        e._world = self.world
        if reserves > 0:
            e.assets_trad.append({"label": "cash", "amount": reserves, "counterparty": None})
        self.entities[name] = e
        self.save()
        return e

    def get(self, name: str) -> Entity:
        if name not in self.entities:
            raise ValueError(f"Entity '{name}' not found. Create it first.")
        return self.entities[name]

    # Labels that belong to trad world and should not carry over as tokens
    TRAD_ONLY_LABELS = {
        "cash", "equity", "loan-payable", "loan-receivable",
    }

    def _is_token(self, label: str) -> bool:
        """True if this label represents an issued token (not trad-world plumbing)."""
        if label in self.TRAD_ONLY_LABELS:
            return False
        if label.startswith("deposit-") or label.startswith("deposit@"):
            return False
        return True

    def _sync_tokens_to_crypto(self):
        """
        Mirror issued tokens from trad world onto crypto balance sheets.
        Called once when first switching to crypto.

        For each entity:
          - trad liabilities that are tokens → copy to crypto liabilities
          - trad assets that are tokens     → copy to crypto assets
        Existing crypto entries are left untouched (additive, no duplicates).
        """
        for entity in self.entities.values():
            # Collect existing crypto labels to avoid duplicates
            existing_liab_labels = {
                (e["label"], e.get("counterparty")) for e in entity.liabilities_crypto
            }
            existing_asset_labels = {
                (e["label"], e.get("counterparty")) for e in entity.assets_crypto
            }

            for entry in entity.liabilities_trad:
                if self._is_token(entry["label"]):
                    key = (entry["label"], entry.get("counterparty"))
                    if key not in existing_liab_labels:
                        entity.liabilities_crypto.append(dict(entry))

            for entry in entity.assets_trad:
                if self._is_token(entry["label"]):
                    # Strip counterparty — in crypto world tokens are bearer assets,
                    # not claims on a specific issuer
                    clean = {"label": entry["label"], "amount": entry["amount"], "counterparty": None}
                    key = (entry["label"], None)
                    if key not in existing_asset_labels:
                        entity.assets_crypto.append(clean)

    def switch_world(self) -> str:
        new_world = "crypto" if self.world == "trad" else "trad"
        if new_world == "crypto":
            self._sync_tokens_to_crypto()
        self._set_world(new_world)
        self.save()
        return new_world

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
        if self.world == "crypto":
            raise ValueError("No cash in crypto world. Use tokens to pay.")
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
        sender_cash["amount"] -= amount
        if sender_cash["amount"] == 0:
            s.assets.remove(sender_cash)
        r.add_asset("cash", amount)
        self.record_transaction(sender, receiver, "cash", amount, tx_type)
        self.save()

    def transfer_token(self, sender: str, receiver: str, token: str, amount: float, tx_type: str = "payment"):
        """Token transfer for crypto world — analogous to transfer_cash."""
        s = self.get(sender)
        r = self.get(receiver)
        sender_token = next((e for e in s.assets if e["label"] == token), None)
        if sender_token is None:
            raise ValueError(f"'{sender}' has no '{token}' asset.")
        if sender_token["amount"] < amount:
            raise ValueError(
                f"'{sender}' has insufficient {token}: "
                f"{sender_token['amount']:,.0f} available, {amount:,.0f} requested."
            )
        sender_token["amount"] -= amount
        if sender_token["amount"] == 0:
            s.assets.remove(sender_token)
        r.add_asset(token, amount)
        self.record_transaction(sender, receiver, token, amount, tx_type)
        self.save()

    def reset(self):
        self.entities = {}
        self.transactions_trad = []
        self.transactions_crypto = []
        self.world = "trad"
        if STATE_FILE.exists():
            STATE_FILE.unlink()