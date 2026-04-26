"""
Unit tests for aitrustlayer SDK.

Run with: pytest test_client.py
"""

import unittest
from unittest.mock import patch, MagicMock
from aitrustlayer import (
    TrustClient, Agent, Task, FeedbackResponse, ValidationError,
    NotFoundError, ConnectionError, validate_score, parse_skill_keywords,
)


class TestTrustClient(unittest.TestCase):
    """Test cases for TrustClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = TrustClient("https://test.example.com")
        self.sample_agent = {
            "agent_id": "test_agent",
            "agent_name": "Test Agent",
            "skill_md": "Test skills",
            "trust_score": 0.75,
            "tasks_completed": 5,
            "tasks_received": 6,
            "ratings_count": 5,
        }

    def test_client_initialization(self):
        """Test client initialization."""
        client = TrustClient("https://example.com")
        self.assertEqual(client.base_url, "https://example.com")
        self.assertEqual(client.timeout, 30)

    def test_client_initialization_with_timeout(self):
        """Test client initialization with custom timeout."""
        client = TrustClient("https://example.com", timeout=60)
        self.assertEqual(client.timeout, 60)

    def test_base_url_trailing_slash_removed(self):
        """Test that trailing slashes are removed from base URL."""
        client = TrustClient("https://example.com/")
        self.assertEqual(client.base_url, "https://example.com")

    @patch("urllib.request.urlopen")
    def test_get_agents(self, mock_urlopen):
        """Test getting all agents."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"agents": [' + \
            b'{"agent_id": "a1", "agent_name": "Agent 1", "skill_md": "skills", "trust_score": 0.8, "tasks_completed": 5, "tasks_received": 6, "ratings_count": 5}' + \
            b']}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        agents = self.client.get_agents()
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_id, "a1")

    @patch("urllib.request.urlopen")
    def test_discover_agents(self, mock_urlopen):
        """Test discovering agents by keyword."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"results": [' + \
            b'{"agent_id": "data_1", "agent_name": "Data Agent", "skill_md": "data analysis", "trust_score": 0.7, "tasks_completed": 3, "tasks_received": 4, "ratings_count": 3}' + \
            b']}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        results = self.client.discover("data analysis")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].agent_id, "data_1")

    def test_submit_feedback_validates_score(self):
        """Test that submit_feedback validates score range."""
        with self.assertRaises(ValidationError):
            self.client.submit_feedback("agent", 1.5, True)

        with self.assertRaises(ValidationError):
            self.client.submit_feedback("agent", -0.1, True)

    def test_validate_score_utility(self):
        """Test the validate_score utility function."""
        self.assertTrue(validate_score(0.0))
        self.assertTrue(validate_score(0.5))
        self.assertTrue(validate_score(1.0))
        self.assertFalse(validate_score(-0.1))
        self.assertFalse(validate_score(1.5))
        self.assertFalse(validate_score("0.5"))

    def test_parse_skill_keywords(self):
        """Test skill keyword parsing."""
        skill_md = """
        # Capabilities
        - Python programming
        - Machine learning and AI
        - Data analysis with SQL
        """

        keywords = parse_skill_keywords(skill_md)
        self.assertIn("python", keywords)
        self.assertIn("machine", keywords)
        self.assertIn("learning", keywords)
        self.assertIn("sql", keywords)
        self.assertNotIn("and", keywords)  # Common word filtered

    def test_agent_model_from_dict(self):
        """Test Agent model creation from dictionary."""
        agent = Agent.from_dict(self.sample_agent)
        self.assertEqual(agent.agent_id, "test_agent")
        self.assertEqual(agent.agent_name, "Test Agent")
        self.assertEqual(agent.trust_score, 0.75)

    def test_task_model_from_dict(self):
        """Test Task model creation from dictionary."""
        task_data = {
            "task_id": "task_1",
            "requester_id": "req_1",
            "provider_id": "prov_1",
            "description": "Test task",
            "status": "pending",
        }
        task = Task.from_dict(task_data)
        self.assertEqual(task.task_id, "task_1")
        self.assertEqual(task.status, "pending")

    def test_feedback_response_model(self):
        """Test FeedbackResponse model."""
        feedback_data = {
            "status": "feedback_recorded",
            "trust_before": 0.6,
            "trust_after": 0.75,
            "message": "Trust updated",
        }
        feedback = FeedbackResponse.from_dict(feedback_data)
        self.assertEqual(feedback.trust_before, 0.6)
        self.assertEqual(feedback.trust_after, 0.75)

    @patch("urllib.request.urlopen")
    def test_connection_error_handling(self, mock_urlopen):
        """Test connection error handling."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Connection refused")

        with self.assertRaises(ConnectionError):
            self.client.get_agents()

    @patch("urllib.request.urlopen")
    def test_not_found_error_handling(self, mock_urlopen):
        """Test 404 error handling."""
        from urllib.error import HTTPError
        mock_error = HTTPError(
            "https://test.example.com/api/agents",
            404,
            "Not Found",
            {},
            None
        )
        mock_error.read = MagicMock(return_value=b'{"error": "Agent not found"}')
        mock_urlopen.side_effect = mock_error

        with self.assertRaises(NotFoundError):
            self.client.get_agent("nonexistent")

    def test_leaderboard_sorting(self):
        """Test leaderboard sorting by trust score."""
        agents = [
            Agent(agent_id="a", agent_name="A", skill_md="", trust_score=0.5),
            Agent(agent_id="b", agent_name="B", skill_md="", trust_score=0.9),
            Agent(agent_id="c", agent_name="C", skill_md="", trust_score=0.7),
        ]

        # Mock get_agents to return our test agents
        with patch.object(self.client, 'get_agents', return_value=agents):
            leaderboard = self.client.leaderboard(limit=3)
            self.assertEqual(leaderboard[0].agent_id, "b")  # 0.9
            self.assertEqual(leaderboard[1].agent_id, "c")  # 0.7
            self.assertEqual(leaderboard[2].agent_id, "a")  # 0.5


