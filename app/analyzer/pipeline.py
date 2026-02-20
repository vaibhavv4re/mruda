"""MRUDA — Analysis Pipeline Orchestrator.

Runs the full data flow:
  fetch → store raw → normalize → run engines → produce InsightOutput → store result

Supports time window parameterization, data freshness checks, and confidence scoring.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict

from sqlmodel import Session, select

from app.config import settings
from app.connectors.meta.client import MetaClient
from app.connectors.meta.endpoints import MetaEndpoints
from app.connectors.meta.transformer import transform_insights
from app.models.raw_models import RawMetaData
from app.models.normalized_models import NormalizedMetric
from app.models.analysis_models import (
    AnalysisResult,
    InsightOutput,
    MetaSummary,
    CampaignRanking,
    ConfidenceBreakdown,
    MetricContext,
    ROASReason,
    Risk,
)
from app.analyzer.kpi_engine import compute_kpis
from app.analyzer.trend_engine import compute_trends
from app.analyzer.fatigue_engine import compute_fatigue
from app.analyzer.opportunity_engine import compute_opportunities
from app.core.logging import get_logger

logger = get_logger("analyzer.pipeline")

ANALYSIS_SCHEMA_VERSION = settings.analysis_schema_version


def _validate_date(d: Optional[str]) -> Optional[str]:
    """Return the date string if valid YYYY-MM-DD, else None."""
    if not d:
        return None
    try:
        datetime.strptime(d, "%Y-%m-%d")
        return d
    except ValueError:
        return None


def _resolve_dates(
    date_range: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[str, str]:
    """Resolve date parameters into (start, end) strings."""
    today = datetime.now(timezone.utc).date()

    # Sanitize inputs
    start_date = _validate_date(start_date)
    end_date = _validate_date(end_date)

    if start_date and end_date:
        return start_date, end_date

    if date_range and date_range != "string":
        mapping = {
            "yesterday": (today - timedelta(days=1), today - timedelta(days=1)),
            "last_7d": (today - timedelta(days=7), today - timedelta(days=1)),
            "last_14d": (today - timedelta(days=14), today - timedelta(days=1)),
            "last_30d": (today - timedelta(days=30), today - timedelta(days=1)),
            "this_month": (today.replace(day=1), today),
        }
        if date_range in mapping:
            s, e = mapping[date_range]
            return s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")

    # Default: last 7 days
    return (today - timedelta(days=7)).strftime("%Y-%m-%d"), (
        today - timedelta(days=1)
    ).strftime("%Y-%m-%d")


def _check_data_freshness(session: Session, date_stop: str) -> bool:
    """Check if data for the date range has already been fetched today."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = session.exec(
        select(RawMetaData).where(
            RawMetaData.date_stop == date_stop,
            RawMetaData.fetched_at
            >= datetime.strptime(today_str, "%Y-%m-%d").replace(tzinfo=timezone.utc),
        )
    ).first()
    return existing is not None


def _compute_confidence(
    session: Session,
    date_start: str,
    date_stop: str,
) -> tuple[float, ConfidenceBreakdown]:
    """Compute confidence score based on data quality."""
    metrics = session.exec(
        select(NormalizedMetric).where(
            NormalizedMetric.source == "meta",
            NormalizedMetric.date >= date_start,
            NormalizedMetric.date <= date_stop,
        )
    ).all()

    if not metrics:
        return 0.0, ConfidenceBreakdown(
            data_completeness=0.0,
            sample_size_factor=0.0,
            metric_coverage=0.0,
            volume_stability=0.0,
        )

    # Data completeness: how many days have data?
    start = datetime.strptime(date_start, "%Y-%m-%d")
    stop = datetime.strptime(date_stop, "%Y-%m-%d")
    expected_days = (stop - start).days + 1
    actual_days = len(set(m.date for m in metrics))
    data_completeness = (
        min(actual_days / expected_days, 1.0) if expected_days > 0 else 0.0
    )

    # Sample size: more entities = more confidence
    entity_count = len(set(m.entity_id for m in metrics))
    sample_size_factor = min(entity_count / 5, 1.0)  # Full confidence at 5+ entities

    # Metric coverage: how many distinct metric types?
    metric_names = set(m.metric_name for m in metrics)
    expected_metrics = {"impressions", "clicks", "spend", "ctr", "cpc"}
    coverage = len(metric_names & expected_metrics) / len(expected_metrics)

    # Volume stability: coefficient of variation of impressions
    daily_impressions: dict[str, float] = defaultdict(float)
    for m in metrics:
        if m.metric_name == "impressions":
            daily_impressions[m.date] += m.metric_value
    if len(daily_impressions) > 1:
        values = list(daily_impressions.values())
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        cv = (variance**0.5) / mean if mean > 0 else 1.0
        volume_stability = max(1.0 - cv, 0.0)
    else:
        volume_stability = 0.5

    breakdown = ConfidenceBreakdown(
        data_completeness=round(data_completeness, 3),
        sample_size_factor=round(sample_size_factor, 3),
        metric_coverage=round(coverage, 3),
        volume_stability=round(volume_stability, 3),
    )

    # Weighted average
    score = (
        data_completeness * 0.3
        + sample_size_factor * 0.2
        + coverage * 0.3
        + volume_stability * 0.2
    )
    return round(score, 4), breakdown


