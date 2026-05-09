"""Atlassian OAuth session management for user-specific Jira operations."""

import os
import logging
from datetime import datetime, timedelta

import aiohttp

from open_webui.models.oauth_sessions import OAuthSessions

log = logging.getLogger(__name__)

JIRA_OAUTH_PROVIDER = "atlassian"
ATLASSIAN_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ATLASSIAN_CLIENT_ID = os.environ.get("ATLASSIAN_CLIENT_ID", "")
ATLASSIAN_CLIENT_SECRET = os.environ.get("ATLASSIAN_CLIENT_SECRET", "")
JIRA_CLOUD_ID = os.environ.get("JIRA_CLOUD_ID")

JIRA_OAUTH_BASE_URL = f"https://api.atlassian.com/ex/jira/{JIRA_CLOUD_ID}/rest/api/3"


async def _refresh_jira_token(session) -> dict | None:
    """Refresh an expired Atlassian OAuth token, preserving custom metadata."""
    token_data = session.token
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        log.warning(f"No refresh token for JIRA session {session.id}")
        return None

    refresh_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": ATLASSIAN_CLIENT_ID,
        "client_secret": ATLASSIAN_CLIENT_SECRET,
    }
    try:
        async with aiohttp.ClientSession(trust_env=True) as http:
            async with http.post(
                ATLASSIAN_TOKEN_URL,
                json=refresh_data,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    log.error(
                        f"JIRA token refresh failed: {resp.status} - {error_text}"
                    )
                    return None
                new_token = await resp.json()
    except Exception as e:
        log.error(f"JIRA token refresh exception: {e}")
        return None

    # Preserve refresh_token if the provider didn't return a new one
    if "refresh_token" not in new_token:
        new_token["refresh_token"] = refresh_token

    # Preserve custom metadata stored during initial OAuth
    for key in ("cloud_id", "atlassian_account_id"):
        if key not in new_token and key in token_data:
            new_token[key] = token_data[key]

    new_token["issued_at"] = int(datetime.now().timestamp())
    if "expires_in" in new_token and "expires_at" not in new_token:
        new_token["expires_at"] = int(datetime.now().timestamp()) + int(
            new_token["expires_in"]
        )

    updated = OAuthSessions.update_session_by_id(session.id, new_token)
    if updated:
        log.info(f"Refreshed JIRA token for session {session.id}")
        return updated.token
    return None


async def get_jira_session(user_id: str):
    """
    Get a valid Atlassian OAuthSession for the user,
    refreshing automatically if close to expiry.

    Returns the OAuthSessionModel or None.
    """
    session = OAuthSessions.get_session_by_provider_and_user_id(
        JIRA_OAUTH_PROVIDER, user_id
    )
    if not session:
        log.warning(f"No JIRA OAuth session for user {user_id}")
        return None

    # Refresh if expiring within 5 minutes
    if datetime.now() + timedelta(minutes=5) >= datetime.fromtimestamp(
        session.expires_at
    ):
        log.debug(f"JIRA token near expiry for user {user_id}, refreshing")
        refreshed = await _refresh_jira_token(session)
        if refreshed:
            # Re-fetch the updated session
            session = OAuthSessions.get_session_by_provider_and_user_id(
                JIRA_OAUTH_PROVIDER, user_id
            )
            if session:
                return session
        # Refresh failed – delete stale session
        OAuthSessions.delete_session_by_id(session.id)
        log.warning(f"JIRA token refresh failed for user {user_id}, session deleted")
        return None

    return session
