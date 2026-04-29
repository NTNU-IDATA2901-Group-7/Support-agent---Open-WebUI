import os
import logging
from base64 import b64encode

from httpx import AsyncClient

log = logging.getLogger(__name__)

JIRA_API_BASE_URL = os.environ.get("JIRA_API_BASE_URL")
JIRA_SERVICE_ACCOUNT_EMAIL = os.environ.get("JIRA_SERVICE_ACCOUNT_EMAIL")
JIRA_SERVICE_ACCOUNT_API_TOKEN = os.environ.get("JIRA_SERVICE_ACCOUNT_API_TOKEN")


def get_jira_headers() -> dict[str, str]:
    basic_credentials = b64encode(
        f"{JIRA_SERVICE_ACCOUNT_EMAIL}:{JIRA_SERVICE_ACCOUNT_API_TOKEN}".encode()
    ).decode()
    return {
        "Authorization": f"Basic {basic_credentials}",
        "Accept": "application/json",
    }


def get_jira_url(path: str) -> str:
    return f"{JIRA_API_BASE_URL}{path}"


async def jira_api_get(path: str, params: dict | None = None) -> dict:
    """Perform an authenticated Jira GET request and return parsed JSON."""
    try:
        async with AsyncClient() as client:
            response = await client.get(
                get_jira_url(path),
                headers=get_jira_headers(),
                params=params,
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log.exception(f"Jira GET request failed for {path}: {e}")
        raise
