"""Offline red-team evaluation of the heuristic injection guard.

Runs every corpus case through GuardService locally (no LLM calls),
prints a summary to stdout, and writes docs/guard-eval.md.

Usage (from repo root or backend/):
    backend/.venv/bin/python backend/evals/run.py            # evaluate, write report
    backend/.venv/bin/python backend/evals/run.py --json /tmp/baseline.json
    backend/.venv/bin/python backend/evals/run.py --compare /tmp/baseline.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.guard_service import GuardService  # noqa: E402

CORPUS = Path(__file__).with_name("corpus.jsonl")
REPORT = BACKEND.parent / "docs" / "guard-eval.md"

Case = dict[str, Any]


def load_corpus(path: Path) -> list[Case]:
    cases: list[Case] = []
    for lineno, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        if line.strip():
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"corpus.jsonl:{lineno}: bad JSON: {exc}")
    return cases


def evaluate(cases: list[Case], threshold: int) -> list[Case]:
    guard = GuardService(block_threshold=threshold)
    results: list[Case] = []
    for case in cases:
        verdict = guard.inspect(str(case["text"]))
        blocked = not verdict.allowed
        expected_block = case["expect"] == "block"
        results.append(
            {
                **case,
                "blocked": blocked,
                "correct": blocked == expected_block,
                "score": verdict.score,
                "categories": verdict.categories,
                "reasons": verdict.reasons,
            }
        )
    return results


def _rate(subset: list[Case]) -> float:
    return sum(1 for r in subset if r["correct"]) / len(subset) * 100


def summarize(results: list[Case]) -> dict[str, Any]:
    attacks = [r for r in results if r["expect"] == "block"]
    benign = [r for r in results if r["expect"] == "allow"]
    per_cat: dict[str, Any] = {}
    for cat in sorted({str(r["category"]) for r in results}):
        rows = [r for r in results if r["category"] == cat]
        per_cat[cat] = {"total": len(rows), "detected": sum(r["correct"] for r in rows)}
    return {
        "total": len(results),
        "n_block": len(attacks),
        "recall": _rate(attacks),
        "n_allow": len(benign),
        "fpr": 100 - _rate(benign),
        "per_category": per_cat,
        "bypasses": [r for r in attacks if not r["blocked"]],
        "false_positives": [r for r in benign if r["blocked"]],
    }


def render_markdown(out: dict[str, Any], threshold: int, header: str) -> str:
    per_cat = out["per_category"]
    assert isinstance(per_cat, dict)
    now = datetime.now(timezone.utc)
    n_block, n_allow = out["n_block"], out["n_allow"]
    benign_pass = n_allow - len(out["false_positives"])
    lines = [
        "# Prompt-injection guard evaluation",
        "",
        f"> {header}",
        f"> Run: {now.strftime('%Y-%m-%d %H:%M UTC')} · "
        f"threshold={threshold} · corpus={out['total']} cases",
        "",
        "## Summary",
        "",
        f"Evaluated on a labelled {out['total']}-case synthetic corpus at threshold "
        f"{threshold} on {now.strftime('%Y-%m-%d')} ({now.strftime('%H:%M UTC')}): "
        f"{n_block} attack cases and {n_allow} benign controls.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Injection recall (attacks blocked) | **{out['recall']:.1f}%** "
        f"({n_block - len(out['bypasses'])}/{n_block}) |",
        f"| Benign pass rate | **{benign_pass / n_allow * 100:.1f}%** "
        f"({benign_pass}/{n_allow}) |",
        f"| False-positive rate (benign blocked) | **{out['fpr']:.1f}%** "
        f"({len(out['false_positives'])}/{n_allow}) |",
        "",
        "The threshold was selected on this same corpus, so these are initial baseline",
        "figures rather than a production-scale benchmark. Threshold tuning should move to",
        "a separate validation set before the numbers are relied on.",
        "",
        "## Per category",
        "",
        "| Category | Detected | Rate |",
        "| --- | --- | --- |",
    ]
    for cat, st in per_cat.items():
        lines.append(f"| {cat} | {st['detected']}/{st['total']} | {st['detected'] / st['total'] * 100:.0f}% |")
    lines += ["", "## Bypasses (attacks the guard let through)", ""]
    bypasses = out["bypasses"]
    if bypasses:
        lines.append("| id | category | score | text |")
        lines.append("| --- | --- | --- | --- |")
        for r in bypasses:
            lines.append(f"| {r['id']} | {r['category']} | {r['score']} | {escape(r['text'])} |")
    else:
        lines.append("_None._")
    lines += ["", "## False positives (benign text blocked)", ""]
    fps = out["false_positives"]
    if fps:
        lines.append("| id | score | text |")
        lines.append("| --- | --- | --- |")
        for r in fps:
            lines.append(f"| {r['id']} | {r['score']} | {escape(r['text'])} |")
    else:
        lines.append("_None._")
    return "\n".join(lines) + "\n"


def escape(x: object) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=int, default=40, help="block threshold (default 40)")
    ap.add_argument("--json", type=Path, help="write raw per-case results as JSON")
    ap.add_argument("--compare", type=Path, help="JSON results from an earlier run; print delta, skip report")
    args = ap.parse_args()

    results = evaluate(load_corpus(CORPUS), args.threshold)
    out = summarize(results)

    if args.compare:
        base_results = json.loads(args.compare.read_text("utf-8"))
        base = summarize([dict(r) for r in base_results])
        print(f"recall {base['recall']:.1f}% -> {out['recall']:.1f}% "
              f"({out['recall'] - base['recall']:+.1f}pp)")
        print(f"false positives {base['fpr']:.1f}% -> {out['fpr']:.1f}% "
              f"({out['fpr'] - base['fpr']:+.1f}pp)")
        still = [r for r in results if r["expect"] == "block" and not r["blocked"]]
        print(f"still bypassing: {len(still)}")
        for r in still:
            print(f"  - [{r['id']}] {r['category']}: {escape(r['text'])}")
        return

    if args.json:
        args.json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"raw results -> {args.json}")

    md = render_markdown(out, args.threshold, "Guard hardening evaluation — after hardening")
    REPORT.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()