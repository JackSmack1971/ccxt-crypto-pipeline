#!/usr/bin/env python3
"""Validate the syntax of this pipeline's canonical crypto identities.

Shapes:
  CEX: exchange:symbol
  DEX/on-chain: chain:address-or-source-identifier

Supported-chain membership belongs in repository config, not this helper.  When an
address family is known, request strict family validation instead of guessing from
an arbitrary chain slug.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_EVM_ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BASE58 = frozenset("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
_KNOWN_EVM = frozenset({"ethereum", "base", "arbitrum", "bsc", "optimism", "avalanche"})


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str


def _clean_component(value: str, label: str) -> ValidationResult:
    if not value:
        return ValidationResult(False, f"empty {label}")
    if value != value.strip():
        return ValidationResult(False, f"{label} has leading/trailing whitespace")
    if any(ord(ch) < 32 or ch.isspace() for ch in value):
        return ValidationResult(False, f"{label} contains whitespace/control characters")
    return ValidationResult(True, "ok")


def _validate_solana_address(value: str) -> ValidationResult:
    if not 32 <= len(value) <= 44:
        return ValidationResult(False, f"solana address length {len(value)} is outside 32..44")
    if any(ch not in _BASE58 for ch in value):
        return ValidationResult(False, "solana address contains non-base58 characters")

    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for ch in value:
        n = n * 58 + alphabet.index(ch)
    payload = b"" if n == 0 else n.to_bytes((n.bit_length() + 7) // 8, "big")
    leading_zeroes = len(value) - len(value.lstrip("1"))
    decoded = b"\x00" * leading_zeroes + payload
    if len(decoded) != 32:
        return ValidationResult(False, f"solana address decodes to {len(decoded)} bytes, expected 32")
    return ValidationResult(True, "ok")


def validate_canonical_id(
    canonical_id: str,
    source_type: str,
    address_family: str = "auto",
) -> tuple[bool, str]:
    """Return ``(is_valid, reason)``.

    ``address_family`` may be ``auto``, ``evm``, ``solana``, or ``opaque``.
    ``auto`` applies strict validation only to researched well-known EVM chain
    slugs and ``solana``; unknown chain slugs remain syntactically validated so
    the helper does not contradict repository-configured multi-chain support.
    """
    if not isinstance(canonical_id, str):
        return False, "canonical_id must be a string"
    if source_type not in {"cex", "dex"}:
        return False, f"unknown source_type: {source_type!r} (expected 'cex' or 'dex')"
    if address_family not in {"auto", "evm", "solana", "opaque"}:
        return False, "address_family must be auto, evm, solana, or opaque"
    if ":" not in canonical_id:
        return False, "missing ':' separator"

    prefix, rest = canonical_id.split(":", 1)
    prefix_check = _clean_component(prefix, "prefix")
    if not prefix_check.ok:
        return False, prefix_check.reason
    if not _PREFIX.fullmatch(prefix):
        return False, "prefix must be letters/digits with optional . _ - separators"

    rest_check = _clean_component(rest, "suffix")
    if not rest_check.ok:
        return False, rest_check.reason

    if source_type == "cex":
        # CCXT symbols may include '/', '-', ':', settlement suffixes, or other
        # exchange-defined punctuation.  The local canonical contract is the
        # exchange prefix + non-whitespace symbol; pinned CCXT/exchange metadata
        # is authoritative for whether a specific symbol exists.
        return True, "ok"

    family = address_family
    prefix_key = prefix.lower()
    if family == "auto":
        if prefix_key == "solana":
            family = "solana"
        elif prefix_key in _KNOWN_EVM:
            family = "evm"
        else:
            family = "opaque"

    if family == "evm":
        if not _EVM_ADDR.fullmatch(rest):
            return False, "not a 20-byte 0x-prefixed EVM address"
    elif family == "solana":
        result = _validate_solana_address(rest)
        if not result.ok:
            return False, result.reason
    # opaque: syntax only; chain-specific address validity must come from the
    # repository's configured chain adapter/provider contract.

    return True, "ok"


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("canonical_id")
    parser.add_argument("source_type", choices=("cex", "dex"))
    parser.add_argument(
        "--address-family",
        choices=("auto", "evm", "solana", "opaque"),
        default="auto",
        help="strict DEX address family; auto only recognizes researched common chains",
    )
    args = parser.parse_args()
    ok, reason = validate_canonical_id(args.canonical_id, args.source_type, args.address_family)
    print(f"{'VALID' if ok else 'INVALID'}: {reason}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_main())
