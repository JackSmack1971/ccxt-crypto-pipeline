#!/usr/bin/env python3
"""Deterministically check researched crypto provider capability routes.

This helper is a guardrail, not a live documentation client.  It reads the
September 2026 snapshot in references/provider-capabilities.json and refuses to
turn unresolved research into a production-safe claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REGISTRY = Path(__file__).resolve().parents[1] / "references" / "provider-capabilities.json"


def load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("providers"), dict) or not data["providers"]:
        raise ValueError("registry has no providers object")
    return data


def check_route(provider: str, capability: str, chain: str | None, free_only: bool) -> tuple[bool, str]:
    data = load_registry()
    providers = data["providers"]
    if provider not in providers:
        return False, f"provider {provider!r} is not in the researched snapshot"
    spec = providers[provider]

    if capability in spec.get("forbidden_capabilities", []):
        return False, f"{provider} explicitly does not provide {capability} in this snapshot"
    if capability not in spec.get("capabilities", []):
        return False, f"{provider} capability {capability!r} is not supported by this snapshot"

    explicit_chains = spec.get("chains")
    if explicit_chains is not None:
        if not chain:
            return False, f"{provider} capability check requires --chain"
        if chain not in explicit_chains:
            return False, f"{provider} is not researched for chain {chain!r}"

    if free_only:
        overrides = spec.get("free_capability_overrides")
        if overrides is not None:
            if not chain:
                return False, f"{provider} free-tier capability check requires --chain"
            allowed = overrides.get(chain)
            if allowed is None:
                return False, f"free-tier status for {provider}/{chain} is not established by this snapshot"
            if capability not in allowed:
                return False, f"{provider} {capability} is not researched as free on {chain}"

    if spec.get("verification_required"):
        return False, (
            f"route is research-candidate only: {provider} requires current official verification before "
            f"production use. {spec.get('notes', '')}"
        )

    return True, f"allowed by {data.get('snapshot', 'unknown')} snapshot: {provider} -> {capability}"


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="check one provider/capability/chain route")
    check.add_argument("--provider", required=True)
    check.add_argument("--capability", required=True)
    check.add_argument("--chain")
    check.add_argument("--free-only", action="store_true")

    ls = sub.add_parser("list", help="list researched providers and capabilities")
    ls.add_argument("--provider")

    args = parser.parse_args()
    if args.command == "check":
        ok, reason = check_route(args.provider, args.capability, args.chain, args.free_only)
        print(f"{'ALLOW' if ok else 'BLOCK'}: {reason}")
        return 0 if ok else 1

    data = load_registry()
    providers = data["providers"]
    if args.provider:
        if args.provider not in providers:
            print(f"unknown provider: {args.provider}", file=sys.stderr)
            return 2
        print(json.dumps({args.provider: providers[args.provider]}, indent=2, sort_keys=True))
    else:
        for name, spec in sorted(providers.items()):
            print(f"{name}: {', '.join(spec.get('capabilities', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
