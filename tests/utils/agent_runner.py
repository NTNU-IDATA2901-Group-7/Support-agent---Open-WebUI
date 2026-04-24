"""
Agent runner — sends queries through Open WebUI's chat API and returns structured results.

This is the bridge between LLM-judge tests and the running Open WebUI instance.
It sends a user message through the full pipeline:
    Open WebUI → LLM → MCP tool calls → LLM synthesizes response

Open WebUI only executes tools in the streaming + Socket.IO path. So we:
    1. Sign in to get a JWT (needed for Socket.IO auth)
    2. Connect a Socket.IO client to receive events
    3. POST to /api/chat/completions with stream=True
    4. Collect socket events until the response is done
    5. Parse tool calls from <details type="tool_calls"> HTML in the content

Requires:
    - A running Open WebUI instance
    - OPEN_WEBUI_URL, OPEN_WEBUI_EMAIL, OPEN_WEBUI_PASSWORD env vars
    - The model must have MCP tools assigned via tool_ids
"""

import html
import json
import os
import re
import threading
from dataclasses import dataclass, field
from uuid import uuid4

import httpx
import socketio

OPEN_WEBUI_URL = os.environ.get("OPEN_WEBUI_URL", "http://localhost:8080")
OPEN_WEBUI_EMAIL = os.environ.get("OPEN_WEBUI_EMAIL", "")
OPEN_WEBUI_PASSWORD = os.environ.get("OPEN_WEBUI_PASSWORD", "")
OPEN_WEBUI_MODEL = os.environ.get("OPEN_WEBUI_MODEL", "gpt-4.1-mini")
TOOL_IDS = json.loads(
    os.environ.get("OPEN_WEBUI_TOOL_IDS", '["server:support-agent-tools"]')
)

SOCKET_TIMEOUT = int(os.environ.get("AGENT_RUNNER_TIMEOUT", "60"))


@dataclass
class AgentResult:
    """Structured result from an agent query."""

    answer: str
    tool_calls: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    retrieval_context: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_jwt_token: str | None = None
_user_id: str | None = None


