"""MRUDA — Meta API Routes."""

from fastapi import APIRouter, HTTPException

from app.connectors.meta.client import MetaClient, MetaAPIError
from app.core.logging import get_logger

logger = get_logger("api.meta")

router = APIRouter(prefix="/meta", tags=["Meta"])


@router.get("/validate-token")
async def validate_token():
    """Check if the Meta access token is valid.

    Returns validity status, expiration, and granted scopes.
    """
    client = MetaClient()
    try:
        result = await client.validate_token()
        return {
            "status": "success",
            "valid": result["valid"],
            "expires_at": result["expires_at"],
            "scopes": result["scopes"],
            "app_id": result["app_id"],
        }
    except MetaAPIError as e:
        raise HTTPException(
            status_code=400, detail=f"Token validation failed: {str(e)}"
        )
    finally:
        await client.close()


@router.get("/account-info")
async def get_account_info():
    """Fetch ad account details from Meta."""
    client = MetaClient()
    try:
        result = await client.get_account_info()
        return {"status": "success", "account": result}
    except MetaAPIError as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to fetch account info: {str(e)}"
        )
    finally:
        await client.close()
