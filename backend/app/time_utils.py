"""
Centralized timezone handling for Boiler Pickup.
All user-facing times are in Eastern Time (America/New_York — EST/EDT).
Storage remains UTC for consistency; conversion happens at API boundaries.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")


def now_est() -> datetime:
    """Current time in Eastern (West Lafayette)."""
    return datetime.now(timezone.utc).astimezone(EST)


def to_est(dt: datetime | None) -> datetime | None:
    """Convert datetime to Eastern. Naive UTC assumed if no tzinfo."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(EST)


def to_utc(dt: datetime) -> datetime:
    """Convert to UTC for storage. Accepts EST or naive (assumed EST)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=EST)
    return dt.astimezone(timezone.utc)


def to_est_isoformat(dt: datetime | None) -> str | None:
    """Serialize datetime as Eastern ISO string for API (e.g. 2025-02-25T14:00:00-05:00)."""
    if dt is None:
        return None
    est_dt = to_est(dt)
    z = est_dt.strftime("%z")
    return est_dt.strftime("%Y-%m-%dT%H:%M:%S") + (z[:3] + ":" + z[3:] if z else "")
