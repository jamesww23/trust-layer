"""Main client for interacting with the trust layer API."""

import json
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

from .models import (
    Agent, Task, ActivityEvent, RegistrationResponse, DelegationResponse,
    SubmitResultResponse, FeedbackResponse, VouchResponse, Leaderboard
)
from .exceptions import (
    TrustLayerError, ConnectionError, ServerError, ClientError,
    NotFoundError, ValidationError, TrustGateError, FeedbackRequired,
    TimeoutError
)


class TrustClient:
    """Client for interacting with the Agentic Reputation Infrastructure Layer."""

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize the TrustClient.

        Args:
            base_url: Base URL of the trust layer server (e.g., https://aitrustlayer.vercel.app)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an HTTP request to the trust layer API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /api/register-agent)
            data: Request body data (for POST requests)

        Returns:
            Response JSON as dictionary

        Raises:
            TrustLayerError: For any request error
        """
        url = self.base_url + path
        headers = {"Content-Type": "application/json"}

        request_data = None
        if data is not None:
            request_data = json.dumps(data).encode()

        try:
            req = urllib.request.Request(
                url, data=request_data, headers=headers, method=method
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode())

        except urllib.error.HTTPError as e:
            status_code = e.code
            try:
                error_data = json.loads(e.read().decode())
                error_msg = error_data.get("error", str(e))
            except Exception:
                error_msg = str(e)

            if status_code == 404:
                raise NotFoundError(error_msg)
            elif status_code == 400:
                # Check if it's a trust gate error or feedback required error
                if "trust" in error_msg.lower():
                    raise TrustGateError(error_msg)
                elif "feedback required" in error_msg.lower():
                    raise FeedbackRequired(error_msg)
                else:
                    raise ValidationError(error_msg)
            elif status_code == 409:
                raise ClientError(error_msg)
            elif 400 <= status_code < 500:
                raise ClientError(error_msg)
            elif status_code >= 500:
                raise ServerError(error_msg)
            else:
                raise TrustLayerError(error_msg)

        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to connect to {self.base_url}: {str(e)}")
        except Exception as e:
            if "timeout" in str(e).lower():
                raise TimeoutError(f"Request timed out after {self.timeout}s: {str(e)}")
            raise TrustLayerError(f"Request failed: {str(e)}")

    def register(self, agent_id: str, agent_name: str, skill_md: str) -> RegistrationResponse:
        """
        Register a new agent.

        Args:
            agent_id: Unique identifier for the agent
            agent_name: Human-readable name for the agent
            skill_md: Markdown document describing the agent's capabilities

        Returns:
            RegistrationResponse with the registered agent

        Raises:
            ClientError: If registration fails
        """
        data = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "skill_md": skill_md,
        }
        response = self._request("POST", "/api/register-agent", data)
        return RegistrationResponse.from_dict(response)

    def get_agent(self, agent_id: str) -> Agent:
        """
        Get a specific agent by ID.

        Args:
            agent_id: Agent ID to retrieve

        Returns:
            Agent object

        Raises:
            NotFoundError: If agent is not found
        """
        # Some deployments return the full agent list and ignore agent_id; always pick by id.
        params = urlencode({"agent_id": agent_id})
        response = self._request("GET", f"/api/agents?{params}")
        agents = response.get("agents", [])
        for raw in agents:
            if raw.get("agent_id") == agent_id:
                return Agent.from_dict(raw)
        raise NotFoundError(f"Agent '{agent_id}' not found")

    def get_agents(self) -> List[Agent]:
        """
        Get all registered agents.

        Returns:
            List of all agents
        """
        response = self._request("GET", "/api/agents")
        return [Agent.from_dict(a) for a in response.get("agents", [])]

    def discover(self, keyword: str) -> List[Agent]:
        """
        Discover agents by keyword.

        Args:
            keyword: Keyword to search agent skills (supports multiple keywords separated by spaces)

        Returns:
            List of matching agents sorted by relevance
        """
        params = urlencode({"keyword": keyword})
        response = self._request("GET", f"/api/discover?{params}")
        return [Agent.from_dict(a) for a in response.get("results", [])]

    def delegate_task(
        self,
        requester_id: str,
        provider_id: str,
        description: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> DelegationResponse:
        """
        Delegate a task to an agent.

        Args:
            requester_id: ID of the agent requesting the task
            provider_id: ID of the agent providing the service
            description: Task description
            payload: Optional task payload (custom data for the provider)

        Returns:
            DelegationResponse with the created task

        Raises:
            TrustGateError: If provider trust is below threshold
            FeedbackRequired: If requester has unrated completed tasks
            NotFoundError: If either agent doesn't exist
        """
        data = {
            "requester_id": requester_id,
            "provider_id": provider_id,
            "description": description,
        }
        if payload is not None:
            data["payload"] = payload

        response = self._request("POST", "/api/delegate-task", data)
        return DelegationResponse.from_dict(response)

    def get_tasks(
        self,
        agent_id: str,
        role: str = "provider",
        status: Optional[str] = None
    ) -> List[Task]:
        """
        Get tasks for an agent.

        Args:
            agent_id: Agent ID
            role: Role of the agent - 'provider' (inbox, default) or 'requester' (sent tasks)
            status: Optional status filter - 'pending', 'completed', 'rated'

        Returns:
            List of tasks for the agent
        """
        params = {"agent_id": agent_id, "role": role}
        if status:
            params["status"] = status

        params_str = urlencode(params)
        response = self._request("GET", f"/api/tasks?{params_str}")
        return [Task.from_dict(t) for t in response.get("tasks", [])]

    def submit_result(self, task_id: str, result: Dict[str, Any]) -> SubmitResultResponse:
        """
        Submit a result for a delegated task.

        Args:
            task_id: ID of the task to submit result for
            result: Result data (dictionary with the task output)

        Returns:
            SubmitResultResponse with updated task

        Raises:
            NotFoundError: If task is not found
            ClientError: If task is already completed
        """
        data = {
            "task_id": task_id,
            "result": result,
        }
        response = self._request("POST", "/api/submit-result", data)
        return SubmitResultResponse.from_dict(response)

    def submit_feedback(
        self,
        agent_id: str,
        score: float,
        fulfilled: bool,
        task_id: Optional[str] = None,
        rated_by: Optional[str] = None
    ) -> FeedbackResponse:
        """
        Submit feedback for a completed task.

        Args:
            agent_id: ID of the agent being rated
            score: Feedback score (0.0 to 1.0)
            fulfilled: Whether the task was fulfilled/completed (required)
            task_id: Optional ID of the specific task
            rated_by: Optional ID of the agent giving the rating

        Returns:
            FeedbackResponse with trust score update

        Raises:
            ValidationError: If score is not in valid range
        """
        if not (0.0 <= score <= 1.0):
            raise ValidationError(f"Score must be between 0.0 and 1.0, got {score}")

        data = {
            "agent_id": agent_id,
            "score": score,
            "fulfilled": fulfilled,
        }
        if task_id is not None:
            data["task_id"] = task_id
        if rated_by is not None:
            data["rated_by"] = rated_by

        response = self._request("POST", "/api/submit-feedback", data)
        return FeedbackResponse.from_dict(response)

    def vouch(self, voucher_id: str, target_id: str) -> VouchResponse:
        """
        Vouch for another agent (requires voucher to have high trust).

        Args:
            voucher_id: ID of the agent vouching
            target_id: ID of the agent being vouched for

        Returns:
            VouchResponse with updated trust scores

        Raises:
            ClientError: If voucher doesn't have sufficient trust or already vouched
        """
        data = {
            "voucher_id": voucher_id,
            "target_id": target_id,
        }
        response = self._request("POST", "/api/vouch", data)
        return VouchResponse.from_dict(response)

    def get_activity(self) -> List[ActivityEvent]:
        """
        Get recent task activity events.

        Returns:
            List of recent activity events (up to 20 most recent)
        """
        response = self._request("GET", "/api/activity")
        return [ActivityEvent.from_dict(e) for e in response.get("activity", [])]

    def health(self) -> Dict[str, Any]:
        """
        Check the health of the trust layer server.

        Returns:
            Health status information

        Raises:
            ConnectionError: If server is unavailable
        """
        try:
            response = self._request("GET", "/api/agents")
            return {
                "status": "ok",
                "agents_count": len(response.get("agents", [])),
            }
        except Exception as e:
            raise ConnectionError(f"Server health check failed: {str(e)}")

    def leaderboard(self, limit: int = 10) -> List[Agent]:
        """
        Get the trust leaderboard (agents sorted by trust score).

        Args:
            limit: Maximum number of agents to return

        Returns:
            List of agents sorted by trust score (descending)
        """
        agents = self.get_agents()
        # Sort by trust_score descending
        agents.sort(key=lambda a: a.trust_score, reverse=True)
        return agents[:limit]

    def export_reputation(self, agent_id: str) -> Dict[str, Any]:
        """
        Export reputation data for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Dictionary with reputation metrics
        """
        agent = self.get_agent(agent_id)
        return {
            "agent_id": agent.agent_id,
            "agent_name": agent.agent_name,
            "trust_score": agent.trust_score,
            "tasks_completed": agent.tasks_completed,
            "tasks_received": agent.tasks_received,
            "ratings_count": agent.ratings_count,
            "avg_rating": sum(agent.ratings) / len(agent.ratings) if agent.ratings else 0.0,
            "completion_rate": agent.completion_rate,
            "avg_latency_ms": agent.avg_latency_ms,
            "components": {
                "feedback_score": agent.wfs,
                "success_rate": agent.tsr,
                "reliability": agent.rh,
                "specialization": agent.ss,
            },
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }

    # ------------------------------------------------------------------
    # Portable reputation: cross-instance export / import
    # ------------------------------------------------------------------

    def export_blob(self, agent_id: str) -> Dict[str, Any]:
        """Fetch a signed, portable reputation blob from the server.

        Calls ``GET /api/export?agent_id=...``. The returned dict is a
        self-describing JSON payload (format_version, agent state, rated
        task history, sha256 signature) that another trust-layer instance
        can ingest via :py:meth:`import_blob`.

        Use this for cross-instance migration; for a client-side metrics
        summary, use :py:meth:`export_reputation` instead.

        Args:
            agent_id: Agent to export

        Returns:
            The signed export blob (suitable for ``json.dumps``)

        Raises:
            NotFoundError: If the agent does not exist on this instance
        """
        params = urlencode({"agent_id": agent_id})
        return self._request("GET", f"/api/export?{params}")

    def import_blob(
        self,
        blob: Dict[str, Any],
        overwrite: bool = False,
        apply_decay: bool = True,
    ) -> Dict[str, Any]:
        """Import a reputation blob produced by another trust-layer instance.

        Calls ``POST /api/import``. The server verifies the blob's
        signature, rejects malformed or tampered payloads, and (by default)
        halves imported rating weights so the agent's trust score starts
        capped and rebuilds via local activity.

        Args:
            blob:        the export dict returned by :py:meth:`export_blob`
                         (or fetched from another instance's /api/export)
            overwrite:   if True, replace an existing agent with the same id;
                         if False (default), duplicates raise ClientError
            apply_decay: if True (default), halve imported rating weights
                         to prevent reputation poisoning across instances

        Returns:
            Server response describing the imported agent
            (agent_id, applied_trust, ratings_imported, source_url, ...)

        Raises:
            ValidationError: blob is malformed or has a bad signature
            ClientError:     agent already exists and ``overwrite`` is False
        """
        return self._request("POST", "/api/import", {
            "blob": blob,
            "overwrite": overwrite,
            "apply_decay": apply_decay,
        })
