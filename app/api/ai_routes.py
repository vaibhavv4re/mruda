"""MRUDA — AI Summary & Intelligence Routes."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Optional, List

from app.database import get_session
from app.models.analysis_models import AnalysisResult
from app.ai.openai_provider import OpenAIProvider
from app.ai.claude_provider import ClaudeProvider
from app.ai.sarvam_provider import SarvamProvider
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("api.ai")

router = APIRouter(tags=["AI"])


# ── Request / Response Models ──


class SummaryRequest(BaseModel):
    """Request body for POST /generate-summary."""

    provider: str = "auto"
    insight_id: Optional[int] = None
    question: Optional[str] = None


class SummaryResponse(BaseModel):
    """Response for POST /generate-summary."""

    status: str
    provider_used: str
    summary: str


class IntelligenceRequest(BaseModel):
    """Request body for POST /generate-intelligence."""

    provider: str = "auto"
    insight_id: Optional[int] = None


class CardInsight(BaseModel):
    """AI-generated insight for a signal card."""

    one_liner: str
    deep_analysis: str


class StrategicMove(BaseModel):
    """AI-generated strategic recommendation."""

    title: str
    reasoning: str
    action_items: List[str]
    confidence: str


class IntelligenceResponse(BaseModel):
    """Response for POST /generate-intelligence."""

    status: str
    provider_used: str
    hero_lines: List[str]
    card_insights: dict
    strategic_moves: List[StrategicMove]


# ── Intelligence Prompt ──

INTELLIGENCE_PROMPT = """You are MRUDA's intelligence engine. You analyze pre-computed advertising metrics and generate insights for a living intelligence surface.

You MUST respond with valid JSON only. No markdown, no code blocks, no explanation outside the JSON.

The JSON must have exactly this structure:
{
  "hero_lines": [
    "First insight — the most important finding from the data",
    "Second insight — a different angle or surprising observation",
    "Third insight — a forward-looking or strategic observation"
  ],
  "card_insights": {
    "creative_resonance": {
      "one_liner": "A punchy, specific one-liner about creative performance that references actual numbers",
      "deep_analysis": "3-5 paragraphs: What do CTR, engagement rate, and video completion tell us? Include industry benchmark context (typical social ad CTR is 0.5-1.5%, engagement 1-5%). Explain what these numbers mean for audience reception. Identify the 'funnel leak' (e.g. high CTR but low video completion = strong hook but weak payoff). Give specific tactical recommendations (e.g. improve first 3 seconds, front-load the value proposition). Reference the exact numbers from the data."
    },
    "cost_efficiency": {
      "one_liner": "A punchy, specific one-liner about cost metrics referencing actual CPC/CPM values",
      "deep_analysis": "3-5 paragraphs: Analyze CPC and CPM in context. Are these competitive for the platform? What does the CPC-to-CTR ratio suggest about ad relevance? If no baseline trend data exists, explain what will become visible with more data. Give specific recommendations for cost optimization."
    },
    "conversion_alignment": {
      "one_liner": "A punchy, specific one-liner about conversion status",
      "deep_analysis": "3-5 paragraphs: If ROAS is not applicable (lead gen campaign), explain what should be tracked instead (cost per lead, lead quality score, form fill rate). If conversion tracking is missing, explain how to implement it. Give specific steps to measure true campaign value beyond revenue attribution."
    },
    "growth_momentum": {
      "one_liner": "A punchy, specific one-liner about growth trajectory",
      "deep_analysis": "3-5 paragraphs: Analyze trend signals. If no baseline exists, explain what trend intelligence will reveal after the next sync cycle. Discuss what metrics to watch and what thresholds would trigger action. Give a growth hypothesis based on current data."
    }
  },
  "strategic_moves": [
    {
      "title": "Short actionable title",
      "reasoning": "Why this matters — reference specific metrics",
      "action_items": ["Specific step 1 that can be done today", "Specific step 2", "Specific step 3"],
      "confidence": "High"
    },
    {
      "title": "Second recommendation",
      "reasoning": "Data-backed reasoning",
      "action_items": ["Step 1", "Step 2"],
      "confidence": "Medium"
    },
    {
      "title": "Third recommendation",
      "reasoning": "Data-backed reasoning",
      "action_items": ["Step 1", "Step 2"],
      "confidence": "Medium"
    }
  ]
}

CRITICAL RULES:
1. Every insight MUST reference ACTUAL numbers from the data. No generic statements.
2. Use the currency from the data exactly (do not convert).
3. If previous_period_available is false, say baseline is building — NEVER fabricate trends.
4. If roas_context.applicable is false, explain why ROAS doesn't apply for the campaign objective.
5. Hero lines must be THREE DIFFERENT perspectives — each must be unique and insightful.
6. Card one-liners must feel like expert commentary, NOT generic labels.
   BAD: "Performance is good" or "Audience response is strong"
   GOOD: "Your 3.62% CTR is crushing the industry average — but 75% of viewers are leaving before your video ends"
