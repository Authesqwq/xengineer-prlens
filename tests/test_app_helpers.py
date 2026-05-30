"""Tests for app.py display helper functions."""

from dataclasses import dataclass

from app import (
    HISTORY_MAX,
    PRIORITY_ORDER,
    SEVERITY_ORDER,
    _badge_class,
    _build_report_md,
    _history_item_label,
    _make_history_key,
    _mode_display_name,
    _none_if_empty,
    _risk_label,
    build_analysis_steps,
    format_elapsed_time,
    format_pr_status,
    render_progress_steps,
    t,
)


@dataclass
class FakePRInfo:
    title: str = "Add login validation"
    state: str = "closed"
    merged: bool = True
    author: str = "dev1"
    changed_files: int = 3
    additions: int = 42
    deletions: int = 10
    commits: int = 2


@dataclass
class FakeSummaryResult:
    summary: str = "This PR adds login validation."
    main_changes: list = None
    affected_areas: list = None
    uncertainties: list = None

    def __post_init__(self):
        if self.main_changes is None:
            self.main_changes = ["Added validation"]
        if self.affected_areas is None:
            self.affected_areas = ["Auth"]
        if self.uncertainties is None:
            self.uncertainties = []


@dataclass
class FakeRiskItem:
    risk_type: str = "logic"
    severity: str = "medium"
    file_path: str = "src/login.py"
    evidence: str = "Null check removed"
    explanation: str = "May crash"
    impact: str = "Login may fail"
    suggestion: str = "Add null check"
    confidence: str = "medium"
    need_human_check: bool = True


@dataclass
class FakeRiskResult:
    overall_risk_level: str = "medium"
    risk_items: list = None
    limitations: list = None

    def __post_init__(self):
        if self.risk_items is None:
            self.risk_items = [FakeRiskItem()]
        if self.limitations is None:
            self.limitations = []


@dataclass
class FakeSuggestion:
    title: str = "Add test"
    priority: str = "medium"
    file_path: str = "src/login.py"
    problem: str = "No test coverage"
    evidence: str = "No test file modified"
    impact: str = ""
    suggestion: str = "Add unit test"
    copy_text: str = "Could you add a unit test?"
    source_risk_type: str = "testing"
    need_human_check: bool = True


@dataclass
class FakeSuggestionResult:
    suggestions: list = None
    limitations: list = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = [FakeSuggestion()]
        if self.limitations is None:
            self.limitations = []


class TestFormatPRStatus:
    def test_open_zh(self):
        assert format_pr_status(FakePRInfo(state="open", merged=False), "zh") == "打开"

    def test_merged_en(self):
        assert format_pr_status(FakePRInfo(state="closed", merged=True), "en") == "Merged"

    def test_closed_zh(self):
        assert format_pr_status(FakePRInfo(state="closed", merged=False), "zh") == "已关闭"


class TestNoneIfEmpty:
    def test_empty_zh(self):
        assert _none_if_empty([], "zh") == ["无"]

    def test_empty_en(self):
        assert _none_if_empty([], "en") == ["None"]


class TestSorting:
    def test_severity(self):
        assert SEVERITY_ORDER["high"] < SEVERITY_ORDER["medium"] < SEVERITY_ORDER["low"]

    def test_priority(self):
        assert PRIORITY_ORDER["high"] < PRIORITY_ORDER["medium"] < PRIORITY_ORDER["low"]


class TestBadge:
    def test_high(self):
        assert "high" in _badge_class("high")
    def test_low(self):
        assert "low" in _badge_class("low")


class TestRiskLabel:
    def test_high_zh(self):
        assert _risk_label("high", "zh") == "高风险"


class TestTranslations:
    def test_t_en(self):
        assert "PRLens" in t("en", "title")
    def test_t_zh(self):
        assert "助手" in t("zh", "title")


class TestBuildReportMd:
    def test_en_has_sections(self):
        md = _build_report_md("en", FakePRInfo(), FakeSummaryResult(), FakeRiskResult(), FakeSuggestionResult())
        assert "# PRLens" in md
        assert "## PR Overview" in md

    def test_zh_has_sections(self):
        md = _build_report_md("zh", FakePRInfo(), FakeSummaryResult(), FakeRiskResult(), FakeSuggestionResult())
        assert "PRLens 分析报告" in md

    def test_with_mode_and_elapsed(self):
        md = _build_report_md("en", FakePRInfo(), FakeSummaryResult(), FakeRiskResult(),
                              FakeSuggestionResult(), analysis_mode="standard", elapsed_seconds=18.5)
        assert "Standard" in md
        assert "18.5s" in md


