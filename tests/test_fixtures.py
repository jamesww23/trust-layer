"""Tests for scenario listing and loading."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.fixtures import load_demo_task, list_scenarios, load_scenario


class TestListScenarios:
    def test_returns_list(self):
        scenarios = list_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) >= 4

    def test_each_scenario_has_required_fields(self):
        for s in list_scenarios():
            assert "task_id" in s
            assert "title" in s
            assert "domain" in s
            assert "file" in s

    def test_default_scenario_included(self):
        ids = [s["task_id"] for s in list_scenarios()]
        assert "task_renewable_energy" in ids

    def test_all_task_ids_unique(self):
        ids = [s["task_id"] for s in list_scenarios()]
        assert len(ids) == len(set(ids))


class TestLoadScenario:
    def test_load_default_scenario(self):
        task, candidates = load_scenario("task_renewable_energy")
        assert task.task_id == "task_renewable_energy"
        assert len(candidates) >= 2

    def test_load_healthcare_scenario(self):
        task, candidates = load_scenario("task_patient_triage")
        assert task.task_id == "task_patient_triage"
        assert len(candidates) >= 2

    def test_load_finance_scenario(self):
        task, candidates = load_scenario("task_fraud_detection")
        assert task.task_id == "task_fraud_detection"
        assert len(candidates) >= 2

    def test_load_cybersecurity_scenario(self):
        task, candidates = load_scenario("task_threat_analysis")
        assert task.task_id == "task_threat_analysis"
        assert len(candidates) >= 2

    def test_unknown_task_id_raises(self):
        with pytest.raises(ValueError, match="Unknown task_id"):
            load_scenario("task_nonexistent")

    def test_all_scenarios_loadable(self):
        """Every scenario in the manifest must load without error."""
        for s in list_scenarios():
            task, candidates = load_scenario(s["task_id"])
            assert task.task_id == s["task_id"]
            assert len(candidates) >= 2

    def test_all_candidates_match_task_id(self):
        """Every candidate must reference the correct task_id."""
        for s in list_scenarios():
            task, candidates = load_scenario(s["task_id"])
            for c in candidates:
                assert c.task_id == task.task_id


class TestLoadDemoTaskBackwardCompat:
    def test_existing_function_still_works(self):
        task, candidates = load_demo_task()
        assert task.task_id == "task_renewable_energy"
        assert len(candidates) == 3
