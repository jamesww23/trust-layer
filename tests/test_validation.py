"""Regression tests for input validation fixes."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import Task


class TestTaskKeywordsValidation:
    """Fix 1: expected_keywords must be a list of strings."""

    def test_valid_keywords_list(self):
        task = Task("t1", "prompt", ["solar", "wind"])
        assert task.expected_keywords == ["solar", "wind"]

    def test_none_keywords_defaults_to_empty(self):
        task = Task("t1", "prompt", None)
        assert task.expected_keywords == []

    def test_empty_list_accepted(self):
        task = Task("t1", "prompt", [])
        assert task.expected_keywords == []

    def test_string_rejected(self):
        with pytest.raises(ValueError, match="must be a list"):
            Task("t1", "prompt", "abc")

    def test_integer_rejected(self):
        with pytest.raises(ValueError, match="must be a list"):
            Task("t1", "prompt", 123)

    def test_dict_rejected(self):
        with pytest.raises(ValueError, match="must be a list"):
            Task("t1", "prompt", {"key": "val"})

    def test_list_with_non_string_element_rejected(self):
        with pytest.raises(ValueError, match="must be a string"):
            Task("t1", "prompt", ["solar", 42])

    def test_list_with_none_element_rejected(self):
        with pytest.raises(ValueError, match="must be a string"):
            Task("t1", "prompt", ["solar", None])

    def test_list_with_nested_list_rejected(self):
        with pytest.raises(ValueError, match="must be a string"):
            Task("t1", "prompt", ["solar", ["nested"]])

    def test_from_dict_validates_keywords(self):
        with pytest.raises(ValueError, match="must be a list"):
            Task.from_dict({"task_id": "t1", "prompt": "p", "expected_keywords": "bad"})

    def test_string_iterates_characters_bug(self):
        """Regression: a string like 'abc' would iterate as ['a','b','c'] in scoring."""
        with pytest.raises(ValueError, match="must be a list"):
            Task("t1", "prompt", "renewable")