7. Deep analysis must feel like a senior strategist speaking — specific, contextual, actionable.
8. Strategic moves: exactly 3, ranked by impact. Each must have 2-3 clear action items.
9. Report confidence score from the data exactly as given.
10. One-liners should be catchy and create curiosity to expand for more details.
"""


# ── Shared Helpers ──


def _get_latest_insight(session: Session, insight_id: Optional[int] = None):
    """Get the latest or specified insight from the database."""
    if insight_id:
        result = session.get(AnalysisResult, insight_id)
    else:
        result = session.exec(
            select(AnalysisResult)
            .order_by(AnalysisResult.created_at.desc())  # type: ignore
            .limit(1)
        ).first()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="No analysis results found. Run /run-analysis first.",
        )
    return json.loads(result.result_json)


def _select_provider(provider_name: str):
    """Select and return an available AI provider.

    When provider_name is 'auto', tries DEFAULT_AI_PROVIDER first,
    then falls through remaining providers.
    """
    providers = {
        "sarvam": SarvamProvider,
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
    }

    if provider_name == "auto":
        # Try the configured default first
        default = settings.default_ai_provider
        if default in providers:
            p = providers[default]()
            if p.is_available():
                return default, p
        # Fall through remaining providers
        for name, cls in providers.items():
            if name == default:
                continue  # already tried
            provider = cls()
            if provider.is_available():
                return name, provider
        raise HTTPException(
            status_code=503,
            detail="No AI provider configured. Set SARVAM_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY in .env.",
        )
    elif provider_name in providers:
        provider = providers[provider_name]()
        if not provider.is_available():
            raise HTTPException(
                status_code=503,
                detail=f"{provider_name} provider not configured.",
            )
        return provider_name, provider
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider_name}.",
        )


# ── Endpoints ──


@router.post("/generate-summary", response_model=SummaryResponse)
async def generate_summary(
    request: SummaryRequest,
    session: Session = Depends(get_session),
):
    """Generate an AI narrative from the latest insight, or answer a specific question."""
    insight_json = _get_latest_insight(session, request.insight_id)
    provider_name, provider = _select_provider(request.provider)

    try:
        summary = await provider.generate_summary(
            insight_json, question=request.question
        )
        return SummaryResponse(
            status="success", provider_used=provider_name, summary=summary
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/generate-intelligence", response_model=IntelligenceResponse)
async def generate_intelligence(
    request: IntelligenceRequest,
    session: Session = Depends(get_session),
):
    """Generate all AI-driven intelligence for the surface in one call.

    Returns hero lines, card insights with deep analysis, and strategic moves.
    One API call powers the entire intelligence surface.
    """
    insight_json = _get_latest_insight(session, request.insight_id)
    provider_name, provider = _select_provider(request.provider)

    data_block = json.dumps(insight_json, indent=2)
    user_prompt = f"Generate intelligence for this advertising data:\n\n{data_block}"

    try:
        raw = ""
        if isinstance(provider, SarvamProvider) and provider.client:
            response = await provider.client.chat.completions(
                messages=[
                    {"role": "system", "content": INTELLIGENCE_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=3000,
            )
            raw = response.choices[0].message.content or "{}"
        elif isinstance(provider, OpenAIProvider) and provider.client:
            response = await provider.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": INTELLIGENCE_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
        elif isinstance(provider, ClaudeProvider) and provider.client:
            response = await provider.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                system=INTELLIGENCE_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text if response.content else "{}"
        else:
            raise RuntimeError("No provider client available")

        # Parse AI JSON response
        # Strip any markdown code fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
        parsed = json.loads(clean)

        hero_lines = parsed.get(
            "hero_lines",
            [
                "Intelligence data available.",
                "Review the signals below.",
                "Analysis complete.",
            ],
        )[:3]

        card_insights = {}
        for card_name in [
            "creative_resonance",
            "cost_efficiency",
            "conversion_alignment",
            "growth_momentum",
        ]:
            ci = parsed.get("card_insights", {}).get(card_name, {})
            card_insights[card_name] = {
                "one_liner": ci.get("one_liner", "Analysis available."),
                "deep_analysis": ci.get("deep_analysis", "Expand for details."),
            }

        strategic_moves = []
        for m in parsed.get("strategic_moves", [])[:3]:
            strategic_moves.append(
                StrategicMove(
                    title=m.get("title", "Recommendation"),
                    reasoning=m.get("reasoning", "Based on current data."),
                    action_items=m.get("action_items", []),
                    confidence=m.get("confidence", "Medium"),
                )
            )

        return IntelligenceResponse(
            status="success",
            provider_used=provider_name,
            hero_lines=hero_lines,
            card_insights=card_insights,
            strategic_moves=strategic_moves,
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI JSON: {e}. Raw: {raw[:300]}")
        return IntelligenceResponse(
            status="partial",
            provider_used=provider_name,
            hero_lines=[
                "Performance data analysed.",
                "Review signals below.",
                "Sync again for trend data.",
            ],
            card_insights={
                k: {"one_liner": "Generating…", "deep_analysis": "Try again."}
                for k in [
                    "creative_resonance",
                    "cost_efficiency",
                    "conversion_alignment",
                    "growth_momentum",
                ]
            },
            strategic_moves=[],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Intelligence generation failed: {str(e)}"
        )
