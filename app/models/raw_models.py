"""MRUDA — Raw Data Models (Immutable)."""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class RawMetaData(SQLModel, table=True):
    """Immutable raw response from Meta API.

    Never modify this data — it's the audit trail.
    """

    __tablename__ = "raw_meta_data"

    id: Optional[int] = Field(default=None, primary_key=True)
    endpoint: str = Field(
        index=True, description="Meta API endpoint that produced this data"
    )
    entity_type: str = Field(index=True, description="campaign | adset | ad | account")
    entity_id: str = Field(default="", description="Meta entity ID")
    date_start: str = Field(default="", description="Reporting date start")
    date_stop: str = Field(default="", description="Reporting date stop")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload_json: str = Field(description="Full raw JSON response")
