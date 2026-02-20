"""MRUDA — Analysis Output Models (Versioned)."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from sqlmodel import SQLModel, Field


# ─────────────────────────────────────────────
# DATABASE MODEL — Stores versioned analysis results
# ─────────────────────────────────────────────


class AnalysisResult(SQLModel, table=True):
    """Versioned analysis output stored in DB."""

    __tablename__ = "analysis_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field(description="e.g. 1.0.0")
    date_range_start: str = Field(default="", description="Analysis window start")
    date_range_end: str = Field(default="", description="Analysis window end")
    result_json: str = Field(description="Full InsightOutput as JSON")


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS — Insight Output v1
# ─────────────────────────────────────────────


class KPIMetric(BaseModel):
    """A single computed KPI."""

    name: str
    value: float
    unit: str = ""
    entity_type: str = ""
    entity_id: str = ""
    entity_name: str = ""


class CampaignRanking(BaseModel):
    """Campaign ranked by a KPI."""

    rank: int
    entity_id: str
    entity_name: str
    primary_kpi: str
    primary_value: float
    spend: float = 0.0
    roas: float = 0.0


class TrendSignal(BaseModel):
    """Trend comparison for a metric."""

    metric_name: str
    entity_type: str
    entity_id: str
    entity_name: str = ""
    current_value: float
    previous_value: float
    change_pct: float
    direction: str  # "up" | "down" | "flat"
    signal: str = (
        ""  # "improving" | "declining" | "stable" | "alert" | "insufficient_data"
    )
    previous_period_available: bool = True


class FatigueAnalysis(BaseModel):
    """Ad fatigue detection."""

    fatigue_level: str  # "none" | "low" | "medium" | "high" | "critical"
    affected_entities: List[dict] = []
    signals: List[str] = []


class Opportunity(BaseModel):
    """Actionable opportunity flag."""

    type: str
    description: str
    entity_type: str = ""
    entity_id: str = ""
    entity_name: str = ""
    potential_impact: str = ""  # "low" | "medium" | "high"


class Risk(BaseModel):
    """Risk flag."""

    type: str
    description: str
    severity: str = "medium"  # "low" | "medium" | "high"
    entity_type: str = ""
    entity_id: str = ""


class ConfidenceBreakdown(BaseModel):
    """How confidence was computed."""

    data_completeness: float = 1.0
    sample_size_factor: float = 1.0
    metric_coverage: float = 1.0
    volume_stability: float = 1.0


class ROASReason(str, Enum):
    """Why ROAS may not be applicable."""

    APPLICABLE = "applicable"
    LEAD_GEN = "lead_generation_campaign"
    AWARENESS = "awareness_objective"
    NO_CONVERSION_VALUE = "no_conversion_value_tracked"


class MetricContext(BaseModel):
    """Context for a metric's applicability."""

    applicable: bool = True
    reason: ROASReason = ROASReason.APPLICABLE


class MetaSummary(BaseModel):
    """High-level account summary."""

    total_spend: float = 0.0
    total_impressions: int = 0
    total_clicks: int = 0
    total_reach: int = 0
    avg_ctr: float = 0.0
    avg_cpc: float = 0.0
    avg_cpm: float = 0.0
    total_conversions: int = 0
    overall_roas: float = 0.0
    campaign_objective: str = ""
    roas_context: MetricContext = MetricContext()


class InsightOutput(BaseModel):
    """MRUDA Insight Output v1 — the analyzer's structured intelligence."""

    schema_version: str = "1.0.0"
    generated_at: str = ""
    currency: str = "INR"
    date_range_start: str = ""
    date_range_end: str = ""
    meta_summary: MetaSummary = MetaSummary()
    kpis: List[KPIMetric] = []
    campaign_rankings: List[CampaignRanking] = []
    trend_signals: List[TrendSignal] = []
    fatigue_analysis: FatigueAnalysis = FatigueAnalysis(fatigue_level="none")
    opportunities: List[Opportunity] = []
    risks: List[Risk] = []
    confidence_score: float = 0.0
    confidence_breakdown: ConfidenceBreakdown = ConfidenceBreakdown()