def _build_meta_summary(
    session: Session,
    date_start: str,
    date_stop: str,
) -> MetaSummary:
    """Build account-level summary from normalized metrics."""
    rows = session.exec(
        select(NormalizedMetric).where(
            NormalizedMetric.source == "meta",
            NormalizedMetric.entity_type == "account",
            NormalizedMetric.date >= date_start,
            NormalizedMetric.date <= date_stop,
        )
    ).all()

    sums: dict[str, float] = defaultdict(float)
    for r in rows:
        sums[r.metric_name] += r.metric_value

    spend = sums.get("spend", 0)
    impressions = sums.get("impressions", 0)
    clicks = sums.get("clicks", 0)

    return MetaSummary(
        total_spend=round(spend, 2),
        total_impressions=int(impressions),
        total_clicks=int(clicks),
        total_reach=int(sums.get("reach", 0)),
        avg_ctr=round((clicks / impressions * 100) if impressions > 0 else 0, 4),
        avg_cpc=round((spend / clicks) if clicks > 0 else 0, 4),
        avg_cpm=round((spend / impressions * 1000) if impressions > 0 else 0, 4),
        total_conversions=int(sums.get("conversions", 0)),
        overall_roas=round(
            (sums.get("purchase_value", 0) / spend) if spend > 0 else 0, 4
        ),
    )


def _build_rankings(kpis: list) -> list[CampaignRanking]:
    """Rank campaigns by ROAS (primary KPI)."""
    # Group KPIs by entity
    entity_kpis: dict[str, dict[str, float]] = {}
    entity_names: dict[str, str] = {}
    for kpi in kpis:
        if kpi.entity_type == "campaign":
            if kpi.entity_id not in entity_kpis:
                entity_kpis[kpi.entity_id] = {}
                entity_names[kpi.entity_id] = kpi.entity_name
            entity_kpis[kpi.entity_id][kpi.name] = kpi.value

    # Sort by ROAS descending
    sorted_entities = sorted(
        entity_kpis.items(),
        key=lambda x: x[1].get("roas", 0),
        reverse=True,
    )

    rankings = []
    for rank, (eid, mkpis) in enumerate(sorted_entities, 1):
        rankings.append(
            CampaignRanking(
                rank=rank,
                entity_id=eid,
                entity_name=entity_names.get(eid, ""),
                primary_kpi="roas",
                primary_value=round(mkpis.get("roas", 0), 4),
                spend=round(mkpis.get("spend", 0), 2),
                roas=round(mkpis.get("roas", 0), 4),
            )
        )

    return rankings


