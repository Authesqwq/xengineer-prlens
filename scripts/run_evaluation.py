"""
PRLens automated evaluation runner.

Runs standard-mode analysis against a fixed set of evaluation PRs and
records objective metrics (status, elapsed time, risk count, etc.).
Does NOT claim accuracy — all qualitative judgments require human review.

Usage:
    python scripts/run_evaluation.py

Output:
    docs/evaluation_results.json
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

# Always prefer gh CLI token if available (avoids dotenv encoding issues)
try:
    import subprocess as _sp
    result = _sp.run(["gh", "auth", "token"], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        os.environ["GITHUB_TOKEN"] = result.stdout.strip()
except Exception:
    pass

from src.pr_parser import parse_github_pr_url, PRUrlParseError
from src.github_client import (
    fetch_pr_info,
    fetch_pr_files,
    GitHubClientError,
)
from src.diff_processor import build_diff_context
from src.llm_client import (
    load_llm_config_from_env,
    LLMConfigError,
    LLMClientError,
)
from src.summary_analyzer import generate_pr_summary, SummaryAnalyzerError
from src.risk_analyzer import analyze_pr_risks, RiskAnalyzerError
from src.review_suggestion import (
    generate_review_suggestions,
    ReviewSuggestionError,
)

# ---------------------------------------------------------------------------
# Evaluation cases
# ---------------------------------------------------------------------------

EVALUATION_CASES = [
    {"case_id": "E1", "pr_url": "https://github.com/Authesqwq/xengineer-prlens/pull/1",
     "pr_type": "documentation", "modes": ["standard"]},
    {"case_id": "E2", "pr_url": "https://github.com/Authesqwq/xengineer-prlens/pull/2",
     "pr_type": "feature (parser)", "modes": ["standard"]},
    {"case_id": "E3", "pr_url": "https://github.com/Authesqwq/xengineer-prlens/pull/5",
     "pr_type": "feature (diff)", "modes": ["standard"]},
    {"case_id": "E4", "pr_url": "https://github.com/Authesqwq/xengineer-prlens/pull/6",
     "pr_type": "feature (llm)", "modes": ["standard"]},
    {"case_id": "E5", "pr_url": "https://github.com/Authesqwq/xengineer-prlens/pull/9",
     "pr_type": "feature (risk)", "modes": ["standard", "full"]},
    {"case_id": "E6", "pr_url": "https://github.com/Authesqwq/xengineer-prlens/pull/11",
     "pr_type": "feature (suggestions)", "modes": ["standard", "full"]},
    {"case_id": "E7", "pr_url": "https://github.com/Authesqwq/xengineer-prlens/pull/15",
     "pr_type": "feature (workspace)", "modes": ["standard", "full"]},
    {"case_id": "E8", "pr_url": "https://github.com/Authesqwq/xengineer-prlens/pull/17",
     "pr_type": "documentation", "modes": ["standard"]},
]


def _auto_flags(case_result: dict) -> dict:
    flags = {}
    summary = case_result.get("summary_result")
    risk = case_result.get("risk_result")
    suggestions = case_result.get("suggestions_result")

    flags["summary_non_empty"] = bool(summary and summary.summary.strip())
    flags["risk_has_evidence_when_present"] = True
    if risk and risk.risk_items:
        flags["risk_has_evidence_when_present"] = all(
            ri.evidence.strip() for ri in risk.risk_items
        )
    flags["suggestion_has_copy_text_when_present"] = True
    if suggestions and suggestions.suggestions:
        flags["suggestion_has_copy_text_when_present"] = all(
            s.copy_text.strip() for s in suggestions.suggestions
        )
    flags["no_high_risk_for_docs_only"] = True
    if case_result.get("pr_type") == "documentation" and risk and risk.risk_items:
        has_high = any(ri.severity == "high" for ri in risk.risk_items)
        flags["no_high_risk_for_docs_only"] = not has_high
    flags["completed_without_exception"] = case_result.get("status") == "success"
    return flags


def run_case(case: dict) -> list[dict]:
    results = []
    pr_type = case["pr_type"]
    for mode in case["modes"]:
        result = {
            "case_id": case["case_id"],
            "pr_url": case["pr_url"],
            "pr_type": pr_type,
            "mode": mode,
            "status": "pending",
            "elapsed_seconds": None,
            "files_total": 0,
            "files_included": 0,
            "files_skipped": 0,
            "diff_chars": 0,
            "summary_generated": False,
            "risk_generated": False,
            "risk_count": 0,
            "suggestion_generated": False,
            "suggestion_count": 0,
            "fallback_used": False,
            "error_message": None,
            "auto_quality_flags": {},
            "human_review_required": True,
            "notes": "",
        }

        try:
            start = time.perf_counter()
            parsed = parse_github_pr_url(case["pr_url"])
            token = os.getenv("GITHUB_TOKEN") or None
            pr_info = fetch_pr_info(parsed.owner, parsed.repo, parsed.pull_number, token=token)
            files = fetch_pr_files(parsed.owner, parsed.repo, parsed.pull_number, token=token)
            diff_context = build_diff_context(files)

            result["files_total"] = diff_context.total_files
            result["files_included"] = diff_context.included_files
            result["files_skipped"] = diff_context.skipped_files
            result["diff_chars"] = diff_context.processed_total_chars

            llm_config = load_llm_config_from_env()
            output_lang = "en"

            # Summary (all modes)
            summary = generate_pr_summary(pr_info, diff_context, llm_config, output_language=output_lang)
            result["summary_generated"] = True
            result["summary_result"] = summary

            # Risk (standard + full)
            do_risk = mode in ("standard", "full")
            risk = None
            if do_risk:
                risk = analyze_pr_risks(pr_info, diff_context, llm_config, output_language=output_lang)
                result["risk_generated"] = True
                result["risk_count"] = len(risk.risk_items) if risk.risk_items else 0
                # Detect fallback
                if risk.limitations:
                    for lim in risk.limitations:
                        if "empty content" in lim.lower() or "could not be parsed" in lim.lower() or "空内容" in lim or "未能解析" in lim:
                            result["fallback_used"] = True
                            break
                result["risk_result"] = risk

            # Suggestions (full only)
            do_sug = mode == "full"
            sug_result = None
            if do_sug:
                sug_result = generate_review_suggestions(
                    pr_info=pr_info, diff_context=diff_context,
                    risk_result=risk, llm_config=llm_config,
                    output_language=output_lang,
                )
                result["suggestion_generated"] = True
                result["suggestion_count"] = len(sug_result.suggestions) if sug_result.suggestions else 0
                result["suggestions_result"] = sug_result

            result["elapsed_seconds"] = round(time.perf_counter() - start, 2)
            result["status"] = "success"

        except LLMConfigError as e:
            result["status"] = "skipped"
            result["error_message"] = f"LLM config missing: {e}"
            result["notes"] = "Skipped due to missing LLM configuration"
        except (GitHubClientError, PRUrlParseError, LLMClientError,
                SummaryAnalyzerError, RiskAnalyzerError, ReviewSuggestionError, Exception) as e:
            result["status"] = "error"
            result["error_message"] = str(e)[:300]
            result["notes"] = f"Failed: {type(e).__name__}"

        result["auto_quality_flags"] = _auto_flags(result)
        results.append(result)

        # Brief pause between cases
        time.sleep(0.5)

    return results


def main():
    print("=" * 60)
    print("PRLens Evaluation Runner")
    print("=" * 60)

    all_results = []
    for case in EVALUATION_CASES:
        print(f"\n[{case['case_id']}] {case['pr_type']} — modes: {case['modes']}")
        results = run_case(case)
        for r in results:
            status = r["status"]
            elapsed = r["elapsed_seconds"]
            risks = r["risk_count"]
            print(f"  {r['mode']}: {status} | {elapsed}s | {risks} risks | fallback={r['fallback_used']}")
        all_results.extend(results)

    # Save JSON
    output_path = ROOT_DIR / "docs" / "evaluation_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "Authesqwq/xengineer-prlens",
        "total_cases": len(EVALUATION_CASES),
        "total_runs": len(all_results),
        "cases": all_results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # Summary
    success = sum(1 for r in all_results if r["status"] == "success")
    skipped = sum(1 for r in all_results if r["status"] == "skipped")
    errors = sum(1 for r in all_results if r["status"] == "error")
    print(f"\n{'=' * 60}")
    print(f"Done. {success} succeeded, {skipped} skipped, {errors} errors")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
