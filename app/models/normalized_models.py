"""MRUDA — Normalized Metric Models (Universal Schema).

This is the plug-and-play schema. Every connector normalizes into this format.
Adding Google Ads, Reviews, or Bookings later requires zero schema changes.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, UniqueConstraint


class NormalizedMetric(SQLModel, table=True):
    """Universal metric record.

    Unique constraint on (entity_type, entity_id, date, metric_name)
    ensures idempotent upserts — re-running analysis won't duplicate data.
    """

    __tablename__ = "normalized_metrics"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "entity_type",
            "entity_id",
            "date",
            "metric_name",
            name="uq_normalized_metric",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True, description="Data source: meta | google | booking")
    entity_type: str = Field(index=True, description="campaign | adset | ad | account")
    entity_id: str = Field(index=True, description="Source entity ID")
    entity_name: str = Field(default="", description="Human-readable name")
    date: str = Field(index=True, description="YYYY-MM-DD")
    metric_name: str = Field(index=True, description="Metric key from registry")
    metric_value: float = Field(description="Numeric value")
    metric_type: str = Field(
        default="", description="Classification from metric_registry"
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
