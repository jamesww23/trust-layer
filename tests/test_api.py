"""Tests for API endpoint behavior.

These tests verify the thin API layer handles request parsing correctly.
They do NOT test business logic (that's in test_controller.py).
They use io mocks to simulate BaseHTTPRequestHandler I/O.
"""

import json
import io
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_handler(handler_class, method="GET", body=None, headers=None):
    """Simulate a BaseHTTPRequestHandler request without a real socket.

    Returns (handler_instance, response_bytes).
    """
    # Build raw HTTP request
    if body is not None:
        body_bytes = body if isinstance(body, bytes) else body.encode()
    else:
        body_bytes = b""

    path = "/"
    request_line = f"{method} {path} HTTP/1.1\r\n"
    header_lines = f"Content-Length: {len(body_bytes)}\r\n"
    if headers:
        for k, v in headers.items():
            header_lines += f"{k}: {v}\r\n"
    raw_request = (request_line + header_lines + "\r\n").encode() + body_bytes

    # Mock the socket/rfile/wfile
    rfile = io.BytesIO(raw_request)
    wfile = io.BytesIO()

    # BaseHTTPRequestHandler reads from rfile in __init__, so we need to
    # patch __init__ and call the method manually.
    instance = handler_class.__new__(handler_class)
    instance.rfile = io.BytesIO(body_bytes)
    instance.wfile = wfile
    instance.requestline = f"{method} {path} HTTP/1.1"
    instance.command = method
    instance.path = path
    instance.request_version = "HTTP/1.1"
    instance.close_connection = True

    # Mock headers
    from http.client import HTTPMessage
    msg = HTTPMessage()
    msg["Content-Length"] = str(len(body_bytes))
    if headers:
        for k, v in headers.items():
            msg[k] = v
    instance.headers = msg

    # Capture response
    instance._response_code = None
    instance._response_headers = {}

    original_send_response = instance.send_response.__func__ if hasattr(instance.send_response, '__func__') else None

    def mock_send_response(code, message=None):
        instance._response_code = code
        wfile.write(f"HTTP/1.1 {code}\r\n".encode())

    def mock_send_header(key, value):
        instance._response_headers[key] = value
        wfile.write(f"{key}: {value}\r\n".encode())

    def mock_end_headers():
        wfile.write(b"\r\n")

    instance.send_response = mock_send_response
    instance.send_header = mock_send_header
    instance.end_headers = mock_end_headers
    instance.log_message = lambda *args, **kwargs: None  # suppress logs

    # Call the handler method
    handler_method = getattr(instance, f"do_{method}")
    handler_method()

    # Parse response body from wfile
    wfile.seek(0)
    raw_response = wfile.read()
    # Body is after the double \r\n
    parts = raw_response.split(b"\r\n\r\n", 1)
    response_body = parts[1] if len(parts) > 1 else b""

    return instance, response_body


# ---------------------------------------------------------------------------
# Tests: GET /api/health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200_ok(self):
        from api.health import handler as HealthHandler
        instance, body = _make_handler(HealthHandler, method="GET")
        assert instance._response_code == 200
        data = json.loads(body)
        assert data["status"] == "ok"
        assert data["engine"] == "trust-layer"
        assert data["version"] == "1.0"


# ---------------------------------------------------------------------------
# Tests: POST /api/run-demo — malformed JSON handling
# ---------------------------------------------------------------------------

class TestRunDemoMalformedJson:
    """Verify that /api/run-demo returns 400 for malformed JSON bodies."""

    @patch("api.run_demo.RedisStore")
    def test_malformed_json_returns_400(self, mock_store_cls):
        """Broken JSON string should return 400, not 500."""
        from api.run_demo import handler as RunDemoHandler

        instance, body = _make_handler(
            RunDemoHandler, method="POST", body=b"{not valid json"
        )
        assert instance._response_code == 400
        data = json.loads(body)
        assert "Malformed JSON" in data["error"]

    @patch("api.run_demo.RedisStore")
    def test_non_dict_json_returns_400(self, mock_store_cls):
        """Valid JSON but not an object should return 400."""
        from api.run_demo import handler as RunDemoHandler

        instance, body = _make_handler(
            RunDemoHandler, method="POST", body=b'[1, 2, 3]'
        )
        assert instance._response_code == 400
        data = json.loads(body)
        assert "JSON object" in data["error"]

    @patch("api.run_demo.RedisStore")
    def test_empty_body_succeeds(self, mock_store_cls):
        """Empty body (no JSON) should work — it's optional."""
        from api.run_demo import handler as RunDemoHandler

        # Set up mock store
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.is_empty.return_value = False

        # Mock list_all to return seed profiles
        from core.models import AgentProfile
        profiles = [
            AgentProfile("agent_gpt4", "GPT-4", success_rate=0.85, total_runs=20),
            AgentProfile("agent_claude", "Claude", success_rate=0.78, total_runs=15),
            AgentProfile("agent_llama", "LLaMA", success_rate=0.60, total_runs=10),
        ]
        mock_store.list_all.return_value = profiles
        mock_store.lookup.side_effect = lambda aid: next(
            (p for p in profiles if p.agent_id == aid),
            AgentProfile(aid, aid, success_rate=0.5, total_runs=0)
        )

        instance, body = _make_handler(
            RunDemoHandler, method="POST", body=b""
        )
        assert instance._response_code == 200
        data = json.loads(body)
        assert "result" in data
        assert data["result"]["winner_agent_id"] is not None

    @patch("api.run_demo.RedisStore")
    def test_binary_garbage_returns_400(self, mock_store_cls):
        """Non-UTF8 binary should return 400."""
        from api.run_demo import handler as RunDemoHandler

        instance, body = _make_handler(
            RunDemoHandler, method="POST", body=b'\x80\x81\x82\xff'
        )
        assert instance._response_code == 400
        data = json.loads(body)
        assert "Malformed JSON" in data["error"]
