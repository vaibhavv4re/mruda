"""MRUDA — Analysis API Routes."""

import json
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models.analysis_models import AnalysisResult, InsightOutput
from app.analyzer.pipeline import run_analysis
from app.core.logging import get_logger

logger = get_logger("api.analysis")

router = APIRouter(tags=["Analysis"])


# ── Request / Response Models ──


class RunAnalysisRequest(BaseModel):
    """Request body for POST /run-analysis."""

    date_range: Optional[str] = None
    """One of: "yesterday", "last_7d", "last_14d", "last_30d", "this_month". Overrides start/end dates."""
    start_date: Optional[str] = None
    """Custom start date in YYYY-MM-DD format."""
    end_date: Optional[str] = None
    """Custom end date in YYYY-MM-DD format."""
    force: bool = False
    """Force re-fetch from Meta even if today's data already exists."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"date_range": "last_7d", "force": False},
                {"start_date": "2026-02-01", "end_date": "2026-02-18", "force": False},
            ]
        }
    }


class RunAnalysisResponse(BaseModel):
    """Response for POST /run-analysis."""

    status: str = "success"
    insight: InsightOutput


# ── Endpoints ──


@router.post("/run-analysis", response_model=RunAnalysisResponse)
async def trigger_analysis(
    request: RunAnalysisRequest,
    session: Session = Depends(get_session),
):
    """Trigger a full analysis pipeline run.

    Fetches latest data from Meta, normalizes, runs all engines,
    and returns structured insight JSON.
    """
    try:
        insight = await run_analysis(
            session=session,
            date_range=request.date_range,
            start_date=request.start_date,
            end_date=request.end_date,
            force=request.force,
        )
        return RunAnalysisResponse(status="success", insight=insight)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/insights/latest")
async def get_latest_insight(session: Session = Depends(get_session)):
    """Get the most recent analysis result."""
    result = session.exec(
        select(AnalysisResult)
        .order_by(AnalysisResult.created_at.desc())  # type: ignore
        .limit(1)
    ).first()

    if not result:
        return {"status": "no_data", "message": "No analysis has been run yet."}

    return {
        "status": "success",
        "id": result.id,
        "created_at": result.created_at.isoformat(),
        "schema_version": result.schema_version,
        "insight": json.loads(result.result_json),
    }


@router.get("/insights")
async def get_insights_by_date(
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Get historical analysis results, optionally filtered by date."""
    query = select(AnalysisResult).order_by(AnalysisResult.created_at.desc()).limit(limit)  # type: ignore

    if date:
        query = query.where(AnalysisResult.date_range_end == date)

    results = session.exec(query).all()

    return {
        "status": "success",
        "count": len(results),
        "results": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "schema_version": r.schema_version,
                "date_range": f"{r.date_range_start} → {r.date_range_end}",
                "insight": json.loads(r.result_json),
            }
            for r in results
        ],
    }
