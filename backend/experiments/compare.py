"""Print a comparison table from already-saved result files.

Usage:
    python -m experiments.compare                  # latest run of each model
    python -m experiments.compare --all             # every result file, unfiltered
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"


def load_all() -> list[dict]:
    files = sorted(RESULTS_DIR.glob("*.json"))
    out = []
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
            data["_file"] = f.name
            out.append(data)
    return out


def latest_per_model(results: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for r in results:
        model = r["model"]
        if model not in latest or r["run_at"] > latest[model]["run_at"]:
            latest[model] = r
    return list(latest.values())


def print_table(results: list[dict]):
    print(f"\n{'model':<22} {'run_at':<18} {'n_events':>9} {'top1_acc':>9} {'top3_hit':>9} {'mean_mrr':>9}")
    print("-" * 82)
    for r in sorted(results, key=lambda r: r["model"]):
        s = r["summary"]
        if s["n_events"] == 0:
            print(f"{r['model']:<22} {r['run_at']:<18} {'(no scoreable events)':>40}")
            continue
        print(
            f"{r['model']:<22} {r['run_at']:<18} {s['n_events']:>9} "
            f"{s['top1_accuracy']:>9.3f} {s['top3_hit_rate']:>9.3f} {s['mean_mrr']:>9.3f}"
        )


if __name__ == "__main__":
    all_results = load_all()
    if not all_results:
        print(f"No result files found in {RESULTS_DIR}/ — run experiments/run.py first.")
        sys.exit(0)

    show_all = "--all" in sys.argv
    print_table(all_results if show_all else latest_per_model(all_results))
