#!/usr/bin/env python3
"""Offline deterministic self-test for crypto-ingestion-source helper scripts."""
from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from provider_policy import check_route, load_registry  # noqa: E402
from validate_canonical_id import validate_canonical_id  # noqa: E402


def expect(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> int:
    cases = [
        ("kraken:BTC/USDT", "cex", "auto", True),
        ("binance:BTC/USDT:USDT", "cex", "auto", True),
        ("Kraken:BTC/USDT", "cex", "auto", True),
        ("kraken exchange:BTC/USDT", "cex", "auto", False),
        ("kraken:BAD SYMBOL/USDT", "cex", "auto", False),
        ("base:0x" + "a" * 40, "dex", "auto", True),
        ("base:0x123", "dex", "auto", False),
        ("solana:11111111111111111111111111111111", "dex", "auto", True),
        ("solana:00000000000000000000000000000000", "dex", "auto", False),
        ("sui:0x2::coin::TOKEN", "dex", "auto", True),
        ("sui:bad value", "dex", "auto", False),
    ]
    for cid, source_type, family, expected in cases:
        got, reason = validate_canonical_id(cid, source_type, family)
        expect(got == expected, f"canonical case {cid!r}: expected {expected}, got {got} ({reason})")

    route_cases = [
        (("geckoterminal", "ohlcv", "base", False), True),
        (("dexscreener", "ohlcv", "base", False), False),
        (("etherscan_v2", "token_holders", "base", True), False),
        (("etherscan_v2", "contract_source", "base", True), True),
        (("honeypot_is", "risk_screen", "solana", False), False),
        (("helius", "das", "solana", False), True),
        (("helius", "das", None, False), False),
        (("routescan", "token_holders", "base", False), False),
        (("bsctrace_meganode", "token_holders", "bsc", False), False),
    ]
    for args, expected in route_cases:
        got, reason = check_route(*args)
        expect(got == expected, f"provider case {args}: expected {expected}, got {got} ({reason})")

    registry = load_registry()
    expect(registry.get("snapshot") == "2026-09", "registry snapshot must be 2026-09")
    expect(len(registry["providers"]) >= 9, "expected researched provider set")

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    expect(skill.startswith("---\nname: crypto-ingestion-source\n"), "SKILL.md frontmatter/name malformed")
    for ref in ("tier0-aggregators.md", "evm-tier1.md", "solana-tier2.md", "provider-capabilities.json"):
        expect((ROOT / "references" / ref).is_file(), f"missing reference {ref}")

    # JSON round-trip catches malformed registry edits.
    json.dumps(registry, sort_keys=True)
    print(f"PASS: {len(cases)} canonical cases, {len(route_cases)} provider cases, package structure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
