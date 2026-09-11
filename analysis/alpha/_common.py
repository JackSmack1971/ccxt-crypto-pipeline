from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

def as_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return result.astimezone(UTC).replace(tzinfo=None) if result.tzinfo else result

def payload(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("payload_json", {})
    if isinstance(value, str):
        try: value = json.loads(value)
        except json.JSONDecodeError: return {}
    return value if isinstance(value, dict) else {}

def first(mapping: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = mapping.get(name)
        if value not in (None, ""): return value
    return None

def address_key(chain: str, address: str) -> str:
    return address.strip() if chain.lower() == "solana" else address.strip().lower()

def identity(chain: str, address: str) -> str:
    return f"{chain}:{address_key(chain, address)}"

def numeric(value: Any) -> float | None:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError): return None

def expected_count(start: datetime, end: datetime, timeframe: str) -> int:
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    if not timeframe or timeframe[-1] not in units: raise ValueError(f"unsupported timeframe: {timeframe}")
    interval = timedelta(seconds=int(timeframe[:-1]) * units[timeframe[-1]])
    return max(1, int((end - start) / interval) + 1)

def coverage_report(observations: tuple[Any, ...], start: datetime, end: datetime, timeframe: str) -> dict[str, Any]:
    """Measure interval coverage without filling missing observations."""
    if end < start: raise ValueError("coverage interval is reversed")
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    interval = timedelta(seconds=int(timeframe[:-1]) * units[timeframe[-1]])
    points = sorted({as_time(getattr(item, "timestamp", item)) for item in observations if start <= as_time(getattr(item, "timestamp", item)) <= end})
    expected = expected_count(start, end, timeframe)
    gaps = [max(timedelta(0), current - previous - interval) for previous, current in zip(points, points[1:])]
    missing_interval = max(gaps, default=(end - start + interval if not points else timedelta(0)))
    coverage = len(points) / expected
    return {"observed": len(points), "expected": expected, "coverage": coverage,
            "max_contiguous_missing_seconds": missing_interval.total_seconds(),
            "max_allowed_missing_seconds": (end - start).total_seconds() * .25,
            "passes": coverage >= .8 and missing_interval <= (end - start) * .25}
