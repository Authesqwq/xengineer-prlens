"""
PRLens automated evaluation runner v2.

Reads evaluation cases from JSON config, runs analysis, records metrics.
Supports CLI flags: --include-stress, --case X, --mode Y.

Usage:
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --include-stress
    python scripts/run_evaluation.py --case E1
    python scripts/run_evaluation.py --mode standard
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

# Prefer gh CLI token to avoid dotenv encoding quirks
try:
    import subprocess as _sp
    result = _sp.run(["gh", "auth", "token"], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        os.environ["GITHUB_TOKEN"] = result.stdout.strip()
except Exception:
    pass

from src.pr_parser import parse_github_pr_url, PRUrlParseError
from src.github_client import fetch_pr_info, fetch_pr_files, GitHubClientError
from src.diff_processor import build_diff_context
from src.llm_client import load_llm_config_from_env, LLMConfigError, LLMClientError
from src.summary_analyzer import generate_pr_summary, SummaryAnalyzerError
from src.risk_analyzer import analyze_pr_risks, RiskAnalyzerError
from src.review_suggestion import generate_review_suggestions, ReviewSuggestionError

# ---------------------------------------------------------------------------
# Speed-oriented diff limits (override via env)
# ---------------------------------------------------------------------------
EVAL_MAX_FILES = int(os.getenv("PRLENS_MAX_FILES", "8"))
EVAL_MAX_PATCH_CHARS = int(os.getenv("PRLENS_MAX_PATCH_CHARS_PER_FILE", "6000"))
EVAL_MAX_TOTAL_CHARS = int(os.getenv("PRLENS_MAX_TOTAL_DIFF_CHARS", "30000"))


def load_cases(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _auto_flags(result: dict) -> dict:
    f = {}
    summary = result.get("summary_result")
    risk = result.get("risk_result")
    sug = result.get("suggestions_result")
    f["summary_non_empty"] = bool(summary and summary.summary.strip())
    f["risk_has_evidence"] = True
    if risk and risk.risk_items:
        f["risk_has_evidence"] = all(ri.evidence.strip() for ri in risk.risk_items)
    f["suggestion_has_copy_text"] = True
    if sug and sug.suggestions:
        f["suggestion_has_copy_text"] = all(s.copy_text.strip() for s in sug.suggestions)
    f["no_high_risk_for_docs"] = True
    if "文档" in result.get("pr_type", "") and risk and risk.risk_items:
        f["no_high_risk_for_docs"] = not any(ri.severity == "high" for ri in risk.risk_items)
    f["completed_without_exception"] = result.get("status") == "success"
    f["truncated"] = result.get("truncated", False)
    f["fallback_used"] = result.get("fallback_used", False)
    return f


def run_case(case: dict) -> list[dict]:
    results = []
    for mode in case["modes"]:
        r = {
            "case_id": case["case_id"], "pr_url": case["pr_url"],
            "repo_type": case.get("repo_type", "external"),
            "pr_type": case.get("pr_type", ""), "focus": case.get("focus", ""),
            "mode": mode, "status": "pending",
            "elapsed_seconds": None,
            "files_total": 0, "files_included": 0, "files_skipped": 0,
            "diff_chars_before": 0, "diff_chars_after": 0, "truncated": False,
            "summary_generated": False, "risk_generated": False,
            "risk_count": 0, "suggestion_generated": False, "suggestion_count": 0,
            "fallback_used": False,
            "error_message": None, "auto_quality_flags": {},
            "human_review_required": True, "notes": "",
        }
        try:
            start = time.perf_counter()
            parsed = parse_github_pr_url(case["pr_url"])
            token = os.getenv("GITHUB_TOKEN") or None
            info = fetch_pr_info(parsed.owner, parsed.repo, parsed.pull_number, token=token)
            files = fetch_pr_files(parsed.owner, parsed.repo, parsed.pull_number, token=token,
                                   per_page=min(EVAL_MAX_FILES, 100), max_files=EVAL_MAX_FILES)
            ctx = build_diff_context(files, max_file_chars=EVAL_MAX_PATCH_CHARS,
                                     max_total_chars=EVAL_MAX_TOTAL_CHARS)
            r["files_total"] = ctx.total_files
            r["files_included"] = ctx.included_files
            r["files_skipped"] = ctx.skipped_files
            r["diff_chars_before"] = ctx.original_total_chars
            r["diff_chars_after"] = ctx.processed_total_chars
            r["truncated"] = ctx.was_truncated

            cfg = load_llm_config_from_env()
            lang = "en"

            # Summary
            summary = generate_pr_summary(info, ctx, cfg, output_language=lang)
            r["summary_generated"] = True
            r["summary_result"] = summary

            do_risk = mode in ("standard", "full")
            risk = None
            if do_risk:
                risk = analyze_pr_risks(info, ctx, cfg, output_language=lang)
                r["risk_generated"] = True
                r["risk_count"] = len(risk.risk_items) if risk.risk_items else 0
                for lim in (risk.limitations or []):
                    lo = lim.lower()
                    if any(k in lo for k in ("empty content", "could not be parsed", "空内容", "未能解析")):
                        r["fallback_used"] = True
                        break
                r["risk_result"] = risk

            do_sug = mode == "full"
            sug_res = None
            if do_sug:
                sug_res = generate_review_suggestions(info, ctx, risk, cfg, output_language=lang)
                r["suggestion_generated"] = True
                r["suggestion_count"] = len(sug_res.suggestions) if sug_res.suggestions else 0
                r["suggestions_result"] = sug_res

            r["elapsed_seconds"] = round(time.perf_counter() - start, 2)
            r["status"] = "success"
        except LLMConfigError as e:
            r["status"] = "skipped"; r["error_message"] = str(e)[:200]
        except (GitHubClientError, PRUrlParseError, LLMClientError,
                SummaryAnalyzerError, RiskAnalyzerError, ReviewSuggestionError, Exception) as e:
            r["status"] = "error"; r["error_message"] = f"{type(e).__name__}: {str(e)[:200]}"
        r["auto_quality_flags"] = _auto_flags(r)
        results.append(r)
        time.sleep(0.3)
    return results


def generate_report(results: list[dict], output_path: Path):
    succ = [c for c in results if c["status"] == "success"]
    errs = [c for c in results if c["status"] == "error"]
    skips = [c for c in results if c["status"] == "skipped"]
    times = [c["elapsed_seconds"] for c in succ if c["elapsed_seconds"]]
    avg_t = sum(times) / len(times) if times else 0
    fallbacks = sum(1 for c in succ if c["fallback_used"])
    risks_nonzero = sum(1 for c in succ if c["risk_count"] > 0)
    sug_nonzero = sum(1 for c in succ if c["suggestion_count"] > 0)
    truncated = sum(1 for c in succ if c.get("truncated"))

    rows = []
    for c in results:
        rows.append(
            f"| {c['case_id']} | {c['pr_type']} | {c['mode']} | {c['status']} | "
            f"{c['elapsed_seconds'] or '-'} | {c['risk_count']} | {c['suggestion_count']} | "
            f"{'Yes' if c['fallback_used'] else '-'} | {'Yes' if c.get('truncated') else '-'} | "
            f"Summary={'✓' if c['auto_quality_flags'].get('summary_non_empty') else '✕'} |"
        )

    hr_rows = []
    for c in results:
        hr_rows.append(
            f"| {c['case_id']} | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |"
        )

    md = f"""# PRLens 自动测评与人工复核报告

