"""
Agent runner — sends queries through Open WebUI's chat API and returns structured results.

This is the bridge between LLM-judge tests and the running Open WebUI instance.
It sends a user message through the full pipeline:
    Open WebUI → LLM → MCP tool calls → LLM synthesizes response

The response includes the final answer, any tool calls made, and source citations.

Requires:
    - A running Open WebUI instance
    - OPEN_WEBUI_URL and OPEN_WEBUI_API_KEY env vars (or defaults)
    - The model must have MCP tools assigned via tool_ids
"""

import json
import os
from dataclasses import dataclass, field

import httpx

OPEN_WEBUI_URL = os.environ.get("OPEN_WEBUI_URL", "http://localhost:8080")
OPEN_WEBUI_API_KEY = os.environ.get("OPEN_WEBUI_API_KEY", "")
OPEN_WEBUI_MODEL = os.environ.get("OPEN_WEBUI_MODEL", "gpt-4.1-mini")
TOOL_IDS = json.loads(os.environ.get("OPEN_WEBUI_TOOL_IDS", '["server:mcp:support-agent-tools"]'))

_client = httpx.Client(
    base_url=OPEN_WEBUI_URL,
    headers={"Authorization": f"Bearer {OPEN_WEBUI_API_KEY}"},
    timeout=120,
)


@dataclass
class AgentResult:
    """Structured result from an agent query."""
    answer: str
    tool_calls: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    retrieval_context: list[str] = field(default_factory=list)


def run(query: str) -> AgentResult:
    """Send a query through Open WebUI and return the agent's response.

    Posts to /api/chat/completions with the configured model and tool_ids.
    Open WebUI's middleware handles tool execution (MCP calls) and returns
    the final LLM response with citations.
    """
    payload = {
        "model": OPEN_WEBUI_MODEL,
        "messages": [{"role": "user", "content": query}],
        "stream": False,
        "tool_ids": TOOL_IDS,
    }

    resp = _client.post("/api/chat/completions", json=payload)

    if resp.status_code == 400:
        try:
            body = resp.json()
            error_msg = body.get("error", {}).get("message", "")
        except Exception:
            error_msg = ""
        if "content management policy" in error_msg or "content_filter" in error_msg:
            return AgentResult(
                answer=f"[Blocked by content filter] {error_msg}"
            )
        resp.raise_for_status()

    resp.raise_for_status()
    data = resp.json()

    choice = data["choices"][0]
    message = choice["message"]

    return AgentResult(
        answer=message.get("content", ""),
        tool_calls=message.get("tool_calls", []),
        sources=data.get("sources", []),
        retrieval_context=[
            source.get("document", [""])[0]
            for source in data.get("sources", [])
            if source.get("document")
        ],
    )


def get_ticket_fields(query: str) -> dict:
    """Send a query and extract ticket classification fields from the response.

    Used by test_ticket_fields.py to test priority and component extraction.
    Expects the LLM to return a JSON object with 'priority' and 'components'.
    """
    payload = {
        "model": OPEN_WEBUI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a ticket classifier. Given a user's issue description, "
                    "respond with ONLY a JSON object containing:\n"
                    '- "priority": one of "critical", "high", "medium", "low"\n'
                    '- "components": a list from ONLY these values: '
                    '"WMS" (warehouse management), "TMS" (transport management), "OMS" (order management)\n'
                    "No other text, just the JSON."
                ),
            },
            {"role": "user", "content": query},
        ],
        "stream": False,
    }

    resp = _client.post("/api/chat/completions", json=payload)
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    # Strip markdown code fences the LLM sometimes wraps around JSON
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # remove ```json line
        content = content.rsplit("```", 1)[0]  # remove closing ```
    return json.loads(content)


def close():
    """Clean up the HTTP client."""
    _client.close()
