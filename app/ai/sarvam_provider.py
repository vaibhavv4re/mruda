"""MRUDA — Sarvam AI Provider."""

import json
from typing import Optional
from sarvamai import AsyncSarvamAI

from app.ai.base_provider import AIProvider
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("ai.sarvam")

# ── Strict data-interpretation prompt (for summaries) ──
SUMMARY_PROMPT = """You are a compliance-bound analytics interpreter for MRUDA.

You are reading audited, pre-computed business metrics. Your job is INTERPRETATION ONLY.

STRICT RULES — VIOLATION IS FAILURE:

1. NEVER calculate, derive, estimate, round, or modify numeric values.
2. NEVER convert currency. Use the "currency" field from the data exactly as provided.
3. NEVER reinterpret or recompute the confidence_score. Report it exactly as given.
4. If a trend's previous_period_available is false, state: "No prior baseline available for comparison." Do NOT interpret it as an increase or decrease.
5. If roas_context.applicable is false, explain that ROAS is not applicable and state the reason provided. Do NOT call it a failure.
6. If data is insufficient, say so explicitly. Do NOT fabricate analysis.
7. Report numeric values EXACTLY as they appear in the data. No rounding. No recomputation.
8. Do NOT introduce any new numbers not present in the data.
9. Do NOT infer missing metrics or assume values.
10. If uncertain, state uncertainty rather than guessing.

FORMAT RULES:
- Lead with the most important finding
- Use bullet points for clarity
- Keep it under 500 words
- Be direct and actionable
- Always state: "Confidence Score: {exact value from data}"
"""

# ── Strategic advisor prompt (for user questions) ──
QA_PROMPT = """You are MRUDA, an expert digital advertising strategist and analyst.

You have access to real campaign performance data. Use it to give specific, actionable, and strategic answers.

WHEN ANSWERING QUESTIONS:
1. Reference actual metrics from the data (CTR, CPC, CPM, spend, clicks, etc.) to support your answer.
2. Be STRATEGIC and CREATIVE — go beyond just reading numbers. Provide real marketing insights.
3. If asked for campaign ideas, new strategies, or recommendations, give SPECIFIC and ACTIONABLE suggestions grounded in the data patterns you see.
4. For budget questions, reference actual spend and cost metrics from the data.
5. When currency values appear in the data, use them exactly as shown.
6. If data is insufficient for the specific question, say so and suggest what data would help.
7. If the question is about future campaigns, use the current data as a baseline to inform your recommendations.

TONE: Speak like a senior marketing strategist — confident, specific, data-informed, and actionable.
Keep answers concise but thorough. Use bullet points where helpful.
"""


class SarvamProvider(AIProvider):
    """Sarvam AI provider for narrative generation (model: sarvam-m)."""

    def __init__(self):
        self.client = (
            AsyncSarvamAI(api_subscription_key=settings.sarvam_api_key)
            if settings.sarvam_api_key
            else None
        )

    def is_available(self) -> bool:
        return self.client is not None and bool(settings.sarvam_api_key)

    async def generate_summary(
        self, insight_json: dict, question: Optional[str] = None
    ) -> str:
        if not self.is_available():
            raise RuntimeError("Sarvam provider not configured")

        data_block = json.dumps(insight_json, indent=2)

        if question:
            system_prompt = QA_PROMPT
            user_prompt = (
                f'The user asks: "{question}"\n\n'
                f"Use the campaign performance data below to give a specific, "
                f"strategic, and actionable answer. Reference actual metrics "
                f"where relevant, but focus on answering the question with "
                f"real marketing insight.\n\n"
                f"Campaign Data:\n{data_block}"
            )
        else:
            system_prompt = SUMMARY_PROMPT
            user_prompt = (
                f"Analyze this data and produce an executive summary:\n\n{data_block}"
            )

        try:
            response = await self.client.chat.completions(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5 if question else 0.3,
                max_tokens=1500 if question else 1000,
            )
            return response.choices[0].message.content or "No summary generated."
        except Exception as e:
            logger.error(f"Sarvam generation failed: {e}")
            raise
