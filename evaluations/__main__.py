"""Run from the checkout: python -m evaluations [--output dist/phase02/eval.json]."""

import argparse
import json
import os
from pathlib import Path

from evaluations.runner import load_cases, run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", dest="case_ids", help="Select a corpus case ID (repeatable)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--suite", choices=("regression", "holdout", "development", "pipeline", "phase03",
                                           'phase04', 'phase04_development', 'phase04_assessment',
                                           'phase05', 'phase05_development', 'phase05_assessment'), default="regression")
    parser.add_argument("--live-approval", type=Path, help="Reviewed endpoint/model and whole-run budgets; required for live trials")
    parser.add_argument("--cohort", choices=("all", "phase01", "phase02"), default="all",
                        help="Score the unchanged original case IDs, additions only, or the whole corpus")
    parser.add_argument("--compact", action="store_true", help="Omit detailed trajectories from the output artifact")
    parser.add_argument("--strict", action="store_true", help="Also fail on documented known defects")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Explicit opt-in: send synthetic prompts to the configured model")
    mode.add_argument("--history", type=Path, help="Inventory private historical files locally; no model or DB execution")
    options = parser.parse_args(argv)
    if options.output is None:
        options.output = Path("dist/phase02/evaluation.json" if options.suite == "regression" else
                              ("dist/phase05/" if options.suite.startswith('phase05') else "dist/phase03/") + options.suite + ".json")
    try:
        if options.suite != "regression":
            if options.history or options.cohort != "all":
                parser.error("Phase 03 suites do not select historical/regression cohorts")
            from evaluations.trajectories import load_trajectories, run_trajectories
            if options.suite.startswith('phase05'):
                from evaluations.phase05 import load_cases as load_phase05
                cases = load_phase05(options.suite)
            elif options.suite.startswith('phase04'):
                from evaluations.phase04 import load_cases as load_phase04
                cases = load_phase04(options.suite)
            else:
                cases = load_trajectories(options.suite)
            if options.case_ids:
                if set(options.case_ids) - {case["id"] for case in cases}:
                    parser.error("Unknown trajectory ID")
                cases = [case for case in cases if case["id"] in options.case_ids]
            config, approval = None, None
            excluded_ids = []
            if options.live:
                if options.output.exists():
                    parser.error("Live output already exists; choose a new path to preserve first-attempt records")
                keys = ("SAGEQL_EVAL_API_KEY", "SAGEQL_EVAL_BASE_URL", "SAGEQL_EVAL_MODEL")
                if options.suite != "holdout" or options.live_approval is None or not all(os.environ.get(key) for key in keys):
                    parser.error("Live trials require --suite holdout, --live-approval and explicit evaluation configuration")
                from sageql import LLMConfig
                config = LLMConfig(*(os.environ[key] for key in keys))
                approval = json.loads(options.live_approval.read_text(encoding="utf-8"))
                excluded_ids = [case["id"] for case in cases if any(t.get("fault") or t.get("control") for t in case["turns"])]
                cases = [case for case in cases if case["id"] not in excluded_ids]
                if not cases:
                    parser.error("No eligible natural synthetic holdouts selected")
            def checkpoint(value):
                options.output.parent.mkdir(parents=True, exist_ok=True)
                options.output.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            result = run_trajectories(cases, live_config=config, approval=approval, checkpoint=checkpoint)
            result["live_excluded_cases"] = excluded_ids
            failed = bool(result["summary"]["failing_trajectories"] or result["unexecuted_trajectories"])
        elif options.history:
            if options.case_ids or options.cohort != "all":
                parser.error("--history does not select synthetic cases")
            from evaluations.history import inventory
            result = inventory(options.history)
            failed = not result["evidence_consistent"]
        else:
            cases = load_cases()
            if options.cohort != "all":
                archived = json.loads((Path(__file__).parent / "baselines" / "phase01_cases.json").read_text(encoding="utf-8"))
                original = {case["id"] for case in archived["cases"]}
                cases = [case for case in cases if (case["id"] in original) == (options.cohort == "phase01")]
            if options.case_ids:
                if set(options.case_ids) - {case["id"] for case in cases}:
                    parser.error("Unknown evaluation case ID")
                cases = [case for case in cases if case["id"] in options.case_ids]
            config = None
            if options.live:
                parser.error("Live evaluation now requires --suite holdout and a reviewed --live-approval file")
            result = run(cases, live_config=config)
            result["cohort"] = options.cohort
            failed = bool(result["summary"]["new_regressions"])
            if options.strict:
                failed = failed or bool(result["summary"]["known_failures"])
            if options.compact:
                result["results"] = [{key: value for key, value in row.items()
                                      if key not in {"stages", "validated_queries", "turns"}}
                                     for row in result["results"]]
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        # Historical/provider files and exception strings may contain private
        # data; do not echo them to a console or machine-readable artifact.
        print("Evaluation could not complete; check inputs and optional dependencies.")
        return 2
    print(json.dumps(result.get("summary", {}), indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