## 1. 测评目的

验证 PRLens 在分析准确性、上下文理解、误报与漏报控制、响应速度和使用体验方面的表现。

## 2. 测评集设计

测评集共 {len(results)} 次运行，覆盖 8 个内部 PR 和 6 个外部 PR。

- **内部 PR** (I1-I8)：验证 PRLens 对自身仓库文档型、工具型变更的理解，重点检查是否产生高风险误报
- **外部 PR** (E1-E6)：覆盖 bug fix、测试变更、平台兼容性、API 设计争议、外部文档 PR
- Full 模式仅对 I5/I6/E1/E2 启用，控制测评成本

## 3. 测评方法

- 标准模式 (Summary + Risk) 覆盖所有案例；Full (Summary + Risk + Suggestions) 仅覆盖 4 个案例
- 测评层面 diff 限制: max_files={EVAL_MAX_FILES}, max_patch_chars={EVAL_MAX_PATCH_CHARS}, max_total_chars={EVAL_MAX_TOTAL_CHARS}
- 记录耗时、风险数量、fallback 次数、suggestion 数量等客观指标
- 准确性、误报、漏报仅做自动初判，必须人工复核

## 4. 测评结果总览

| 案例 | 类型 | 模式 | 状态 | 耗时(s) | Risk数 | Sug数 | Fallback | 截断 | 自动初判 |
|---|---|---|---|---|---:|---:|---:|---|---|---|
{chr(10).join(rows)}

**统计**: {len(succ)} 成功 / {len(errs)} 失败 / {len(skips)} 跳过 | 平均耗时 {avg_t:.1f}s | Fallback {fallbacks} 次 | risk>0: {risks_nonzero} 案例 | sug>0: {sug_nonzero} 案例 | 截断: {truncated} 次

