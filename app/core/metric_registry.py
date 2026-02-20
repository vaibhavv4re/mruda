"""MRUDA — Unified Metric Registry.

Defines the canonical set of metrics and their classifications.
When adding new connectors (Google Ads, Reviews, Bookings), register
metrics here so the analyzer engines treat them uniformly.
"""

from enum import Enum
from typing import Dict


class MetricType(str, Enum):
    """How a metric is categorised."""

    VOLUME = "volume"  # Raw counts: impressions, clicks, reach
    COST = "cost"  # Monetary: spend, cost
    REVENUE = "revenue"  # Income: purchase_value, revenue
    RATE = "rate"  # Pre-computed rates from source: ctr, cpc
    DERIVED = "derived"  # Computed by MRUDA engines: roas, cpa
    ENGAGEMENT = "engagement"  # Likes, shares, comments
    VIDEO = "video"  # Video-specific: views, completions


class MetricDefinition:
    """Describes a single metric."""

    def __init__(
        self, name: str, metric_type: MetricType, unit: str = "", description: str = ""
    ):
        self.name = name
        self.metric_type = metric_type
        self.unit = unit
        self.description = description

    def __repr__(self) -> str:
        return f"<Metric {self.name} ({self.metric_type.value})>"


# ─────────────────────────────────────────────
# META METRICS — Canonical Registry
# ─────────────────────────────────────────────

META_METRICS: Dict[str, MetricDefinition] = {
    # Volume
    "impressions": MetricDefinition(
        "impressions", MetricType.VOLUME, "count", "Number of times ad was shown"
    ),
    "reach": MetricDefinition(
        "reach", MetricType.VOLUME, "count", "Unique users who saw ad"
    ),
    "clicks": MetricDefinition("clicks", MetricType.VOLUME, "count", "Total clicks"),
    "unique_clicks": MetricDefinition(
        "unique_clicks", MetricType.VOLUME, "count", "Unique users who clicked"
    ),
    "frequency": MetricDefinition(
        "frequency", MetricType.VOLUME, "avg", "Average times ad shown per user"
    ),
    # Cost
    "spend": MetricDefinition(
        "spend", MetricType.COST, "currency", "Total amount spent"
    ),
    # Revenue
    "purchase_value": MetricDefinition(
        "purchase_value",
        MetricType.REVENUE,
        "currency",
        "Total purchase conversion value",
    ),
    # Rates (from Meta directly)
    "ctr": MetricDefinition("ctr", MetricType.RATE, "%", "Click-through rate"),
    "cpc": MetricDefinition("cpc", MetricType.RATE, "currency", "Cost per click"),
    "cpm": MetricDefinition(
        "cpm", MetricType.RATE, "currency", "Cost per 1000 impressions"
    ),
    "cpp": MetricDefinition("cpp", MetricType.RATE, "currency", "Cost per purchase"),
    # Engagement
    "post_engagement": MetricDefinition(
        "post_engagement", MetricType.ENGAGEMENT, "count", "Total post engagements"
    ),
    "page_engagement": MetricDefinition(
        "page_engagement", MetricType.ENGAGEMENT, "count", "Total page engagements"
    ),
    "likes": MetricDefinition("likes", MetricType.ENGAGEMENT, "count", "Likes"),
    "comments": MetricDefinition(
        "comments", MetricType.ENGAGEMENT, "count", "Comments"
    ),
    "shares": MetricDefinition("shares", MetricType.ENGAGEMENT, "count", "Shares"),
    # Video
    "video_views": MetricDefinition(
        "video_views", MetricType.VIDEO, "count", "Video views"
    ),
    "video_p25_watched": MetricDefinition(
        "video_p25_watched", MetricType.VIDEO, "count", "Watched 25%"
    ),
    "video_p50_watched": MetricDefinition(
        "video_p50_watched", MetricType.VIDEO, "count", "Watched 50%"
    ),
    "video_p75_watched": MetricDefinition(
        "video_p75_watched", MetricType.VIDEO, "count", "Watched 75%"
    ),
    "video_p100_watched": MetricDefinition(
        "video_p100_watched", MetricType.VIDEO, "count", "Watched 100%"
    ),
}


# ─────────────────────────────────────────────
# DERIVED METRICS — Computed by analyzer engines
# ─────────────────────────────────────────────

DERIVED_METRICS: Dict[str, MetricDefinition] = {
    "roas": MetricDefinition("roas", MetricType.DERIVED, "ratio", "Return on ad spend"),
    "cpa": MetricDefinition(
        "cpa", MetricType.DERIVED, "currency", "Cost per acquisition"
    ),
    "engagement_rate": MetricDefinition(
        "engagement_rate", MetricType.DERIVED, "%", "Engagements / Impressions"
    ),
    "video_completion_rate": MetricDefinition(
        "video_completion_rate", MetricType.DERIVED, "%", "100% views / total views"
    ),
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

ALL_METRICS = {**META_METRICS, **DERIVED_METRICS}


def get_metric(name: str) -> MetricDefinition | None:
    """Look up a metric by name."""
    return ALL_METRICS.get(name)


def metrics_by_type(metric_type: MetricType) -> list[MetricDefinition]:
    """Return all metrics of a given type."""
    return [m for m in ALL_METRICS.values() if m.metric_type == metric_type]
