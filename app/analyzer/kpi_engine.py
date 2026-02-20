"""MRUDA — KPI Engine.

Computes derived KPIs from normalized metrics:
CTR, CPC, CPM, CPA, ROAS, Engagement Rate, Video Completion Rate.
"""

from typing import Dict, List
from collections import defaultdict

from sqlmodel import Session, select

from app.models.normalized_models import NormalizedMetric
from app.models.analysis_models import KPIMetric
from app.core.logging import get_logger

logger = get_logger("analyzer.kpi")


def _get_metrics_for_entity(
    session: Session,
    entity_type: str,
    entity_id: str,
    date_start: str,
    date_stop: str,
) -> Dict[str, float]:
    """Aggregate metric values for an entity across a date range."""
    rows = session.exec(
        select(NormalizedMetric).where(
            NormalizedMetric.source == "meta",
            NormalizedMetric.entity_type == entity_type,
            NormalizedMetric.entity_id == entity_id,
            NormalizedMetric.date >= date_start,
            NormalizedMetric.date <= date_stop,
        )
    ).all()

    # Sum volume/cost/revenue, average rates
    sums: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)
    for r in rows:
        sums[r.metric_name] += r.metric_value
        counts[r.metric_name] += 1

    return dict(sums)


def compute_kpis(
    session: Session,
    date_start: str,
    date_stop: str,
    entity_type: str = "campaign",
) -> List[KPIMetric]:
    """Compute KPIs for all entities of a given type in the date range."""
    # Get distinct entities
    entities = session.exec(
        select(NormalizedMetric.entity_id, NormalizedMetric.entity_name)
        .where(
            NormalizedMetric.source == "meta",
            NormalizedMetric.entity_type == entity_type,
            NormalizedMetric.date >= date_start,
            NormalizedMetric.date <= date_stop,
        )
        .distinct()
    ).all()

    kpis: List[KPIMetric] = []

    for entity_id, entity_name in entities:
        m = _get_metrics_for_entity(
            session, entity_type, entity_id, date_start, date_stop
        )

        impressions = m.get("impressions", 0)
        clicks = m.get("clicks", 0)
        spend = m.get("spend", 0)
        conversions = m.get("conversions", 0)
        purchase_value = m.get("purchase_value", 0)
        post_engagement = m.get("post_engagement", 0)
        video_views = m.get("video_views", 0)
        video_complete = m.get("video_p100_watched", 0)

        # CTR
        ctr = (clicks / impressions * 100) if impressions > 0 else 0.0
        kpis.append(
            KPIMetric(
                name="ctr",
                value=round(ctr, 4),
                unit="%",
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
            )
        )

        # CPC
        cpc = (spend / clicks) if clicks > 0 else 0.0
        kpis.append(
            KPIMetric(
                name="cpc",
                value=round(cpc, 4),
                unit="currency",
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
            )
        )

        # CPM
        cpm = (spend / impressions * 1000) if impressions > 0 else 0.0
        kpis.append(
            KPIMetric(
                name="cpm",
                value=round(cpm, 4),
                unit="currency",
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
            )
        )

        # CPA
        cpa = (spend / conversions) if conversions > 0 else 0.0
        kpis.append(
            KPIMetric(
                name="cpa",
                value=round(cpa, 4),
                unit="currency",
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
            )
        )

        # ROAS
        roas = (purchase_value / spend) if spend > 0 else 0.0
        kpis.append(
            KPIMetric(
                name="roas",
                value=round(roas, 4),
                unit="ratio",
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
            )
        )

        # Engagement Rate
        eng_rate = (post_engagement / impressions * 100) if impressions > 0 else 0.0
        kpis.append(
            KPIMetric(
                name="engagement_rate",
                value=round(eng_rate, 4),
                unit="%",
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
            )
        )

        # Video Completion Rate
        vcr = (video_complete / video_views * 100) if video_views > 0 else 0.0
        kpis.append(
            KPIMetric(
                name="video_completion_rate",
                value=round(vcr, 4),
                unit="%",
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
            )
        )

    logger.info(f"Computed {len(kpis)} KPIs for {len(entities)} {entity_type}s")
    return kpis
