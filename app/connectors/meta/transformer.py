"""MRUDA — Meta Raw → Normalized Transformer.

Converts raw Meta API insight data into the universal NormalizedMetric schema
using the metric registry for classification.
"""

from typing import Any, Dict, List

from sqlmodel import Session, select

from app.models.normalized_models import NormalizedMetric
from app.core.metric_registry import META_METRICS, get_metric
from app.core.logging import get_logger

logger = get_logger("meta.transformer")

# Direct-map fields from Meta insight response
DIRECT_METRICS = [
    "impressions",
    "reach",
    "clicks",
    "unique_clicks",
    "spend",
    "frequency",
    "ctr",
    "cpc",
    "cpm",
    "cpp",
]


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_entity_info(row: Dict[str, Any], level: str) -> tuple[str, str, str]:
    """Extract entity_type, entity_id, entity_name from an insight row."""
    if level == "ad":
        return "ad", row.get("ad_id", ""), row.get("ad_name", "")
    elif level == "adset":
        return "adset", row.get("adset_id", ""), row.get("adset_name", "")
    elif level == "campaign":
        return "campaign", row.get("campaign_id", ""), row.get("campaign_name", "")
    else:
        return "account", row.get("account_id", ""), "Account"


def _extract_action_metrics(row: Dict[str, Any]) -> Dict[str, float]:
    """Extract action-based metrics (conversions, purchases, etc.)."""
    metrics: Dict[str, float] = {}
    actions = row.get("actions") or []
    for action in actions:
        action_type = action.get("action_type", "")
        value = _safe_float(action.get("value", 0))
        if action_type == "link_click":
            metrics["link_clicks"] = value
        elif action_type == "post_engagement":
            metrics["post_engagement"] = value
        elif action_type == "page_engagement":
            metrics["page_engagement"] = value
        elif action_type == "like":
            metrics["likes"] = value
        elif action_type == "comment":
            metrics["comments"] = value
        elif action_type == "post":
            metrics["shares"] = value
        elif action_type in ("purchase", "offsite_conversion.fb_pixel_purchase"):
            metrics["conversions"] = metrics.get("conversions", 0) + value
        elif action_type == "video_view":
            metrics["video_views"] = value

    # Action values (revenue)
    action_values = row.get("action_values") or []
    for av in action_values:
        if av.get("action_type") in (
            "purchase",
            "offsite_conversion.fb_pixel_purchase",
        ):
            metrics["purchase_value"] = _safe_float(av.get("value", 0))

    # Video completion metrics
    for pct in ["25", "50", "75", "100"]:
        key = f"video_p{pct}_watched_actions"
        vdata = row.get(key) or []
        for v in vdata:
            if v.get("action_type") == "video_view":
                metrics[f"video_p{pct}_watched"] = _safe_float(v.get("value", 0))

    return metrics


def transform_insights(
    raw_data: List[Dict[str, Any]],
    level: str,
    session: Session,
) -> List[NormalizedMetric]:
    """Transform raw Meta insight rows into NormalizedMetric records.

    Uses idempotent upsert: if a metric already exists for the same
    (source, entity_type, entity_id, date, metric_name), it updates the value.
    """
    created: List[NormalizedMetric] = []

    for row in raw_data:
        entity_type, entity_id, entity_name = _extract_entity_info(row, level)
        date = row.get("date_start", "")

        # Collect all metrics for this row
        all_metrics: Dict[str, float] = {}

        # Direct metrics
        for metric_name in DIRECT_METRICS:
            if metric_name in row:
                all_metrics[metric_name] = _safe_float(row[metric_name])

        # Action-based metrics
        all_metrics.update(_extract_action_metrics(row))

        # Upsert each metric
        for metric_name, metric_value in all_metrics.items():
            metric_def = get_metric(metric_name)
            metric_type_str = metric_def.metric_type.value if metric_def else "unknown"

            # Check for existing record (idempotency)
            existing = session.exec(
                select(NormalizedMetric).where(
                    NormalizedMetric.source == "meta",
                    NormalizedMetric.entity_type == entity_type,
                    NormalizedMetric.entity_id == entity_id,
                    NormalizedMetric.date == date,
                    NormalizedMetric.metric_name == metric_name,
                )
            ).first()

            if existing:
                existing.metric_value = metric_value
                existing.entity_name = entity_name
                existing.metric_type = metric_type_str
                session.add(existing)
            else:
                nm = NormalizedMetric(
                    source="meta",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    date=date,
                    metric_name=metric_name,
                    metric_value=metric_value,
                    metric_type=metric_type_str,
                )
                session.add(nm)
                created.append(nm)

    session.commit()
    logger.info(
        f"Normalized {len(all_metrics) if raw_data else 0} metric types across {len(raw_data)} rows ({len(created)} new)"
    )
    return created
