"""MRUDA — Sarvam AI Provider."""

import json
from typing import Optional
from sarvamai import AsyncSarvamAI

from app.ai.base_provider import AIProvider
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("ai.sarvam")

SYSTEM_PROMPT = """You are a compliance-bound analytics interpreter for MRUDA.

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
            user_prompt = (
                f'The user asks: "{question}"\n\n'
                f"Answer this specific question using ONLY the data below. "
                f"Be concise, direct, and reference specific metrics from the data. "
                f"Do not produce a generic summary — answer the question.\n\n"
                f"Data:\n{data_block}"
            )
        else:
            user_prompt = (
                f"Analyze this data and produce an executive summary:\n\n{data_block}"
            )

        try:
            response = await self.client.chat.completions(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            # Sarvam returns an OpenAI-compatible response structure
            return response.choices[0].message.content or "No summary generated."
        except Exception as e:
            logger.error(f"Sarvam generation failed: {e}")
            raise
