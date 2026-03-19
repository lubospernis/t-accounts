"""
ledger.py — T-account state for all entities.

Two worlds: "trad" (default) and "crypto".
  - trad:   cash-based, full T-accounts, currency-denominated
  - crypto: token-only, per-token net positions

Currency defaults to USD for all entities.

Token prices:
  - Stablecoins: tokenusd=1 USD, tokeneur=1 EUR (hardcoded)
  - Others: set via Ledger.token_prices dict, or `price` command
  - Trad world shows fiat value next to token quantities where a price is known
  - Crypto write-back: transfer_token also updates assets_trad so both worlds stay in sync
"""
import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

STATE_FILE = Path("taccounts_state.json")

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€"}
DEFAULT_CURRENCY = "USD"

TOKEN_EMOJI = {
    "tokenusd": "💵",
    "tokeneur": "💶",
    "tokenbtc": "₿",
    "tokeneth": "Ξ",
}
DEFAULT_TOKEN_EMOJI = "🪙"

# Stablecoin pegs: token → (fiat_amount, currency)
STABLECOIN_PEGS: dict[str, tuple[float, str]] = {
    "tokenusd": (1.0, "USD"),
    "tokeneur": (1.0, "EUR"),
}


def token_emoji(label: str) -> str:
    return TOKEN_EMOJI.get(label.lower(), DEFAULT_TOKEN_EMOJI)


def fmt_amount(amount: float, currency: Optional[str] = None, signed: bool = False,
               world: str = "trad", token_label: Optional[str] = None) -> str:
    """Format a number with optional currency symbol/token emoji and scale suffix.
    In crypto world, currency symbols are suppressed — only token emojis apply."""
    if world == "crypto":
        symbol = (token_emoji(token_label) + " ") if token_label else ""
    else:
        symbol = CURRENCY_SYMBOLS.get(currency or DEFAULT_CURRENCY, "")

    abs_amount = abs(amount)
    neg = amount < 0

    if abs_amount >= 1_000_000_000:
        scaled = f"{abs_amount / 1_000_000_000:.2f}".rstrip("0").rstrip(".")
        text = f"{symbol}{scaled}B"
    elif abs_amount >= 1_000_000:
        scaled = f"{abs_amount / 1_000_000:.2f}".rstrip("0").rstrip(".")
        text = f"{symbol}{scaled}M"
    else:
        if abs_amount != int(abs_amount):
            # Show up to 2 decimal places, strip trailing zeros
            text = f"{symbol}{abs_amount:,.2f}".rstrip("0").rstrip(".")
        else:
            text = f"{symbol}{abs_amount:,.0f}"

    if neg:
        return "-" + text
    if signed:
        return "+" + text
    return text


def generate_address() -> str:
    """Generate a short random wallet address."""
    return "0x" + str(uuid.uuid4()).replace("-", "")[:8]