async def run_analysis(
    session: Session,
    date_range: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    force: bool = False,
) -> InsightOutput:
    """Execute the full MRUDA analysis pipeline."""
    date_start, date_stop = _resolve_dates(date_range, start_date, end_date)
    logger.info(
        f"Starting analysis pipeline: {date_start} → {date_stop} (force={force})"
    )

    # ── Step 1: Data Freshness Check + Currency Fetch ──
    client = MetaClient()
    currency = settings.account_currency
    campaign_objective = ""

    try:
        # Always fetch currency from Meta (lightweight call)
        currency = await client.fetch_currency()

        if not force and _check_data_freshness(session, date_stop):
            logger.info("Data already fetched today, skipping Meta API call")
        else:
            # ── Step 2: Fetch from Meta ──
            endpoints = MetaEndpoints(client, session)

            await endpoints.fetch_account_insights(date_start, date_stop)
            await endpoints.fetch_campaign_insights(date_start, date_stop)
            await endpoints.fetch_adset_insights(date_start, date_stop)
            await endpoints.fetch_ad_insights(date_start, date_stop)

            # Fetch campaign structure to detect objective
            campaigns = await endpoints.fetch_campaigns()
            if campaigns:
                campaign_objective = campaigns[0].get("objective", "")

            endpoints.commit()
            logger.info("Raw data fetched and stored")
    except Exception as e:
        logger.error(f"Meta API fetch failed: {e}")
        # Continue with existing data if available
    finally:
        await client.close()

    # ── Step 3: Normalize ──
    raw_entries = session.exec(
        select(RawMetaData).where(
            RawMetaData.date_start == date_start,
            RawMetaData.date_stop == date_stop,
        )
    ).all()

    for raw in raw_entries:
        try:
            payload = json.loads(raw.payload_json)
            if isinstance(payload, list):
                level = raw.entity_type
                transform_insights(payload, level, session)
        except Exception as e:
            logger.error(f"Normalization failed for raw id {raw.id}: {e}")

    # ── Step 4: Run Engines ──
    kpis = compute_kpis(session, date_start, date_stop, entity_type="campaign")
    trends = compute_trends(session, date_start, date_stop, entity_type="campaign")
    fatigue = compute_fatigue(
        session, date_start, date_stop, entity_type="ad", trend_signals=trends
    )
    opportunities = compute_opportunities(kpis)

    # ── Step 5: Build Output ──
    meta_summary = _build_meta_summary(session, date_start, date_stop)
    rankings = _build_rankings(kpis)
    confidence, confidence_breakdown = _compute_confidence(
        session, date_start, date_stop
    )

    # Detect ROAS context based on campaign objective
    lead_gen_objectives = {"LEAD_GENERATION", "OUTCOME_LEADS", "LEAD_GEN"}
    awareness_objectives = {"BRAND_AWARENESS", "REACH", "OUTCOME_AWARENESS"}

    if campaign_objective.upper() in lead_gen_objectives:
        meta_summary.roas_context = MetricContext(
            applicable=False, reason=ROASReason.LEAD_GEN
        )
    elif campaign_objective.upper() in awareness_objectives:
        meta_summary.roas_context = MetricContext(
            applicable=False, reason=ROASReason.AWARENESS
        )
    elif meta_summary.overall_roas == 0 and meta_summary.total_conversions == 0:
        meta_summary.roas_context = MetricContext(
            applicable=False, reason=ROASReason.NO_CONVERSION_VALUE
        )
    meta_summary.campaign_objective = campaign_objective

    # Detect risks from trends — ONLY when previous period data exists
    risks = []
    for t in trends:
        if not t.previous_period_available:
            continue  # Never flag insufficient data as risk
        if t.signal == "alert" and abs(t.change_pct) > 25:
            risks.append(
                Risk(
                    type="trend_alert",
                    description=f"{t.metric_name} {t.direction} {t.change_pct:+.1f}% for {t.entity_name}",
                    severity="high" if abs(t.change_pct) > 50 else "medium",
                    entity_type=t.entity_type,
                    entity_id=t.entity_id,
                )
            )

    insight = InsightOutput(
        schema_version=ANALYSIS_SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        currency=currency,
        date_range_start=date_start,
        date_range_end=date_stop,
        meta_summary=meta_summary,
        kpis=kpis,
        campaign_rankings=rankings,
        trend_signals=trends,
        fatigue_analysis=fatigue,
        opportunities=opportunities,
        risks=risks,
        confidence_score=confidence,
        confidence_breakdown=confidence_breakdown,
    )

    # ── Step 6: Store Result ──
    result = AnalysisResult(
        schema_version=ANALYSIS_SCHEMA_VERSION,
        date_range_start=date_start,
        date_range_end=date_stop,
        result_json=insight.model_dump_json(),
    )
    session.add(result)
    session.commit()

    logger.info(
        f"Analysis complete. Currency: {currency}. Confidence: {confidence}. Stored as result id {result.id}"
    )
    return insight
