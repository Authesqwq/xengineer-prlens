"""Tests for diff processor."""

from dataclasses import dataclass

import pytest

from src.diff_processor import (
    DiffContext,
    ProcessedDiffFile,
    build_diff_context,
)


@dataclass
class FakeChangedFile:
    filename: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str = ""


def _make_file(filename, changes=1, patch="fake patch content", **kw):
    return FakeChangedFile(filename=filename, changes=changes, patch=patch, **kw)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_empty_files_returns_empty_context(self):
        result = build_diff_context([])
        assert isinstance(result, DiffContext)
        assert result.content == ""
        assert result.total_files == 0
        assert result.warnings == ["No changed files were provided."]

    def test_none_raises_value_error(self):
        with pytest.raises(ValueError, match="files"):
            build_diff_context(None)

    def test_max_total_chars_below_1(self):
        with pytest.raises(ValueError, match="max_total_chars"):
            build_diff_context([], max_total_chars=0)

    def test_max_file_chars_below_1(self):
        with pytest.raises(ValueError, match="max_file_chars"):
            build_diff_context([], max_file_chars=0)


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


class TestOutputStructure:
    def test_content_has_markdown_structure(self):
        f = _make_file("src/app.py", additions=10, deletions=3, changes=13,
                       patch="@@ -1,5 +1,8 @@\n+new line")
        result = build_diff_context([f])
        assert "Pull Request Diff Context" in result.content
        assert "## File: src/app.py" in result.content
        assert "Status: modified" in result.content
        assert "Additions: 10" in result.content
        assert "Deletions: 3" in result.content
        assert "Changes: 13" in result.content
        assert "```diff" in result.content
        assert "new line" in result.content

    def test_fields_populated(self):
        f = _make_file("a.py", changes=5, patch="hello")
        result = build_diff_context([f])
        assert result.total_files == 1
        assert result.included_files == 1
        assert result.skipped_files == 0
        assert result.truncated_files == 0
        assert result.was_truncated is False
        assert result.original_total_chars == len("hello")
        assert result.processed_total_chars == len(result.content)

    def test_processed_chars_matches_content_length(self):
        f = _make_file("a.py", patch="abc")
        result = build_diff_context([f])
        assert result.processed_total_chars == len(result.content)


# ---------------------------------------------------------------------------
# Patch edge cases
# ---------------------------------------------------------------------------


class TestPatchEdgeCases:
    def test_patch_none_converted_to_empty(self):
        f = _make_file("img.png", patch=None)
        result = build_diff_context([f])
        assert "Patch is empty or unavailable" in result.content

    def test_patch_empty_does_not_raise(self):
        f = _make_file("img.png", patch="")
        result = build_diff_context([f])
        assert "Patch is empty or unavailable" in result.content

    def test_patch_empty_file_is_recorded(self):
        f = _make_file("img.png", patch="")
        result = build_diff_context([f])
        assert result.files[0].filename == "img.png"
        assert result.files[0].patch == ""


# ---------------------------------------------------------------------------
# File-level truncation
# ---------------------------------------------------------------------------


class TestFileTruncation:
    def test_single_file_truncated_when_exceeds_max_file_chars(self):
        f = _make_file("big.py", patch="x" * 100)
        result = build_diff_context([f], max_file_chars=50)
        assert result.truncated_files == 1
        assert result.files[0].truncated is True
        assert result.files[0].reason == "file_patch_exceeds_limit"
        assert "TRUNCATED" in result.content
        assert result.was_truncated is True

    def test_truncation_preserves_meta(self):
        f = _make_file("big.py", patch="x" * 100)
        result = build_diff_context([f], max_file_chars=50)
        assert "## File: big.py" in result.content


# ---------------------------------------------------------------------------
# Total-length truncation
# ---------------------------------------------------------------------------


