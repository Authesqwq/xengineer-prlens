"""Tests for app.py display helper functions."""

from dataclasses import dataclass

from app import (
    PRIORITY_ORDER,
    SEVERITY_ORDER,
    T,
    _none_if_empty,
    _risk_level_badge_class,
    _risk_level_label,
    format_pr_status,
    t,
)


@dataclass
class FakePRInfo:
    state: str = "closed"
    merged: bool = True


class TestFormatPRStatus:
    def test_open_zh(self):
        assert format_pr_status(FakePRInfo(state="open", merged=False), "zh") == "打开"

    def test_open_en(self):
        assert format_pr_status(FakePRInfo(state="open", merged=False), "en") == "Open"

    def test_merged_zh(self):
        assert format_pr_status(FakePRInfo(state="closed", merged=True), "zh") == "已合并"

    def test_merged_en(self):
        assert format_pr_status(FakePRInfo(state="closed", merged=True), "en") == "Merged"

    def test_closed_not_merged_zh(self):
        assert format_pr_status(FakePRInfo(state="closed", merged=False), "zh") == "已关闭"

    def test_closed_not_merged_en(self):
        assert format_pr_status(FakePRInfo(state="closed", merged=False), "en") == "Closed"

    def test_unknown_state(self):
        assert format_pr_status(FakePRInfo(state="unknown", merged=False), "en") == "Unknown"


class TestNoneIfEmpty:
    def test_empty_list_zh(self):
        assert _none_if_empty([], "zh") == ["无"]

    def test_empty_list_en(self):
        assert _none_if_empty([], "en") == ["None"]

    def test_non_empty_list(self):
        assert _none_if_empty(["a", "b"], "en") == ["a", "b"]


class TestSorting:
    def test_severity_order(self):
        assert SEVERITY_ORDER["high"] < SEVERITY_ORDER["medium"] < SEVERITY_ORDER["low"]

    def test_priority_order(self):
        assert PRIORITY_ORDER["high"] < PRIORITY_ORDER["medium"] < PRIORITY_ORDER["low"]


class TestRiskLevelBadge:
    def test_high_badge_class(self):
        assert "high" in _risk_level_badge_class("high")

    def test_medium_badge_class(self):
        assert "medium" in _risk_level_badge_class("medium")

    def test_low_badge_class(self):
        assert "low" in _risk_level_badge_class("low")

    def test_unknown_badge_class(self):
        assert "low" in _risk_level_badge_class("unknown")


class TestRiskLevelLabel:
    def test_high_zh(self):
        assert _risk_level_label("high", "zh") == "高风险"

    def test_medium_en(self):
        assert _risk_level_label("medium", "en") == "Medium"

    def test_low_zh(self):
        assert _risk_level_label("low", "zh") == "低风险"


class TestTranslations:
    def test_t_en_title(self):
        assert "PRLens" in t("en", "title")

    def test_t_zh_title(self):
        assert "助手" in t("zh", "title")

    def test_t_fallback(self):
        assert t("fr", "title") == T["en"]["title"]

    def test_t_missing_key(self):
        assert t("en", "xyz_nonexistent") == "xyz_nonexistent"

    def test_t_format(self):
        result = t("en", "more_files", n=5)
        assert "... and 5 more files" in result
