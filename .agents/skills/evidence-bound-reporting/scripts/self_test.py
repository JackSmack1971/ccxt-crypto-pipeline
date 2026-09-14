#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import reporting_guard as guard


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def build_good(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    reporting = repo / "reporting"
    reporting.mkdir(parents=True)
    (reporting / "safe.py").write_text("import json\n", encoding="utf-8")

    package = root / "package"
    charts = package / "charts"
    charts.mkdir(parents=True)
    article = b"# Result\n\nObserved return was 1.5%.\n"
    claims = json.dumps([{"id": "r", "kind": "fact", "text": "Observed return was 1.5%.",
                          "evidence": [{"artifact": "results", "row": 0}]}], sort_keys=True).encode()
    svg = ("<svg xmlns=\"http://www.w3.org/2000/svg\" role=\"img\"><title>r</title>"
           "<desc>Return. Source: fixture</desc><text>percent · fixture</text></svg>").encode()
    review = json.dumps({"status": "pending", "approval_required": True}, sort_keys=True).encode()
    files = {"article.md": article, "claim-ledger.json": claims, "charts/r.svg": svg, "review.json": review}
    for name, content in files.items():
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest = {"immutable": True, "review_status": "pending",
                "validation": {"claims": "passed", "charts": "passed", "accessibility": "passed"},
                "artifacts": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
    write_json(package / "package-manifest.json", manifest)
    return repo, package


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        repo, package = build_good(root)
        assert guard.check_reporting_imports(repo) == []
        assert guard.check_package(package) == []
        assert guard.check_claim_ledger_shape(package) == []

        (repo / "reporting" / "bad.py").write_text("import requests\n", encoding="utf-8")
        assert any("forbidden" in item for item in guard.check_reporting_imports(repo))
        (repo / "reporting" / "bad.py").unlink()

        review = package / "review.json"
        write_json(review, {"status": "approved", "approval_required": False})
        assert any("review.json" in item for item in guard.check_package(package))

        # Rebuild then prove checksum and secret checks fail independently.
        repo, package = build_good(root / "second")
        (package / "article.md").write_text("api_key=" + "sk-" + "1234567890abcdef\n", encoding="utf-8")
        failures = guard.check_package(package)
        assert any("checksum mismatch" in item for item in failures)
        assert any("secret" in item for item in failures)

    print("PASS: reporting_guard self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
