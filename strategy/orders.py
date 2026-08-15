from dataclasses import dataclass
import math
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum, auto

from ibapi.order import Order


class Side(Enum):
    FLAT = auto()
    LONG = auto()
    SHORT = auto()


@dataclass
class OrderGroup:
    parent_id: int
    child_id: int
    side: Side
    qty: int
    entry_price: float = 0.0
    filled: bool = False
    cancelled: bool = False
    parent_filled: bool = False


_ACCOUNT = ""


def set_account(account: str):
    """Target account for all orders — required when the login has >1 account."""
    global _ACCOUNT
    _ACCOUNT = account


def _base(action: str, qty: int, transmit: bool) -> Order:
    if action not in ("BUY", "SELL"):
        raise ValueError("order action must be BUY or SELL")
    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        raise ValueError("share quantity must be a positive integer")
    o = Order()
    o.action = action
    o.totalQuantity = qty
    o.transmit = transmit
    o.tif = "DAY"
    o.eTradeOnly = False
    o.firmQuoteOnly = False
    o.sweepToFill = True
    o.overridePercentageConstraints = True
    if _ACCOUNT:
        o.account = _ACCOUNT
    return o


def stp(action: str, qty: int, stop_px: float, transmit: bool, parent_id: int = 0) -> Order:
    if not isinstance(stop_px, (int, float)) or not math.isfinite(stop_px) or stop_px <= 0:
        raise ValueError("stop price must be positive and finite")
    rounded = float(Decimal(str(stop_px)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if rounded <= 0:
        raise ValueError("stop price rounds below the minimum tick")
    o = _base(action, qty, transmit)
    o.orderType = "STP"
    o.auxPrice = rounded
    if parent_id:
        o.parentId = parent_id
    return o


def mkt(action: str, qty: int, parent_id: int, transmit: bool) -> Order:
    o = _base(action, qty, transmit)
    o.orderType = "MKT"
    o.parentId = parent_id
    return o
