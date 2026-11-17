"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate."""
    import math

    problems = []

    # 1. Any metric value in pr["metrics"] that is NaN or inf
    for k, v in pr.get("metrics", {}).items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {k} has invalid value {v}")

    # 2. len(pr["rows"]) != manifest items x len(manifest seeds)
    manifest = pr.get("manifest", {})
    expected_items = manifest.get("items")
    expected_seeds = manifest.get("seeds")
    if expected_items is not None and expected_seeds is not None:
        expected_count = expected_items * len(expected_seeds)
        if len(pr.get("rows", [])) != expected_count:
            problems.append(f"row count {len(pr.get('rows', []))} != expected {expected_count}")

    # 3. the (item_id, seed) set of PR differs from the baseline's
    pr_pairs = {(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])}
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}
    if pr_pairs != base_pairs:
        problems.append(f"(item_id, seed) set differs from baseline (diff={pr_pairs ^ base_pairs})")

    # 4. evaluator_failures non-empty, or a row whose value for a graded spec metric is None
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s)")
    spec_metric_ids = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS and m["id"] in pr.get("metrics", {})]
    for r in pr.get("rows", []):
        for mid in spec_metric_ids:
            if r.get(mid) is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for metric {mid}")
                break
        if problems and "None for metric" in problems[-1]:
            break

    # 5. an item's slice tags in PR rows differ from the baseline's
    base_slices = {r.get("item_id"): sorted(r.get("slices") or []) for r in base.get("rows", [])}
    for r in pr.get("rows", []):
        item_id = r.get("item_id")
        if item_id in base_slices and sorted(r.get("slices") or []) != base_slices[item_id]:
            problems.append(f"item {item_id} slices {r.get('slices')} differ from baseline {base_slices[item_id]}")
            break

    # 6. Ratchet with base_spec
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        base_m_map = {m["id"]: m for m in base_spec.get("metrics", [])}
        curr_m_map = {m["id"]: m for m in spec.get("metrics", [])}
        for mid, bm in base_m_map.items():
            if mid not in curr_m_map:
                problems.append(f"metric {mid} disappeared from spec")
                continue
            cm = curr_m_map[mid]
            if bm.get("blocking") and not cm.get("blocking"):
                problems.append(f"blocking metric {mid} became non-blocking")
            b_th = bm.get("threshold", {})
            c_th = cm.get("threshold", {})
            if "max" in b_th and ("max" not in c_th or c_th["max"] > b_th["max"]):
                problems.append(f"threshold max for {mid} loosened ({c_th.get('max')} > {b_th['max']})")
            if "min" in b_th and ("min" not in c_th or c_th["min"] < b_th["min"]):
                problems.append(f"threshold min for {mid} loosened ({c_th.get('min')} < {b_th['min']})")
            if b_th.get("no_significant_drop") and not c_th.get("no_significant_drop"):
                problems.append(f"no_significant_drop for {mid} dropped")

        base_sl_map = {s["name"]: s for s in base_spec.get("slices", [])}
        curr_sl_map = {s["name"]: s for s in spec.get("slices", [])}
        for sname, bsl in base_sl_map.items():
            if sname not in curr_sl_map:
                problems.append(f"slice {sname} dropped from spec")
                continue
            csl = curr_sl_map[sname]
            if bsl.get("blocking") and not csl.get("blocking"):
                problems.append(f"blocking slice {sname} became non-blocking")
            if "min" in bsl and ("min" not in csl or csl["min"] < bsl["min"]):
                problems.append(f"slice {sname} min loosened ({csl.get('min')} < {bsl['min']})")
            if bsl.get("no_significant_drop") and not csl.get("no_significant_drop"):
                problems.append(f"slice {sname} no_significant_drop dropped")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices", []):
        sname = sl["name"]
        metric = sl["metric"]
        min_th = sl.get("min")
        blocking = sl.get("blocking", False)
        no_drop = sl.get("no_significant_drop", False)

        pr_items = per_item(pr, metric, slice_name=sname)
        val = sum(pr_items.values()) / len(pr_items) if pr_items else 0.0

        verdict, note = "ok", ""
        if min_th is not None and val < min_th:
            verdict = "fail"

        if no_drop:
            base_items = per_item(base, metric, slice_name=sname)
            keys = sorted(set(pr_items) & set(base_items))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [pr_items[k] for k in keys],
                    [base_items[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"

        slice_id = f"slice:{sname}/{metric}"
        if verdict != "ok" and blocking:
            blocked.append(slice_id)
        label = "BLOCK" if (verdict != "ok" and blocking) else ("warn" if verdict != "ok" else "ok")
        lines.append(f"  {slice_id:<28} {val!s:<8} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
