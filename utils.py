import math
import re
import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def now_et() -> datetime.datetime:
    return datetime.datetime.now(tz=ET)


def et_time(hour: int, minute: int, second: int = 0) -> datetime.datetime:
    return now_et().replace(hour=hour, minute=minute, second=second, microsecond=0)


def calc_leg_qty(equity: float, margin_per_share: float) -> int:
    # spec: (ELV - 2%) / Sell SPY Initial Margin, floor
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
           for v in (equity, margin_per_share)):
        return 0
    return max(0, math.floor(equity * 0.98 / margin_per_share))


def parse_trading_hours(raw: str) -> list[tuple[datetime.datetime, datetime.datetime]]:
    today = now_et().strftime("%Y%m%d")
    sessions = []
    for seg in raw.split(";"):
        seg = seg.strip()
        if not seg.startswith(today + ":") or "CLOSED" in seg:
            continue
        m = re.fullmatch(r"(\d{8}):(\d{4})-(\d{8}):(\d{4})", seg)
        if not m:
            continue
        try:
            open_dt = datetime.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M").replace(tzinfo=ET)
            close_dt = datetime.datetime.strptime(m.group(3) + m.group(4), "%Y%m%d%H%M").replace(tzinfo=ET)
        except ValueError:
            continue
        if close_dt > open_dt:
            sessions.append((open_dt, close_dt))
    return sessions


def is_early_close(raw: str) -> bool:
    sessions = parse_trading_hours(raw)
    return not sessions or max(close for _, close in sessions) < et_time(16, 0)
