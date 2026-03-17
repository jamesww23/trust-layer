"""Tests for ReputationStore — JSON persistence backend."""

import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from store import ReputationStore
from models import AgentProfile


class TestReputationStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "reputation.json")
        self.store = ReputationStore(path=self.path)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("nonexistent"))

    def test_upsert_and_get(self):
        profile = AgentProfile.default("test_agent")
        self.store.upsert(profile)
        loaded = self.store.get("test_agent")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.agent_id, "test_agent")
        self.assertEqual(loaded.success_rate, 0.5)
        self.assertEqual(loaded.total_runs, 0)

    def test_upsert_overwrites(self):
        p = AgentProfile.default("agent_x")
        self.store.upsert(p)
        p.success_rate = 0.9
        p.total_runs = 5
        self.store.upsert(p)
        loaded = self.store.get("agent_x")
        self.assertEqual(loaded.success_rate, 0.9)
        self.assertEqual(loaded.total_runs, 5)

    def test_persistence_across_instances(self):
        """Simulates process restart — new store instance reads same file."""
        p = AgentProfile.default("agent_persist")
        p.success_rate = 0.75
        self.store.upsert(p)

        new_store = ReputationStore(path=self.path)
        loaded = new_store.get("agent_persist")
        self.assertEqual(loaded.success_rate, 0.75)

    def test_list_all(self):
        self.store.upsert(AgentProfile.default("a"))
        self.store.upsert(AgentProfile.default("b"))
        self.store.upsert(AgentProfile.default("c"))
        all_profiles = self.store.list_all()
        self.assertEqual(len(all_profiles), 3)
        ids = {p.agent_id for p in all_profiles}
        self.assertEqual(ids, {"a", "b", "c"})

    def test_default_profile_values(self):
        p = AgentProfile.default("new_agent")
        self.assertEqual(p.success_rate, 0.5)
        self.assertEqual(p.total_runs, 0)
        self.assertTrue(len(p.created_at) > 0)
        self.assertTrue(len(p.updated_at) > 0)


if __name__ == "__main__":
    unittest.main()