class TestTotalTruncation:
    def test_second_file_skipped_when_total_exceeded(self):
        f1 = _make_file("a.py", changes=5, patch="x" * 100)
        f2 = _make_file("b.py", changes=3, patch="y" * 100)
        # max_total_chars fits header + f1 but not f2
        result = build_diff_context([f1, f2], max_total_chars=450)
        assert result.files[0].included is True
        assert result.files[1].included is False
        assert result.files[1].reason == "total_context_limit_reached"
        assert result.was_truncated is True

    def test_was_truncated_true_on_total_limit(self):
        f1 = _make_file("a.py", patch="x" * 100)
        f2 = _make_file("b.py", patch="y" * 100)
        result = build_diff_context([f1, f2], max_total_chars=450)
        assert result.was_truncated is True

    def test_skipped_count_correct(self):
        f1 = _make_file("a.py", patch="x" * 100)
        f2 = _make_file("b.py", patch="y" * 100)
        result = build_diff_context([f1, f2], max_total_chars=450)
        assert result.skipped_files == 1


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


class TestSorting:
    def test_patch_nonempty_first(self):
        empty = _make_file("empty.py", patch="")
        full = _make_file("full.py", patch="def foo(): pass")
        result = build_diff_context([empty, full])
        assert result.files[0].filename == "full.py"
        assert result.files[1].filename == "empty.py"

    def test_changes_desc_within_same_has_patch(self):
        f1 = _make_file("b.py", changes=1, patch="code")
        f2 = _make_file("a.py", changes=99, patch="code")
        result = build_diff_context([f1, f2])
        assert result.files[0].filename == "a.py"
        assert result.files[1].filename == "b.py"

    def test_filename_asc_when_has_patch_and_changes_equal(self):
        f1 = _make_file("z.py", changes=5, patch="code")
        f2 = _make_file("a.py", changes=5, patch="code")
        result = build_diff_context([f1, f2])
        assert result.files[0].filename == "a.py"
        assert result.files[1].filename == "z.py"

    def test_empty_patch_files_at_end(self):
        """Files with no patch go after all files with patch, regardless of changes."""
        f1 = _make_file("small.py", changes=1, patch="x")
        f2 = _make_file("empty.py", changes=999, patch="")
        result = build_diff_context([f2, f1])
        assert result.files[0].filename == "small.py"
        assert result.files[1].filename == "empty.py"

    def test_does_not_mutate_input(self):
        f1 = _make_file("b.py", patch="code")
        f2 = _make_file("a.py", patch="code")
        original = [f1, f2]
        build_diff_context(original)
        assert original[0].filename == "b.py"
        assert original[1].filename == "a.py"


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestStatistics:
    def test_original_total_chars_sum_of_all_patches(self):
        f1 = _make_file("a.py", patch="abc")
        f2 = _make_file("b.py", patch="defg")
        result = build_diff_context([f1, f2])
        assert result.original_total_chars == 7

    def test_original_total_chars_includes_skipped(self):
        f1 = _make_file("a.py", patch="abc")
        f2 = _make_file("b.py", patch="defg")
        result = build_diff_context([f1, f2], max_total_chars=50)
        assert result.original_total_chars == 7


# ---------------------------------------------------------------------------
# ProcessedDiffFile detail
# ---------------------------------------------------------------------------


class TestProcessedDiffFileDetail:
    def test_included_file_has_correct_fields(self):
        f = _make_file("a.py", patch="hello", additions=2, deletions=1, changes=3)
        result = build_diff_context([f])
        pf = result.files[0]
        assert pf.filename == "a.py"
        assert pf.status == "modified"
        assert pf.additions == 2
        assert pf.deletions == 1
        assert pf.changes == 3
        assert pf.patch == "hello"
        assert pf.included is True
        assert pf.truncated is False

    def test_skipped_file_has_processed_length_zero(self):
        f1 = _make_file("a.py", patch="x" * 100)
        f2 = _make_file("b.py", patch="y" * 100)
        result = build_diff_context([f1, f2], max_total_chars=120)
        assert result.files[1].processed_patch_length == 0
