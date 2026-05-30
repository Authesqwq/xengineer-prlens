"""Diff cleaning, truncation, and model-context assembly.

Transforms a list of ChangedFile objects into a structured DiffContext
suitable for LLM input.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProcessedDiffFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str
    included: bool
    truncated: bool
    reason: Optional[str] = None
    original_patch_length: int = 0
    processed_patch_length: int = 0


@dataclass
class DiffContext:
    content: str
    files: list
    total_files: int
    included_files: int
    skipped_files: int
    truncated_files: int
    original_total_chars: int
    processed_total_chars: int
    was_truncated: bool
    warnings: list[str]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_diff_context(
    files: list,
    max_total_chars: int = 12000,
    max_file_chars: int = 4000,
) -> DiffContext:
    """Build a DiffContext from a list of ChangedFile objects.

    Files are sorted by: patch non-empty first, then changes descending,
    then filename ascending.
    """
    if max_total_chars < 1:
        raise ValueError("max_total_chars must be at least 1")
    if max_file_chars < 1:
        raise ValueError("max_file_chars must be at least 1")
    if files is None:
        raise ValueError("files must not be None")

    if not files:
        return DiffContext(
            content="",
            files=[],
            total_files=0,
            included_files=0,
            skipped_files=0,
            truncated_files=0,
            original_total_chars=0,
            processed_total_chars=0,
            was_truncated=False,
            warnings=["No changed files were provided."],
        )

    sorted_files = _sort_files(files)
    processed_files, content, warnings = _process_files(
        sorted_files, max_total_chars, max_file_chars
    )

    total = len(processed_files)
    included = sum(1 for f in processed_files if f.included)
    skipped = total - included
    truncated = sum(1 for f in processed_files if f.truncated)
    was_truncated = truncated > 0 or skipped > 0
    original_chars = sum(f.original_patch_length for f in processed_files)
    processed_chars = len(content)

    return DiffContext(
        content=content,
        files=processed_files,
        total_files=total,
        included_files=included,
        skipped_files=skipped,
        truncated_files=truncated,
        original_total_chars=original_chars,
        processed_total_chars=processed_chars,
        was_truncated=was_truncated,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sort_files(files: list) -> list:
    """Sort: patch non-empty first, then changes desc, then filename asc."""
    def sort_key(f):
        has_patch = 1 if (getattr(f, "patch", None) or "") else 0
        changes = getattr(f, "changes", 0) or 0
        name = getattr(f, "filename", "") or ""
        return (-has_patch, -changes, name)
    return sorted(files, key=sort_key)


def _process_files(files: list, max_total: int, max_file: int) -> tuple:
    processed = []
    parts = []
    warnings = []
    current_total = 0

    header = (
        "# Pull Request Diff Context\n\n"
        "The following content is extracted from GitHub PR changed files.\n"
        "It may not contain the full repository context.\n"
    )
    header_len = len(header)

    for f in files:
        filename = getattr(f, "filename", "") or ""
        status = getattr(f, "status", "") or ""
        additions = getattr(f, "additions", 0) or 0
        deletions = getattr(f, "deletions", 0) or 0
        changes = getattr(f, "changes", 0) or 0
        patch = getattr(f, "patch", None) or ""
        original_len = len(patch)

        file_block, was_truncated, processed_len = _build_file_block(
            filename, status, additions, deletions, changes, patch, max_file
        )

        # Check if this block fits
        needed = header_len + current_total + len(file_block)
        if parts:
            # Already have content, check adding this block
            if needed > max_total:
                processed.append(ProcessedDiffFile(
                    filename=filename, status=status,
                    additions=additions, deletions=deletions, changes=changes,
                    patch=patch, included=False, truncated=False,
                    reason="total_context_limit_reached",
                    original_patch_length=original_len,
                    processed_patch_length=0,
                ))
                continue
        else:
            # First file: check header + first block
            if header_len + len(file_block) > max_total:
                processed.append(ProcessedDiffFile(
                    filename=filename, status=status,
                    additions=additions, deletions=deletions, changes=changes,
                    patch=patch, included=False, truncated=False,
                    reason="total_context_limit_reached",
                    original_patch_length=original_len,
                    processed_patch_length=0,
                ))
                continue

        parts.append(file_block)
        current_total += len(file_block)
        processed.append(ProcessedDiffFile(
            filename=filename, status=status,
            additions=additions, deletions=deletions, changes=changes,
            patch=patch, included=True, truncated=was_truncated,
            reason="file_patch_exceeds_limit" if was_truncated else None,
            original_patch_length=original_len,
            processed_patch_length=processed_len,
        ))

    # Mark all remaining files as skipped after first skip
    first_skipped = False
    for pf in processed:
        if not pf.included and not first_skipped:
            first_skipped = True
        elif first_skipped and pf.included:
            pf.included = False
            pf.reason = "total_context_limit_reached"

    # Build content
    content = header + "".join(parts) if parts else ""

    # Warnings
    any_truncated = any(pf.truncated for pf in processed)
    any_skipped = any(not pf.included for pf in processed)
    if any_truncated:
        warnings.append("One or more file patches were truncated because they exceeded max_file_chars.")
    if any_skipped:
        warnings.append("Diff context was truncated because it exceeded max_total_chars.")

    return processed, content, warnings


def _build_file_block(
    filename: str,
    status: str,
    additions: int,
    deletions: int,
    changes: int,
    patch: str,
    max_file: int,
) -> tuple[str, bool, int]:
    """Build a Markdown block for one file. Returns (text, was_truncated, processed_len)."""
    meta = (
        f"\n\n## File: {filename}\n\n"
        f"Status: {status}\n"
        f"Additions: {additions}\n"
        f"Deletions: {deletions}\n"
        f"Changes: {changes}\n\n"
    )

    if not patch:
        body = "Patch is empty or unavailable.\n"
        text = meta + body
        return text, False, len(body)

    line_prefix = "```diff\n"
    line_suffix = "\n```\n"
    overhead = len(line_prefix) + len(line_suffix)
    available = max_file - overhead

    if available <= 0:
        # max_file_chars too small for overhead
        body = "[TRUNCATED: file patch exceeds max_file_chars]\n"
        text = meta + body
        return text, True, len(body) + overhead

    if len(patch) > available:
        truncated_patch = patch[:available] + "\n[TRUNCATED: file patch exceeds max_file_chars]\n"
        body = line_prefix + truncated_patch + line_suffix
        return meta + body, True, len(truncated_patch) + overhead

    body = line_prefix + patch + line_suffix
    return meta + body, False, len(patch) + overhead
