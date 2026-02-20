"""MRUDA — Meta API Client.

Handles authentication, retry logic, rate limiting, and pagination.
"""

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger("meta.client")

META_BASE = f"{settings.meta_base_url}/{settings.meta_api_version}"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds


class MetaAPIError(Exception):
    """Raised when Meta API returns an error."""

    def __init__(self, message: str, status_code: int = 0, error_code: int = 0):
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class MetaClient:
    """Async HTTP client for Meta Marketing API."""

    def __init__(
        self, access_token: str | None = None, ad_account_id: str | None = None
    ):
        self.access_token = access_token or settings.meta_access_token
        self.ad_account_id = ad_account_id or settings.meta_ad_account_id
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Core Request Method ──

    async def _request(
        self,
        method: str,
        url: str,
        params: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Make a request with retry + rate-limit handling."""
        params = params or {}
        params["access_token"] = self.access_token

        client = await self._get_client()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await client.request(method, url, params=params)

                # Rate limited
                if resp.status_code == 429:
                    wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"Rate limited (429). Retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError as e:
                body = (
                    e.response.json()
                    if e.response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                error_msg = body.get("error", {}).get("message", str(e))
                error_code = body.get("error", {}).get("code", 0)

                if attempt < MAX_RETRIES and e.response.status_code >= 500:
                    wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"Server error {e.response.status_code}. Retrying in {wait}s"
                    )
                    await asyncio.sleep(wait)
                    continue

                raise MetaAPIError(error_msg, e.response.status_code, error_code) from e

            except httpx.RequestError as e:
                if attempt < MAX_RETRIES:
                    wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(f"Request error: {e}. Retrying in {wait}s")
                    await asyncio.sleep(wait)
                    continue
                raise MetaAPIError(
                    f"Connection failed after {MAX_RETRIES} retries: {e}"
                ) from e

        raise MetaAPIError("Max retries exhausted")

    # ── Pagination ──

    async def _paginated_get(
        self,
        url: str,
        params: Dict[str, Any] | None = None,
        max_pages: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch all pages of a paginated endpoint."""
        all_data: List[Dict[str, Any]] = []
        params = params or {}
        current_url = url

        for page in range(max_pages):
            result = await self._request(
                "GET", current_url, params if page == 0 else None
            )
            data = result.get("data", [])
            all_data.extend(data)

            # Check for next page
            paging = result.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break
            current_url = next_url

        logger.info(f"Fetched {len(all_data)} records from {url}")
        return all_data

    # ── Token Validation ──

    async def validate_token(self) -> Dict[str, Any]:
        """Check if the access token is valid and return metadata."""
        url = f"{META_BASE}/debug_token"
        params = {"input_token": self.access_token}
        result = await self._request("GET", url, params)
        token_data = result.get("data", {})
        return {
            "valid": token_data.get("is_valid", False),
            "expires_at": token_data.get("expires_at", 0),
            "scopes": token_data.get("scopes", []),
            "app_id": token_data.get("app_id", ""),
        }

    # ── Account Info ──

    async def get_account_info(self) -> Dict[str, Any]:
        """Fetch ad account details."""
        url = f"{META_BASE}/{self.ad_account_id}"
        params = {
            "fields": "name,account_id,account_status,currency,timezone_name,balance"
        }
        return await self._request("GET", url, params)

    async def fetch_currency(self) -> str:
        """Fetch account currency from Meta API. Falls back to config default."""
        try:
            url = f"{META_BASE}/{self.ad_account_id}"
            params = {"fields": "currency"}
            result = await self._request("GET", url, params)
            currency = result.get("currency", "")
            if currency:
                logger.info(f"Account currency from Meta: {currency}")
                return currency
        except Exception as e:
            logger.warning(f"Could not fetch currency from Meta: {e}")
        return settings.account_currency
