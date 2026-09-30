"""Receipt seal + bake-off tests."""

from __future__ import annotations

import json
from pathlib import Path

from behavioral_edge.profiles import HUSTLE
from behavioral_edge.receipts import (
    compare_receipts,
    issue_hustle_receipt,
    verify_seal,
    write_receipt,
)


def test_issue_and_verify_hustle_receipt(tmp_path: Path):
    receipt = issue_hustle_receipt(
        bars=160,
        seed=42,
        profile=HUSTLE,
        include_stress=False,
    )
    assert verify_seal(receipt)
    assert receipt["claims"]["our_pnl_per_day"] is not None
    path = write_receipt(receipt, tmp_path / "r.json")
    loaded = json.loads(path.read_text())
    assert verify_seal(loaded)


def test_tamper_breaks_seal(tmp_path: Path):
    receipt = issue_hustle_receipt(
        bars=160,
        seed=42,
        profile=HUSTLE,
        include_stress=False,
    )
    receipt["claims"]["our_pnl_per_day"] = 99999.0
    assert verify_seal(receipt) is False


def test_compare_flags_missing_methodology():
    ours = issue_hustle_receipt(
        bars=160,
        seed=42,
        profile=HUSTLE,
        include_stress=False,
    )
    theirs = {"name": "muse", "pnl_per_day": 100.0, "win_rate": 0.5}
    report = compare_receipts(ours, theirs)
    assert report["winner"] in {"behavioral_edge", "muse", "tie", "incomplete"}
    assert report["fair_fight"] is False
    assert any("methodology_missing" in f for f in report["methodology_flags"])