def _get_jwt() -> tuple[str, str]:
    """Sign in to Open WebUI and return (jwt_token, user_id)."""
    global _jwt_token, _user_id
    if _jwt_token and _user_id:
        return _jwt_token, _user_id

    resp = httpx.post(
        f"{OPEN_WEBUI_URL}/api/v1/auths/signin",
        json={"email": OPEN_WEBUI_EMAIL, "password": OPEN_WEBUI_PASSWORD},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _jwt_token = data["token"]
    _user_id = data["id"]
    return _jwt_token, _user_id


# ---------------------------------------------------------------------------
# Parse tool calls from content — same regex as Open WebUI frontend
# (src/lib/utils/index.ts : processDetails)
# ---------------------------------------------------------------------------

_DETAILS_RE = re.compile(
    r'<details\s+type="tool_calls"([^>]*)>[\s\S]*?</details>',
    re.IGNORECASE,
)
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def _parse_tool_calls_from_content(content: str) -> tuple[str, list[dict]]:
    """Extract tool call info from <details type="tool_calls"> blocks.

    Returns (clean_answer, tool_calls).
    """
    tool_calls = []

    for match in _DETAILS_RE.finditer(content):
        attrs = dict(_ATTR_RE.findall(match.group(0)))

        name = attrs.get("name", "")
        done = attrs.get("done", "false") == "true"

        arguments_raw = html.unescape(attrs.get("arguments", "{}"))
        result_raw = html.unescape(attrs.get("result", ""))

        try:
            arguments = json.loads(arguments_raw)
        except (json.JSONDecodeError, ValueError):
            arguments = arguments_raw

        try:
            result = json.loads(result_raw) if result_raw else None
        except (json.JSONDecodeError, ValueError):
            result = result_raw

        tool_calls.append(
            {"name": name, "arguments": arguments, "result": result, "done": done}
        )

    clean = _DETAILS_RE.sub("", content).strip()
    return clean, tool_calls


# ---------------------------------------------------------------------------
# Socket.IO event collector
# ---------------------------------------------------------------------------


class _EventCollector:
    """Connects to Open WebUI's Socket.IO and collects events for a specific message."""

    def __init__(self, token: str, chat_id: str, message_id: str):
        self.token = token
        self.chat_id = chat_id
        self.message_id = message_id

        self.events: list[dict] = []
        self.done = threading.Event()
        self.error: str | None = None

        self._sio = socketio.Client(logger=False, engineio_logger=False)
        self._setup_handlers()

    def _setup_handlers(self):
        sio = self._sio

        @sio.on("events")
        def on_events(data):
            if (
                data.get("chat_id") != self.chat_id
                or data.get("message_id") != self.message_id
            ):
                return

            event_data = data.get("data", {})
            self.events.append(event_data)

            event_type = event_data.get("type", "")

            if event_type == "chat:completion":
                inner = event_data.get("data", {})
                if inner.get("done"):
                    self.done.set()

            if event_type == "chat:message:error":
                self.error = str(
                    event_data.get("data", {}).get("error", "Unknown error")
                )
                self.done.set()

    def connect(self):
        self._sio.connect(
            OPEN_WEBUI_URL,
            auth={"token": self.token},
            transports=["websocket"],
            socketio_path="/ws/socket.io",
            wait_timeout=10,
        )

    def wait(self, timeout: float = SOCKET_TIMEOUT):
        self.done.wait(timeout=timeout)
        if not self.done.is_set():
            self.error = f"Timed out after {timeout}s waiting for response"

    def disconnect(self):
        try:
            self._sio.disconnect()
        except Exception:
            pass

    def get_final_content(self) -> str:
        """Get the last content from chat:completion events."""
        content = ""
        for event in self.events:
            if event.get("type") == "chat:completion":
                inner = event.get("data", {})
                if "content" in inner:
                    content = inner["content"]
        return content

    def get_sources(self) -> list[dict]:
        """Get source events emitted during the response."""
        return [
            event.get("data", {})
            for event in self.events
            if event.get("type") == "source"
        ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run(query: str) -> AgentResult:
    """Send a query through Open WebUI and return the agent's response.

    Uses Socket.IO to receive the full response including tool execution results.
    """
    token, user_id = _get_jwt()

    chat_id = f"test-{uuid4()}"
    message_id = str(uuid4())

    collector = _EventCollector(token, chat_id, message_id)
    collector.connect()

    try:
        payload = {
            "model": OPEN_WEBUI_MODEL,
            "messages": [{"role": "user", "content": query}],
            "stream": True,
            "tool_ids": TOOL_IDS,
            "chat_id": chat_id,
            "id": message_id,
            "session_id": str(uuid4()),
            "params": {"function_calling": "native"},
        }

        resp = httpx.post(
            f"{OPEN_WEBUI_URL}/api/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=SOCKET_TIMEOUT,
        )

        if resp.status_code == 400:
            try:
                body = resp.json()
                error_msg = body.get("error", {}).get("message", "")
            except Exception:
                error_msg = ""
            if (
                "content management policy" in error_msg
                or "content_filter" in error_msg
            ):
                return AgentResult(
                    answer=f"[Blocked by content filter] {error_msg}"
                )
            resp.raise_for_status()

        resp.raise_for_status()

        collector.wait()

        if collector.error:
            return AgentResult(answer=f"[Error] {collector.error}")

        final_content = collector.get_final_content()
        clean_answer, tool_calls = _parse_tool_calls_from_content(final_content)
        sources = collector.get_sources()

        return AgentResult(
            answer=clean_answer,
            tool_calls=tool_calls,
            sources=sources,
            retrieval_context=[
                s.get("document", [""])[0] for s in sources if s.get("document")
            ],
        )

    finally:
        collector.disconnect()


def get_ticket_fields(query: str) -> dict:
    """Send a query and extract ticket classification fields from the response.

    Uses stream=False since no tools are involved — just a plain LLM call.
    """
    token, _ = _get_jwt()

    resp = httpx.post(
        f"{OPEN_WEBUI_URL}/api/chat/completions",
        json={
            "model": OPEN_WEBUI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a ticket classifier. Given a user's issue description, "
                        "respond with ONLY a JSON object containing:\n"
                        '- "priority": one of "critical", "high", "medium", "low"\n'
                        '- "components": a list from ONLY these values: '
                        '"WMS" (warehouse management), "TMS" (transport management), '
                        '"OMS" (order management)\n'
                        "No other text, just the JSON."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "stream": False,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0]
    return json.loads(content)


def close():
    """Clean up resources."""
    pass
