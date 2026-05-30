"""Tests for app.py display helper functions."""

from dataclasses import dataclass

from app import _none_if_empty, format_pr_status, PRIORITY_ORDER, SEVERITY_ORDER


@dataclass
class FakePRInfo:
    state: str = "closed"
    merged: bool = True


class TestFormatPRStatus:
    def test_open(self):
        assert format_pr_status(FakePRInfo(state="open", merged=False)) == "Open"

    def test_merged(self):
        assert format_pr_status(FakePRInfo(state="closed", merged=True)) == "Merged"

    def test_closed_not_merged(self):
        assert format_pr_status(FakePRInfo(state="closed", merged=False)) == "Closed"

    def test_unknown_state(self):
        assert format_pr_status(FakePRInfo(state="unknown", merged=False)) == "Unknown"


class TestNoneIfEmpty:
    def test_empty_list(self):
        assert _none_if_empty([]) == ["None"]

    def test_non_empty_list(self):
        assert _none_if_empty(["a", "b"]) == ["a", "b"]


class TestSorting:
    def test_severity_order_high_first(self):
        assert SEVERITY_ORDER["high"] < SEVERITY_ORDER["medium"] < SEVERITY_ORDER["low"]

    def test_priority_order_high_first(self):
        assert PRIORITY_ORDER["high"] < PRIORITY_ORDER["medium"] < PRIORITY_ORDER["low"]

    def test_severity_sort(self):
        items = [
            type("R", (), {"severity": "medium"})(),
            type("R", (), {"severity": "high"})(),
            type("R", (), {"severity": "low"})(),
        ]
        result = sorted(items, key=lambda r: SEVERITY_ORDER.get(r.severity, 99))
        assert [r.severity for r in result] == ["high", "medium", "low"]

    def test_priority_sort(self):
        items = [
            type("S", (), {"priority": "low"})(),
            type("S", (), {"priority": "high"})(),
            type("S", (), {"priority": "medium"})(),
        ]
        result = sorted(items, key=lambda s: PRIORITY_ORDER.get(s.priority, 99))
        assert [s.priority for s in result] == ["high", "medium", "low"]
