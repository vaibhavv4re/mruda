"""MRUDA — Fatigue Engine.

Detects ad fatigue based on:
- Frequency > threshold
- CTR declining
- CPC rising
"""

from typing import List
from collections import defaultdict

from sqlmodel import Session, select

from app.models.normalized_models import NormalizedMetric
from app.models.analysis_models import FatigueAnalysis
from app.core.logging import get_logger

logger = get_logger("analyzer.fatigue")

# Thresholds
FREQUENCY_THRESHOLDS = {
    "low": 3.0,
    "medium": 5.0,
    "high": 7.0,
    "critical": 10.0,
}
CTR_DECLINE_THRESHOLD = -15.0  # % decline signals fatigue
CPC_RISE_THRESHOLD = 20.0  # % rise signals fatigue


def compute_fatigue(
    session: Session,
    date_start: str,
    date_stop: str,
    entity_type: str = "ad",
    trend_signals: list | None = None,
) -> FatigueAnalysis:
    """Analyze ad fatigue across entities."""

    # Get frequency metrics
    freq_rows = session.exec(
        select(NormalizedMetric).where(
            NormalizedMetric.source == "meta",
            NormalizedMetric.entity_type == entity_type,
            NormalizedMetric.metric_name == "frequency",
            NormalizedMetric.date >= date_start,
            NormalizedMetric.date <= date_stop,
        )
    ).all()

    # Aggregate average frequency per entity
    freq_sums: dict[str, list[float]] = defaultdict(list)
    entity_names: dict[str, str] = {}
    for r in freq_rows:
        freq_sums[r.entity_id].append(r.metric_value)
        entity_names[r.entity_id] = r.entity_name

    affected: List[dict] = []
    signals: List[str] = []
    max_fatigue = "none"

    fatigue_order = ["none", "low", "medium", "high", "critical"]

    for entity_id, freqs in freq_sums.items():
        avg_freq = sum(freqs) / len(freqs) if freqs else 0

        # Determine fatigue level from frequency
        entity_fatigue = "none"
        for level in ["critical", "high", "medium", "low"]:
            if avg_freq >= FREQUENCY_THRESHOLDS[level]:
                entity_fatigue = level
                break

        # Check trend signals for CTR decline + CPC rise
        ctr_declining = False
        cpc_rising = False
        if trend_signals:
            for ts in trend_signals:
                if ts.entity_id == entity_id:
                    if (
                        ts.metric_name == "ctr"
                        and ts.change_pct <= CTR_DECLINE_THRESHOLD
                    ):
                        ctr_declining = True
                    if ts.metric_name == "cpc" and ts.change_pct >= CPC_RISE_THRESHOLD:
                        cpc_rising = True

        # Upgrade fatigue if trends confirm it
        if entity_fatigue != "none" and (ctr_declining or cpc_rising):
            idx = fatigue_order.index(entity_fatigue)
            if idx < len(fatigue_order) - 1:
                entity_fatigue = fatigue_order[min(idx + 1, len(fatigue_order) - 1)]

        if entity_fatigue != "none":
            affected.append(
                {
                    "entity_id": entity_id,
                    "entity_name": entity_names.get(entity_id, ""),
                    "entity_type": entity_type,
                    "fatigue_level": entity_fatigue,
                    "avg_frequency": round(avg_freq, 2),
                    "ctr_declining": ctr_declining,
                    "cpc_rising": cpc_rising,
                }
            )

            if fatigue_order.index(entity_fatigue) > fatigue_order.index(max_fatigue):
                max_fatigue = entity_fatigue

    # Build signal messages
    if affected:
        high_fatigue = [
            a for a in affected if a["fatigue_level"] in ("high", "critical")
        ]
        if high_fatigue:
            signals.append(f"{len(high_fatigue)} entities with high/critical fatigue")
        ctr_drops = [a for a in affected if a.get("ctr_declining")]
        if ctr_drops:
            signals.append(f"{len(ctr_drops)} entities with declining CTR")
        cpc_rises = [a for a in affected if a.get("cpc_rising")]
        if cpc_rises:
            signals.append(f"{len(cpc_rises)} entities with rising CPC")

    logger.info(f"Fatigue analysis: {max_fatigue} — {len(affected)} affected entities")

    return FatigueAnalysis(
        fatigue_level=max_fatigue,
        affected_entities=affected,
        signals=signals,
    )