@dataclass
class Entity:
    name: str
    assets_trad: list = field(default_factory=list)
    liabilities_trad: list = field(default_factory=list)
    assets_crypto: list = field(default_factory=list)
    liabilities_crypto: list = field(default_factory=list)
    currency: str = DEFAULT_CURRENCY  # always set, defaults to USD
    address: Optional[str] = None     # crypto address; None = no crypto presence

    _world: str = field(default="trad", repr=False)

    @property
    def has_address(self) -> bool:
        return self.address is not None

    FUNGIBLE_TRAD = {"cash"}

    @property
    def FUNGIBLE(self):
        if self._world == "crypto":
            return None
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
        lst = self.assets
        fungible = self.FUNGIBLE
        is_fungible = (fungible is None and not label.startswith("deposit@")) or \
                      (fungible is not None and label in fungible)
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

    # Labels whose liabilities track individual counterparties (not aggregated)
    COUNTERPARTY_LIABILITIES = {"deposit-", "loan-payable", "loan-receivable"}

    def _is_token_liability(self, label: str) -> bool:
        """Token liabilities aggregate — the issuer tracks total supply, not individual holders."""
        if label in ("equity", "cash"):
            return False
        if any(label.startswith(p) for p in ("deposit-", "deposit@")):
            return False
        if label in ("loan-payable", "loan-receivable"):
            return False
        return True

    # ── liability helpers ────────────────────────────────────────────────────

    def add_liability(self, label: str, amount: float, counterparty=None):
        if label == "equity":
            return
        lst = self.liabilities
        # Token liabilities aggregate regardless of counterparty (total supply model)
        is_token = self._is_token_liability(label)
        for e in lst:
            if e["label"] == label and (is_token or e.get("counterparty") == counterparty):
                e["amount"] += amount
                return
        # Store counterparty only for non-token liabilities
        cp = None if is_token else counterparty
        lst.append({"label": label, "amount": amount, "counterparty": cp})

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
        # token_prices: {token_label: (price_per_token, currency)}
        # Stablecoin pegs are always applied; this dict holds manual overrides
        self.token_prices: dict[str, tuple[float, str]] = {}
        # fx_rates: {"EURUSD": 1.08} means 1 EUR = 1.08 USD
        self.fx_rates: dict[str, float] = {}
        self.load()

    @property
    def transactions(self) -> list:
        return self.transactions_crypto if self.world == "crypto" else self.transactions_trad

    def _set_world(self, world: str):
        self.world = world
        for e in self.entities.values():
            e._world = world

    def token_fiat_value(self, token: str, quantity: float, entity_currency: str) -> Optional[float]:
        """
        Return the fiat value of `quantity` tokens in the entity's currency.
        Uses FX rates for cross-currency conversion (e.g. EUR entity holding tokenusd).
        Priority: manual token_prices > stablecoin pegs.
        Returns None if no price or FX rate is known.
        """
        def convert(value_usd_equiv: float, from_ccy: str, to_ccy: str) -> Optional[float]:
            """Convert fiat value between currencies using stored FX rates."""
            if from_ccy == to_ccy:
                return value_usd_equiv
            pair = from_ccy + to_ccy   # e.g. USDEUR
            pair_inv = to_ccy + from_ccy  # e.g. EURUSD
            if pair in self.fx_rates:
                return value_usd_equiv * self.fx_rates[pair]
            if pair_inv in self.fx_rates:
                return value_usd_equiv / self.fx_rates[pair_inv]
            return None

        # Manual price override
        if token in self.token_prices:
            price, price_currency = self.token_prices[token]
            value_in_price_ccy = quantity * price
            return convert(value_in_price_ccy, price_currency, entity_currency)

        # Stablecoin peg
        if token in STABLECOIN_PEGS:
            peg_price, peg_currency = STABLECOIN_PEGS[token]
            value_in_peg_ccy = quantity * peg_price
            return convert(value_in_peg_ccy, peg_currency, entity_currency)

        return None

    def set_token_price(self, token: str, price: float, currency: str):
        """Set or update the fiat price of a token."""
        self.token_prices[token] = (price, currency)
        self.save()

    def set_fx_rate(self, pair: str, rate: float):
        """Set an FX rate. pair e.g. 'EURUSD' means 1 EUR = rate USD."""
        self.fx_rates[pair.upper()] = rate
        self.save()

    def save(self):
        data = {
            "world": self.world,
            "token_prices": {k: list(v) for k, v in self.token_prices.items()},
            "entities": {
                name: {
                    "name": e.name,
                    "assets_trad": e.assets_trad,
                    "liabilities_trad": [l for l in e.liabilities_trad if l["label"] != "equity"],
                    "assets_crypto": e.assets_crypto,
                    "liabilities_crypto": [l for l in e.liabilities_crypto if l["label"] != "equity"],
                    "currency": e.currency,
                    "address": e.address,
                }
                for name, e in self.entities.items()
            },
            "transactions_trad": self.transactions_trad,
            "transactions_crypto": self.transactions_crypto,
            "fx_rates": self.fx_rates,
        }
        STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self):
        if not STATE_FILE.exists():
            return
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        self.world = data.get("world", "trad")
        raw_prices = data.get("token_prices", {})
        self.token_prices = {k: tuple(v) for k, v in raw_prices.items()}
        for name, ed in data.get("entities", {}).items():
            ent = Entity(name=ed["name"])
            ent.assets_trad = ed.get("assets_trad", ed.get("assets", []))
            ent.liabilities_trad = [l for l in ed.get("liabilities_trad", ed.get("liabilities", [])) if l["label"] != "equity"]
            ent.assets_crypto = ed.get("assets_crypto", [])
            ent.liabilities_crypto = [l for l in ed.get("liabilities_crypto", []) if l["label"] != "equity"]
            ent.currency = ed.get("currency", DEFAULT_CURRENCY)
            ent.address = ed.get("address")
            ent._world = self.world
            self.entities[name] = ent
        self.transactions_trad = data.get("transactions_trad", data.get("transactions", []))
        self.transactions_crypto = data.get("transactions_crypto", [])
        self.fx_rates = data.get("fx_rates", {})

    def create(self, name: str, reserves: float, currency: str = DEFAULT_CURRENCY,
               with_address: bool = False):
        if name in self.entities:
            raise ValueError(f"Entity '{name}' already exists.")
        if self.world == "crypto":
            raise ValueError("Use 'new' to create entities in crypto world. 'create' is trad-only.")
        e = Entity(name=name, currency=currency)
        e.address = generate_address() if with_address else None
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

    TRAD_ONLY_LABELS = {"cash", "equity", "loan-payable", "loan-receivable"}

    def _is_token(self, label: str) -> bool:
        if label in self.TRAD_ONLY_LABELS:
            return False
        if label.startswith("deposit-") or label.startswith("deposit@"):
            return False
        return True

    def _sync_tokens_to_crypto(self):
        """Mirror issued tokens from trad onto crypto sheets on first worldswitch."""
        for entity in self.entities.values():
            existing_liab = {(e["label"], e.get("counterparty")) for e in entity.liabilities_crypto}
            existing_asset = {(e["label"], e.get("counterparty")) for e in entity.assets_crypto}

            for entry in entity.liabilities_trad:
                if self._is_token(entry["label"]):
                    key = (entry["label"], entry.get("counterparty"))
                    if key not in existing_liab:
                        entity.liabilities_crypto.append(dict(entry))

            for entry in entity.assets_trad:
                if self._is_token(entry["label"]):
                    # Bearer assets: strip counterparty in crypto world
                    clean = {"label": entry["label"], "amount": entry["amount"], "counterparty": None}
                    if (entry["label"], None) not in existing_asset:
                        entity.assets_crypto.append(clean)

    def _writeback_token_to_trad(self, entity_name: str, token: str, delta: float):
        """
        After a crypto token transfer, update the corresponding trad asset entry.
        Skipped for entities with no address (not crypto-visible) or crypto-native entities
        that have no meaningful trad balance sheet.
        delta > 0 = received tokens, delta < 0 = sent tokens.
        """
        entity = self.get(entity_name)
        # Only write back if entity exists in trad world (has a currency denomination)
        if not entity.has_address:
            return
        entry = next((e for e in entity.assets_trad if e["label"] == token), None)

        if delta > 0:
            if entry:
                entry["amount"] += delta
            else:
                # New token asset in trad world — no counterparty (bearer)
                entity.assets_trad.append({"label": token, "amount": delta, "counterparty": None})
        else:
            if entry:
                entry["amount"] += delta  # delta is negative
                if entry["amount"] <= 0:
                    entity.assets_trad.remove(entry)

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

    def settle(self, sender: str, receiver: str, amount: float,
               tx_type: str = "payment", is_payment: bool = True) -> str:
        """
        Trad world settlement: intrabank deposit swap or direct cash transfer.
        Returns "intrabank" or "cash" to indicate which path was used.
        is_payment=True records the flow in the graph (genuine payments only).
        is_payment=False for operational flows: deposits, withdrawals, redemptions.
        Raises ValueError on any validation failure.
        """
        if self.world == "crypto":
            raise ValueError("settle() is for trad world only.")
        s = self.get(sender)
        r = self.get(receiver)

        # Check for shared deposit institution
        sender_deposits = {
            e["label"].removeprefix("deposit@"): e
            for e in s.assets_trad if e["label"].startswith("deposit@")
        }
        receiver_deposits = {
            e["label"].removeprefix("deposit@"): e
            for e in r.assets_trad if e["label"].startswith("deposit@")
        }
        shared = set(sender_deposits) & set(receiver_deposits)
        intrabank = next(
            (bank for bank in shared if sender_deposits[bank]["amount"] >= amount),
            None
        )

        if intrabank:
            bank_entity = self.get(intrabank)
            sd = sender_deposits[intrabank]
            sd["amount"] -= amount
            if sd["amount"] == 0:
                s.assets_trad.remove(sd)
            receiver_deposits[intrabank]["amount"] += amount
            dep_sender = next((e for e in bank_entity.liabilities_trad if e["label"] == f"deposit-{sender}"), None)
            dep_receiver = next((e for e in bank_entity.liabilities_trad if e["label"] == f"deposit-{receiver}"), None)
            if dep_sender:
                dep_sender["amount"] -= amount
                if dep_sender["amount"] == 0:
                    bank_entity.liabilities_trad.remove(dep_sender)
            if dep_receiver:
                dep_receiver["amount"] += amount
            self.save()
            return "intrabank"
        else:
            self.transfer_cash(sender, receiver, amount, tx_type=tx_type, record=is_payment)
            return "cash"

    def transfer_cash(self, sender: str, receiver: str, amount: float,
                       tx_type: str = "payment", record: bool = True):
        """
        Move cash between two entities.
        record=True only for genuine payments (direct cash between parties).
        record=False for operational flows: deposits, withdrawals, redemptions —
        these are balance sheet restructurings, not payments.
        """
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
        if record:
            self.record_transaction(sender, receiver, "cash", amount, tx_type)
        self.save()

    def transfer_token(self, sender: str, receiver: str, token: str, amount: float, tx_type: str = "payment"):
        """
        Token transfer. Updates crypto sheets and writes back to trad sheets
        so both worlds stay in sync.
        """
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

        # Update crypto sheets
        sender_token["amount"] -= amount
        if sender_token["amount"] == 0:
            s.assets.remove(sender_token)
        r.add_asset(token, amount)

        # Write back to trad sheets
        self._writeback_token_to_trad(sender, token, -amount)
        self._writeback_token_to_trad(receiver, token, +amount)

        self.record_transaction(sender, receiver, token, amount, tx_type)
        self.save()

    def reset(self):
        self.entities = {}
        self.transactions_trad = []
        self.transactions_crypto = []
        self.token_prices = {}
        self.world = "trad"
        if STATE_FILE.exists():
            STATE_FILE.unlink()