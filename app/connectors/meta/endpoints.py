"""MRUDA — Meta API Endpoints.

Fetch functions for each Meta Marketing API resource.
Each returns raw JSON data and stores it via the raw data layer.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from sqlmodel import Session

from app.connectors.meta.client import MetaClient, META_BASE
from app.models.raw_models import RawMetaData
from app.core.logging import get_logger

logger = get_logger("meta.endpoints")

# Default fields requested from Meta
INSIGHT_FIELDS = (
    "campaign_name,campaign_id,adset_name,adset_id,ad_name,ad_id,"
    "impressions,reach,clicks,unique_clicks,spend,frequency,"
    "ctr,cpc,cpm,cpp,"
    "actions,action_values,cost_per_action_type,"
    "video_avg_time_watched_actions,video_p25_watched_actions,"
    "video_p50_watched_actions,video_p75_watched_actions,"
    "video_p100_watched_actions"
)

CAMPAIGN_FIELDS = (
    "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time"
)
ADSET_FIELDS = "id,name,campaign_id,status,daily_budget,lifetime_budget,targeting,optimization_goal"
AD_FIELDS = "id,name,adset_id,campaign_id,status,creative"


class MetaEndpoints:
    """Fetch raw data from Meta and store in DB."""

    def __init__(self, client: MetaClient, session: Session):
        self.client = client
        self.session = session
        self.ad_account_id = client.ad_account_id

    def _store_raw(
        self,
        endpoint: str,
        entity_type: str,
        entity_id: str,
        date_start: str,
        date_stop: str,
        payload: Any,
    ) -> RawMetaData:
        """Persist raw response to the immutable store."""
        raw = RawMetaData(
            endpoint=endpoint,
            entity_type=entity_type,
            entity_id=entity_id,
            date_start=date_start,
            date_stop=date_stop,
            payload_json=(
                json.dumps(payload) if not isinstance(payload, str) else payload
            ),
        )
        self.session.add(raw)
        return raw

    # ── Account-Level Insights ──

    async def fetch_account_insights(
        self,
        date_start: str,
        date_stop: str,
        time_increment: str = "1",
    ) -> List[Dict[str, Any]]:
        """Fetch account-level insights broken down by day."""
        url = f"{META_BASE}/{self.ad_account_id}/insights"
        params = {
            "fields": INSIGHT_FIELDS,
            "time_range": json.dumps({"since": date_start, "until": date_stop}),
            "time_increment": time_increment,
            "level": "account",
        }
        data = await self.client._paginated_get(url, params)
        self._store_raw(
            "account/insights",
            "account",
            self.ad_account_id,
            date_start,
            date_stop,
            data,
        )
        logger.info(f"Fetched {len(data)} account insight records")
        return data

    # ── Campaign Insights ──

    async def fetch_campaign_insights(
        self,
        date_start: str,
        date_stop: str,
        time_increment: str = "1",
    ) -> List[Dict[str, Any]]:
        """Fetch campaign-level insights broken down by day."""
        url = f"{META_BASE}/{self.ad_account_id}/insights"
        params = {
            "fields": INSIGHT_FIELDS,
            "time_range": json.dumps({"since": date_start, "until": date_stop}),
            "time_increment": time_increment,
            "level": "campaign",
        }
        data = await self.client._paginated_get(url, params)
        self._store_raw(
            "campaign/insights",
            "campaign",
            self.ad_account_id,
            date_start,
            date_stop,
            data,
        )
        logger.info(f"Fetched {len(data)} campaign insight records")
        return data

    # ── Ad Set Insights ──

    async def fetch_adset_insights(
        self,
        date_start: str,
        date_stop: str,
        time_increment: str = "1",
    ) -> List[Dict[str, Any]]:
        """Fetch ad-set-level insights."""
        url = f"{META_BASE}/{self.ad_account_id}/insights"
        params = {
            "fields": INSIGHT_FIELDS,
            "time_range": json.dumps({"since": date_start, "until": date_stop}),
            "time_increment": time_increment,
            "level": "adset",
        }
        data = await self.client._paginated_get(url, params)
        self._store_raw(
            "adset/insights", "adset", self.ad_account_id, date_start, date_stop, data
        )
        logger.info(f"Fetched {len(data)} adset insight records")
        return data

    # ── Ad-Level Insights ──

    async def fetch_ad_insights(
        self,
        date_start: str,
        date_stop: str,
        time_increment: str = "1",
    ) -> List[Dict[str, Any]]:
        """Fetch ad-level insights."""
        url = f"{META_BASE}/{self.ad_account_id}/insights"
        params = {
            "fields": INSIGHT_FIELDS,
            "time_range": json.dumps({"since": date_start, "until": date_stop}),
            "time_increment": time_increment,
            "level": "ad",
        }
        data = await self.client._paginated_get(url, params)
        self._store_raw(
            "ad/insights", "ad", self.ad_account_id, date_start, date_stop, data
        )
        logger.info(f"Fetched {len(data)} ad insight records")
        return data

    # ── Structure Endpoints (Campaigns, Adsets, Ads) ──

    async def fetch_campaigns(self) -> List[Dict[str, Any]]:
        """Fetch campaign structure."""
        url = f"{META_BASE}/{self.ad_account_id}/campaigns"
        params = {"fields": CAMPAIGN_FIELDS, "limit": 500}
        data = await self.client._paginated_get(url, params)
        self._store_raw("campaigns", "campaign", self.ad_account_id, "", "", data)
        return data

    async def fetch_adsets(self) -> List[Dict[str, Any]]:
        """Fetch ad set structure."""
        url = f"{META_BASE}/{self.ad_account_id}/adsets"
        params = {"fields": ADSET_FIELDS, "limit": 500}
        data = await self.client._paginated_get(url, params)
        self._store_raw("adsets", "adset", self.ad_account_id, "", "", data)
        return data

    async def fetch_ads(self) -> List[Dict[str, Any]]:
        """Fetch ad structure."""
        url = f"{META_BASE}/{self.ad_account_id}/ads"
        params = {"fields": AD_FIELDS, "limit": 500}
        data = await self.client._paginated_get(url, params)
        self._store_raw("ads", "ad", self.ad_account_id, "", "", data)
        return data

    def commit(self) -> None:
        """Commit all stored raw data."""
        self.session.commit()
