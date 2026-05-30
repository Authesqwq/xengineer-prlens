"""Tests for app.py display helper functions."""

from dataclasses import dataclass

from app import (
    PRIORITY_ORDER,
    SEVERITY_ORDER,
    T,
    _none_if_empty,
    format_pr_status,
    t,
)


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


class TestTranslations:
    def test_t_en(self):
        assert t("en", "title") == "PRLens: AI PR Review Assistant"

    def test_t_zh(self):
        assert t("zh", "title") == "PRLens: AI PR Review 助手"

    def test_t_fallback(self):
        assert t("fr", "title") == "PRLens: AI PR Review Assistant"

    def test_t_missing_key(self):
        assert t("en", "xyz_nonexistent") == "xyz_nonexistent"

    def test_t_format(self):
        result = t("en", "more_files", n=5)
        assert "... and 5 more files" in result
