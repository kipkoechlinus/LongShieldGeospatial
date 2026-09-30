"""Tests for behavioral detectors, confluence, high-win profile, duel."""

from __future__ import annotations

import pytest

from behavioral_edge.backtest import head_to_head, run_backtest, run_naive_rsi_baseline
from behavioral_edge.confluence import score_confluence
from behavioral_edge.data import make_behavioral_tape
from behavioral_edge.detectors import detect_panic_capitulation
from behavioral_edge.engine import BehavioralEdgeEngine
from behavioral_edge.profiles import BALANCED, HIGH_WIN, apply_profile
from behavioral_edge.regime import Regime, classify_regime, regime_allows
from behavioral_edge.risk import RiskConfig, size_position
from behavioral_edge.signals import Signal, SignalKind


def test_synthetic_tape_shape():
    df = make_behavioral_tape(n=120, seed=1)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 120
    assert (df["high"] >= df["low"]).all()


def test_scan_finds_behavioral_signals():
    df = make_behavioral_tape()
    engine = BehavioralEdgeEngine(profile=BALANCED)
    signals = engine.scan_history(df)
    kinds = {s.kind for s in signals}
    assert signals, "expected planted behavioral regimes to fire"
    assert kinds & {
        SignalKind.PANIC_CAPITULATION,
        SignalKind.FOMO_EXHAUSTION,
        SignalKind.DISPOSITION_CONTINUATION,
        SignalKind.ANCHOR_REJECTION,
    }


def test_high_win_tightens_targets_for_early_bank():
    weak = Signal(
        kind=SignalKind.ANCHOR_REJECTION,
        side="long",
        strength=0.5,
        reason="weak",
        stop_pct=0.02,
        target_pct=0.04,
        bar_index=10,
        confluence=0.05,
        edge_score=0.5,
    )
    assert apply_profile(weak, HIGH_WIN) is None

    anchor = Signal(
        kind=SignalKind.ANCHOR_REJECTION,
        side="long",
        strength=0.7,
        reason="trap",
        stop_pct=0.02,
        target_pct=0.04,
        bar_index=10,
        confluence=0.4,
        edge_score=0.7,
    )
    shaped = apply_profile(anchor, HIGH_WIN)
    assert shaped is not None
    assert shaped.target_pct < anchor.target_pct
    assert shaped.target_pct <= shaped.stop_pct * 0.7


def test_risk_rejects_weak_and_caps_exposure():
    sig = Signal(
        kind=SignalKind.PANIC_CAPITULATION,
        side="long",
        strength=0.4,
        reason="weak",
        stop_pct=0.02,
        target_pct=0.04,
        bar_index=10,
        edge_score=0.4,
    )
    assert size_position(sig, 100.0, RiskConfig()) is None

    strong = Signal(
        kind=SignalKind.FOMO_EXHAUSTION,
        side="short",
        strength=0.9,
        reason="strong",
        stop_pct=0.02,
        target_pct=0.04,
        bar_index=10,
        edge_score=0.9,
    )
    plan = size_position(strong, 100.0, RiskConfig(account_equity=100_000))
    assert plan is not None
    assert plan.risk_dollars <= 100_000 * 0.005 * 1.35


def test_backtest_runs_and_tracks_equity():
    df = make_behavioral_tape()
    result = run_backtest(
        df,
        engine=BehavioralEdgeEngine(profile=HIGH_WIN),
    )
    assert len(result.equity_curve) >= len(df)
    for t in result.trades:
        assert t.exit_reason in {"stop", "target", "time", "scalp"}


def test_high_win_rate_beats_balanced_on_planted_tape():
    df = make_behavioral_tape(n=220, seed=42)
    high = run_backtest(df, engine=BehavioralEdgeEngine(profile=HIGH_WIN))
    bal = run_backtest(df, engine=BehavioralEdgeEngine(profile=BALANCED))
    assert high.trades, "high_win should still take trades"
    # Primary ask: higher win rate when banking early (scratches excluded)
    assert high.win_rate >= bal.win_rate
    assert high.win_rate >= 0.75


def test_signal_validate():
    bad = Signal(
        kind=SignalKind.ANCHOR_REJECTION,
        side="flat",
        strength=0.5,
        reason="x",
        stop_pct=0.02,
        target_pct=0.04,
        bar_index=1,
    )
    with pytest.raises(ValueError):
        bad.validate()


def test_confluence_and_regime():
    df = make_behavioral_tape()
    raw = None
    for i in range(len(df)):
        raw = detect_panic_capitulation(df, i)
        if raw:
            break
    assert raw is not None
    scored = score_confluence(df, raw)
    assert 0 <= scored.edge_score <= 1
    state = classify_regime(df, 100)
    assert state is not None
    assert isinstance(state.regime, Regime)
    assert regime_allows(SignalKind.PANIC_CAPITULATION, state) in {True, False}


def test_duel_high_win_wins_composite():
    df = make_behavioral_tape(n=180, seed=42)
    report = head_to_head(df, profile=HIGH_WIN)
    assert "behavioral_edge" in report["winner"] or report["winner"] == "tie"
    naive = run_naive_rsi_baseline(df)
    assert naive.label == "naive_rsi_fade"
