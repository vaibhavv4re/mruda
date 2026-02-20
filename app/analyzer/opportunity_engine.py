"""MRUDA — Opportunity Engine.

Identifies actionable opportunities:
- High ROAS + Low Spend → scale up
- High Engagement + Low CTR → improve CTA
- Low CPC + High Volume → capitalize
"""

from typing import List

from app.models.analysis_models import KPIMetric, Opportunity
from app.core.logging import get_logger

logger = get_logger("analyzer.opportunity")

# Thresholds (configurable)
HIGH_ROAS_THRESHOLD = 3.0
LOW_SPEND_PERCENTILE = 0.3  # Bottom 30% of spenders
HIGH_ENGAGEMENT_RATE = 2.0  # %
LOW_CTR_THRESHOLD = 1.0  # %
LOW_CPC_THRESHOLD_RATIO = 0.7  # Below 70% of average CPC


def compute_opportunities(kpis: List[KPIMetric]) -> List[Opportunity]:
    """Detect opportunities from computed KPIs."""

    # Group KPIs by entity
    entity_kpis: dict[str, dict[str, float]] = {}
    entity_names: dict[str, str] = {}

    for kpi in kpis:
        key = kpi.entity_id
        if key not in entity_kpis:
            entity_kpis[key] = {}
            entity_names[key] = kpi.entity_name
        entity_kpis[key][kpi.name] = kpi.value

    opportunities: List[Opportunity] = []

    # Calculate averages for relative thresholds
    all_spend = [
        v.get("spend", 0) for v in entity_kpis.values() if v.get("spend", 0) > 0
    ]
    avg_spend = sum(all_spend) / len(all_spend) if all_spend else 0
    spend_threshold = avg_spend * LOW_SPEND_PERCENTILE

    all_cpc = [v.get("cpc", 0) for v in entity_kpis.values() if v.get("cpc", 0) > 0]
    avg_cpc = sum(all_cpc) / len(all_cpc) if all_cpc else 0
    cpc_threshold = avg_cpc * LOW_CPC_THRESHOLD_RATIO

    for entity_id, metrics in entity_kpis.items():
        name = entity_names.get(entity_id, "")
        roas = metrics.get("roas", 0)
        spend = metrics.get("spend", 0)
        ctr = metrics.get("ctr", 0)
        cpc = metrics.get("cpc", 0)
        eng_rate = metrics.get("engagement_rate", 0)

        # 1. High ROAS + Low Spend → Scale opportunity
        if roas >= HIGH_ROAS_THRESHOLD and spend > 0 and spend <= spend_threshold:
            opportunities.append(
                Opportunity(
                    type="scale_up",
                    description=f"High ROAS ({roas:.1f}x) with low spend (${spend:.2f}). Consider increasing budget.",
                    entity_type="campaign",
                    entity_id=entity_id,
                    entity_name=name,
                    potential_impact="high",
                )
            )

        # 2. High Engagement + Low CTR → Improve CTA
        if eng_rate >= HIGH_ENGAGEMENT_RATE and ctr < LOW_CTR_THRESHOLD and ctr > 0:
            opportunities.append(
                Opportunity(
                    type="cta_optimization",
                    description=f"High engagement ({eng_rate:.1f}%) but low CTR ({ctr:.2f}%). Ad resonates but CTA needs work.",
                    entity_type="campaign",
                    entity_id=entity_id,
                    entity_name=name,
                    potential_impact="medium",
                )
            )

        # 3. Low CPC + Decent Volume → Capitalize
        if cpc > 0 and cpc <= cpc_threshold and metrics.get("clicks", 0) > 0:
            opportunities.append(
                Opportunity(
                    type="capitalize_efficiency",
                    description=f"Below-average CPC (${cpc:.2f} vs avg ${avg_cpc:.2f}). Efficient traffic source — scale it.",
                    entity_type="campaign",
                    entity_id=entity_id,
                    entity_name=name,
                    potential_impact="medium",
                )
            )

        # 4. High ROAS overall → protect
        if roas >= HIGH_ROAS_THRESHOLD * 2:
            opportunities.append(
                Opportunity(
                    type="protect_performer",
                    description=f"Exceptional ROAS ({roas:.1f}x). Protect this campaign from budget cuts.",
                    entity_type="campaign",
                    entity_id=entity_id,
                    entity_name=name,
                    potential_impact="high",
                )
            )

    logger.info(
        f"Found {len(opportunities)} opportunities across {len(entity_kpis)} entities"
    )
    return opportunities