class TestFormatElapsedTime:
    def test_seconds_zh(self):
        assert "18.6 秒" in format_elapsed_time(18.56, "zh")

    def test_seconds_en(self):
        assert "18.6s" in format_elapsed_time(18.56, "en")

    def test_minutes_zh(self):
        result = format_elapsed_time(72, "zh")
        assert "1 分" in result

    def test_minutes_en(self):
        result = format_elapsed_time(72, "en")
        assert "1m" in result
        assert "12.0s" in result

    def test_none_zh(self):
        assert format_elapsed_time(None, "zh") == "未知"

    def test_none_en(self):
        assert format_elapsed_time(None, "en") == "Unknown"


class TestModeDisplayName:
    def test_fast_zh(self):
        assert "快速" in _mode_display_name("fast", "zh")

    def test_standard_en(self):
        assert _mode_display_name("standard", "en") == "Standard"


class TestHistoryHelpers:
    def test_make_history_key(self):
        k = _make_history_key("https://github.com/a/b/pull/1", "en", "standard")
        assert "a/b/pull/1" in k
        assert "en" in k
        assert "standard" in k

    def test_history_item_label_en(self):
        entry = {
            "url": "https://github.com/owner/repo/pull/123",
            "risk_level": "low",
            "risk_count": 0,
            "analysis_mode": "standard",
            "elapsed_seconds": 12.3,
        }
        label = _history_item_label(entry, "en")
        assert "owner/repo #123" in label
        assert "Low" in label
        assert "12.3s" in label

    def test_history_item_label_zh(self):
        entry = {
            "url": "https://github.com/owner/repo/pull/123",
            "risk_level": "medium",
            "risk_count": 2,
            "analysis_mode": "standard",
            "elapsed_seconds": 72.0,
        }
        label = _history_item_label(entry, "zh")
        assert "owner/repo #123" in label
        assert "中风险" in label
        assert "标准模式" in label

    def test_history_max_limit(self):
        entries = [{"url": f"https://github.com/a/b/pull/{i}", "language": "en",
                     "analysis_mode": "standard"} for i in range(HISTORY_MAX + 5)]
        truncated = entries[:HISTORY_MAX]
        assert len(truncated) == 10


class TestBuildAnalysisSteps:
    def test_fast_zh_excludes_risk_and_suggestions(self):
        steps = build_analysis_steps("fast", "zh")
        keys = [s["key"] for s in steps]
        assert "risk" not in keys
        assert "suggestions" not in keys
        assert "summary" in keys

    def test_standard_zh_includes_risk_excludes_suggestions(self):
        steps = build_analysis_steps("standard", "zh")
        keys = [s["key"] for s in steps]
        assert "risk" in keys
        assert "suggestions" not in keys

    def test_full_zh_includes_all(self):
        steps = build_analysis_steps("full", "zh")
        keys = [s["key"] for s in steps]
        assert "risk" in keys
        assert "suggestions" in keys

    def test_en_labels_are_english(self):
        steps = build_analysis_steps("standard", "en")
        assert steps[0]["label"] == "Parse PR URL"
        assert "分析" not in steps[0]["label"]

    def test_zh_labels_are_chinese(self):
        steps = build_analysis_steps("standard", "zh")
        assert "解析" in steps[0]["label"]


class TestRenderProgressSteps:
    def _steps(self):
        return [
            {"key": "parse_url", "label": "Parse URL"},
            {"key": "fetch_pr", "label": "Fetch PR"},
            {"key": "summary", "label": "Generate Summary"},
        ]

    def test_current_step_shows_arrow(self):
        result = render_progress_steps(self._steps(), current_key="fetch_pr",
                                       completed_keys={"parse_url"})
        assert "▶" in result
        assert "✓ Parse URL" in result
        assert "○ Generate Summary" in result

    def test_completed_step_shows_check(self):
        result = render_progress_steps(self._steps(), completed_keys={"parse_url"})
        assert "✓ Parse URL" in result

    def test_skipped_step_shows_warning(self):
        result = render_progress_steps(self._steps(), completed_keys={"parse_url", "fetch_pr"},
                                       skipped_keys={"summary"})
        assert "⚠ Generate Summary" in result

    def test_failed_step_shows_cross(self):
        result = render_progress_steps(self._steps(), completed_keys={"parse_url"},
                                       failed_key="fetch_pr")
        assert "✕ Fetch PR" in result

    def test_pending_step_shows_circle(self):
        result = render_progress_steps(self._steps())
        assert "○ Parse URL" in result