## 5. 分类观察

### 5.1 文档型 PR
内部文档型 PR (I1, I8) 和外部文档 PR (E5): 检查 Summary 是否生成，是否无高风险误报。

### 5.2 小型 bug fix
E1 (requests#7004): 极小 diff 的边界条件修复，检查风险识别是否合理。

### 5.3 测试与兼容性变更
E2 (click#3126), E4 (click#2969): 含测试变更的 bug fix，检查测试缺失提示。

### 5.4 API / 设计争议 PR
E6 (fastapi#10694): 含大量讨论的 API 行为变更，检查是否理解 PR 背景。

### 5.5 完整模式与 Review Suggestions
I5, I6, E1, E2 运行 Full 模式，检查 Suggestions 是否在存在风险时生成。

## 6. 对题干维度的回应

| 题干维度 | 如何验证 | 当前证据 | 仍需人工判断 |
|---|---|---|---|
| 分析准确性 | Summary 是否生成、Risk evidence 是否有 | Summary 生成率, evidence 检查 | 是 |
| 上下文理解 | PR metadata + diff 是否被正确处理 | 文件统计、截断标记 | 是 |
| 误报控制 | 文档型 PR 是否有高风险 | no_high_risk_for_docs 标记 | 是 |
| 漏报控制 | 外部 bug fix PR 是否识别出风险 | risk_count 统计 | 是 |
| 响应速度 | 每个案例耗时 | 平均 {avg_t:.1f}s | 否 |
| 使用体验 | 进度反馈、模式、导出 | Demo 已验证 | 部分 |

## 7. 人工复核记录

| 案例 | Summary准确性 | 上下文理解 | 风险合理性 | 明显误报 | 明显漏报 | 人工结论 |
|---|---:|---:|---:|---|---|---|
{chr(10).join(hr_rows)}

## 8. 局限性

- 自动测评不能替代人工 Review
- 测评样本 14 个案例，类型覆盖有限
- LLM 输出可能波动
- 外部 PR 类型仍有限（小型 bug fix 为主）
- 大型 PR 可能受 diff 截断影响（测评限制为 {EVAL_MAX_FILES} 文件 / {EVAL_MAX_TOTAL_CHARS} 字符）
- Review Suggestions 触发依赖于 Risk 先识别出风险项

## 9. 后续优化方向

- 扩大 golden cases 集合，引入人工标注
- 增加仓库级上下文检索
- 接入团队规则库
- 建立反馈闭环
- 降低 fallback 率，提升响应速度
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved: {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-stress", action="store_true")
    parser.add_argument("--case", type=str, default=None)
    parser.add_argument("--mode", type=str, default=None)
    args = parser.parse_args()

    cases_path = ROOT_DIR / "docs" / "evaluation_cases.json"
    cases = load_cases(cases_path)

    if args.include_stress:
        stress_path = ROOT_DIR / "docs" / "evaluation_stress_cases.json"
        if stress_path.exists():
            cases += load_cases(stress_path)

    # Filter
    if args.case:
        cases = [c for c in cases if c["case_id"] == args.case]
    if args.mode:
        for c in cases:
            c["modes"] = [args.mode]

    if not cases:
        print("No cases selected.")
        return

    print(f"Running {len(cases)} cases...")
    all_results = []
    for case in cases:
        print(f"\n[{case['case_id']}] {case.get('focus', '')} — modes: {case['modes']}")
        for r in run_case(case):
            print(f"  {r['mode']}: {r['status']} | {r['elapsed_seconds']}s | risk={r['risk_count']} | sug={r['suggestion_count']} | fb={r['fallback_used']}")
            all_results.append(r)

    out_path = ROOT_DIR / "docs" / "evaluation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "Authesqwq/xengineer-prlens",
        "limits": {"max_files": EVAL_MAX_FILES, "max_patch_chars": EVAL_MAX_PATCH_CHARS, "max_total_chars": EVAL_MAX_TOTAL_CHARS},
        "total_runs": len(all_results),
        "cases": all_results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    succ = sum(1 for r in all_results if r["status"] == "success")
    errs = sum(1 for r in all_results if r["status"] == "error")
    skips = sum(1 for r in all_results if r["status"] == "skipped")
    print(f"\nDone. {succ} succeeded, {skips} skipped, {errs} errors")

    generate_report(all_results, ROOT_DIR / "docs" / "evaluation_report.md")


if __name__ == "__main__":
    main()
