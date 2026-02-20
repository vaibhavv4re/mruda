"""MRUDA — Trend Engine.

Compares current period vs previous period for key metrics.
Produces trend signals: direction, % change, signal flags.
"""

from typing import List
from collections import defaultdict
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models.normalized_models import NormalizedMetric
from app.models.analysis_models import TrendSignal
from app.core.logging import get_logger

logger = get_logger("analyzer.trend")


def _compute_date_ranges(date_start: str, date_stop: str) -> tuple[str, str]:
    """Compute the previous period of equal length."""
    start = datetime.strptime(date_start, "%Y-%m-%d")
    stop = datetime.strptime(date_stop, "%Y-%m-%d")
    period_days = (stop - start).days + 1
    prev_stop = start - timedelta(days=1)
    prev_start = prev_stop - timedelta(days=period_days - 1)
    return prev_start.strftime("%Y-%m-%d"), prev_stop.strftime("%Y-%m-%d")


def _aggregate(
    session: Session,
    entity_type: str,
    date_start: str,
    date_stop: str,
) -> dict[tuple[str, str, str], float]:
    """Aggregate metrics: (entity_id, entity_name, metric_name) → sum."""
    rows = session.exec(
        select(NormalizedMetric).where(
            NormalizedMetric.source == "meta",
            NormalizedMetric.entity_type == entity_type,
            NormalizedMetric.date >= date_start,
            NormalizedMetric.date <= date_stop,
        )
    ).all()

    agg: dict[tuple[str, str, str], float] = defaultdict(float)
    for r in rows:
        agg[(r.entity_id, r.entity_name, r.metric_name)] += r.metric_value
    return dict(agg)


def _direction(change_pct: float) -> str:
    if change_pct > 2:
        return "up"
    elif change_pct < -2:
        return "down"
    return "flat"


def _signal(metric_name: str, direction: str) -> str:
    """Determine signal based on metric semantics."""
    # For cost metrics, "up" is bad
    cost_metrics = {"cpc", "cpm", "cpa", "spend"}
    # For performance metrics, "up" is good
    perf_metrics = {
        "ctr",
        "roas",
        "engagement_rate",
        "clicks",
        "conversions",
        "purchase_value",
    }

    if metric_name in cost_metrics:
        if direction == "up":
            return "alert"
        elif direction == "down":
            return "improving"
    elif metric_name in perf_metrics:
        if direction == "up":
            return "improving"
        elif direction == "down":
            return "declining"
    return "stable"


# Key metrics to track trends for
TREND_METRICS = {
    "impressions",
    "clicks",
    "spend",
    "ctr",
    "cpc",
    "cpm",
    "conversions",
    "purchase_value",
    "roas",
    "engagement_rate",
}


def compute_trends(
    session: Session,
    date_start: str,
    date_stop: str,
    entity_type: str = "campaign",
) -> List[TrendSignal]:
    """Compare current vs previous period for all entities."""
    prev_start, prev_stop = _compute_date_ranges(date_start, date_stop)

    current = _aggregate(session, entity_type, date_start, date_stop)
    previous = _aggregate(session, entity_type, prev_start, prev_stop)

    signals: List[TrendSignal] = []

    # Process all current period keys
    seen_keys = set()
    for (eid, ename, mname), curr_val in current.items():
        if mname not in TREND_METRICS:
            continue
        seen_keys.add((eid, ename, mname))
        prev_val = previous.get((eid, ename, mname), 0)

        # Handle zero baseline — insufficient data, not +100%
        if prev_val == 0:
            signals.append(
                TrendSignal(
                    metric_name=mname,
                    entity_type=entity_type,
                    entity_id=eid,
                    entity_name=ename,
                    current_value=round(curr_val, 4),
                    previous_value=0,
                    change_pct=0,
                    direction="flat",
                    signal="insufficient_data",
                    previous_period_available=False,
                )
            )
            continue

        change = (curr_val - prev_val) / prev_val * 100
        d = _direction(change)

        signals.append(
            TrendSignal(
                metric_name=mname,
                entity_type=entity_type,
                entity_id=eid,
                entity_name=ename,
                current_value=round(curr_val, 4),
                previous_value=round(prev_val, 4),
                change_pct=round(change, 2),
                direction=d,
                signal=_signal(mname, d),
                previous_period_available=True,
            )
        )

    logger.info(f"Computed {len(signals)} trend signals for {entity_type}")
    return signals