class TestPortabilityMethods(unittest.TestCase):
    """Test the cross-instance export_blob / import_blob methods."""

    def setUp(self):
        self.client = TrustClient("https://test.example.com")

    @patch("urllib.request.urlopen")
    def test_export_blob_returns_payload(self, mock_urlopen):
        """export_blob hits /api/export and returns the parsed JSON."""
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b'{"format_version":"1.0","agent":{"agent_id":"alice"},'
            b'"task_history":[],"signature":"sha256:abc"}'
        )
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        blob = self.client.export_blob("alice")

        self.assertEqual(blob["format_version"], "1.0")
        self.assertEqual(blob["agent"]["agent_id"], "alice")
        self.assertTrue(blob["signature"].startswith("sha256:"))

        # Verify the URL the SDK actually requested
        called_request = mock_urlopen.call_args[0][0]
        self.assertIn("/api/export?agent_id=alice", called_request.full_url)
        self.assertEqual(called_request.get_method(), "GET")

    @patch("urllib.request.urlopen")
    def test_import_blob_posts_payload(self, mock_urlopen):
        """import_blob POSTs to /api/import with blob + flags."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status":"imported","agent_id":"alice"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        blob = {"format_version": "1.0", "agent": {"agent_id": "alice"}}
        result = self.client.import_blob(blob, overwrite=True, apply_decay=False)

        self.assertEqual(result["status"], "imported")

        # Verify the POST body contains our blob and flags
        called_request = mock_urlopen.call_args[0][0]
        self.assertIn("/api/import", called_request.full_url)
        self.assertEqual(called_request.get_method(), "POST")
        import json as _json
        body = _json.loads(called_request.data.decode())
        self.assertEqual(body["blob"], blob)
        self.assertTrue(body["overwrite"])
        self.assertFalse(body["apply_decay"])

    @patch("urllib.request.urlopen")
    def test_import_blob_defaults(self, mock_urlopen):
        """Default flags: overwrite=False, apply_decay=True."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status":"imported"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        self.client.import_blob({"any": "blob"})

        import json as _json
        body = _json.loads(mock_urlopen.call_args[0][0].data.decode())
        self.assertFalse(body["overwrite"])
        self.assertTrue(body["apply_decay"])


class TestModels(unittest.TestCase):
    """Test cases for data models."""

    def test_agent_to_dict(self):
        """Test Agent.to_dict()."""
        agent = Agent(
            agent_id="test",
            agent_name="Test",
            skill_md="Skills",
            trust_score=0.8,
        )
        data = agent.to_dict()
        self.assertEqual(data["agent_id"], "test")
        self.assertEqual(data["trust_score"], 0.8)

    def test_task_to_dict(self):
        """Test Task.to_dict()."""
        task = Task(
            task_id="t1",
            requester_id="r1",
            provider_id="p1",
            description="Test",
            status="pending",
        )
        data = task.to_dict()
        self.assertEqual(data["task_id"], "t1")
        self.assertEqual(data["status"], "pending")


if __name__ == "__main__":
    unittest.main()
