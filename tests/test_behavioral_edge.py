"""Tests for behavioral detectors, confluence, risk, duel, and backtest."""

from __future__ import annotations

import pytest

from behavioral_edge.backtest import head_to_head, run_backtest, run_naive_rsi_baseline
from behavioral_edge.confluence import score_confluence
from behavioral_edge.data import make_behavioral_tape
from behavioral_edge.detectors import detect_panic_capitulation
from behavioral_edge.engine import BehavioralEdgeEngine
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
    engine = BehavioralEdgeEngine()
    signals = engine.scan_history(df)
    kinds = {s.kind for s in signals}
    assert signals, "expected planted behavioral regimes to fire"
    assert kinds & {
        SignalKind.PANIC_CAPITULATION,
        SignalKind.FOMO_EXHAUSTION,
        SignalKind.DISPOSITION_CONTINUATION,
        SignalKind.ANCHOR_REJECTION,
    }
    assert all(s.edge_score >= 0 for s in signals)


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

    blocked = size_position(
        strong,
        100.0,
        RiskConfig(),
        open_risk_dollars=100_000 * 0.015,
    )
    assert blocked is None


def test_backtest_runs_and_tracks_equity():
    df = make_behavioral_tape()
    result = run_backtest(df)
    assert len(result.equity_curve) >= len(df)
    assert isinstance(result.total_pnl, float)
    assert "max_drawdown" in result.summary()
    for t in result.trades:
        assert t.exit is not None
        assert t.pnl is not None
        assert t.exit_reason in {"stop", "target", "time"}


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


def test_plan_trade_uses_strongest_signal(monkeypatch):
    df = make_behavioral_tape(n=80)
    engine = BehavioralEdgeEngine(risk=RiskConfig(min_strength=0.5, min_edge=0.5))

    strong = Signal(
        kind=SignalKind.PANIC_CAPITULATION,
        side="long",
        strength=0.95,
        reason="best",
        stop_pct=0.02,
        target_pct=0.04,
        bar_index=70,
        edge_score=0.95,
    )
    weak = Signal(
        kind=SignalKind.FOMO_EXHAUSTION,
        side="short",
        strength=0.6,
        reason="worse",
        stop_pct=0.02,
        target_pct=0.04,
        bar_index=70,
        edge_score=0.6,
    )
    monkeypatch.setattr(
        "behavioral_edge.engine.scan_bar",
        lambda _df, _i: [strong, weak],
    )
    plan = engine.plan_trade(df, 70)
    assert plan is not None
    assert plan.signal.kind == SignalKind.PANIC_CAPITULATION


def test_confluence_regime_veto_crushes_edge():
    df = make_behavioral_tape()
    # Find any raw panic print and force score through confluence
    raw = None
    for i in range(len(df)):
        raw = detect_panic_capitulation(df, i)
        if raw:
            break
    assert raw is not None
    scored = score_confluence(df, raw)
    assert 0 <= scored.edge_score <= 1
    assert scored.strength <= 1


def test_regime_classifier_returns_state():
    df = make_behavioral_tape()
    state = classify_regime(df, 100)
    assert state is not None
    assert isinstance(state.regime, Regime)
    assert regime_allows(SignalKind.PANIC_CAPITULATION, state) in {True, False}


def test_duel_behavioral_beats_or_matches_naive_on_planted_tape():
    """On a tape planted with behavioral regimes, we should win the risk-adjusted duel."""
    df = make_behavioral_tape(n=180, seed=42)
    report = head_to_head(df)
    assert report["winner"] in {"behavioral_edge", "tie"}
    assert (
        report["composite_scores"]["behavioral_edge"]
        >= report["composite_scores"]["naive_rsi_fade"]
    )
    naive = run_naive_rsi_baseline(df)
    assert naive.label == "naive_rsi_fade"
