"""Run the backtest comparison against real data.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.run your@email.com

Writes one JSON result file per model to experiments/results/, and prints a
summary table. Run experiments/compare.py afterward to re-print or compare
across separate runs.
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import User, Entry
from experiments.backtest import replay_history, summarize
from experiments.models import default_model_factories

RESULTS_DIR = Path(__file__).parent / "results"


async def load_entries(email: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise SystemExit(f"No user found for {email}")

        result = await db.execute(
            select(Entry)
            .where(Entry.user_id == user.id, Entry.metric_type == "exercise")
            .order_by(Entry.created_at.asc())
        )
        entries = result.scalars().all()

    out = []
    for e in entries:
        name = (e.metric_data or {}).get("name")
        if name:
            out.append({"name": name, "created_at": e.created_at})
    return out


def run_comparison(entries: list[dict]) -> dict[str, dict]:
    summaries = {}
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for name, factory in default_model_factories().items():
        model = factory()
        results = replay_history(entries, model)
        summary = summarize(results)
        summaries[name] = summary

        out_path = RESULTS_DIR / f"{name}_{timestamp}.json"
        with open(out_path, "w") as f:
            json.dump({
                "model": name,
                "run_at": timestamp,
                "n_source_entries": len(entries),
                "summary": summary,
                "final_weights": getattr(model, "weights", None),
            }, f, indent=2, default=str)

    return summaries


def print_table(summaries: dict[str, dict]):
    print(f"\n{'model':<22} {'n_events':>9} {'top1_acc':>9} {'top3_hit':>9} {'mean_mrr':>9}")
    print("-" * 62)
    for name, s in summaries.items():
        if s["n_events"] == 0:
            print(f"{name:<22} {'(no scoreable events)':>40}")
            continue
        print(
            f"{name:<22} {s['n_events']:>9} "
            f"{s['top1_accuracy']:>9.3f} {s['top3_hit_rate']:>9.3f} {s['mean_mrr']:>9.3f}"
        )


async def main(email: str):
    entries = await load_entries(email)
    print(f"Loaded {len(entries)} exercise entries for {email}")
    summaries = run_comparison(entries)
    print_table(summaries)
    print(f"\nResult files written to {RESULTS_DIR}/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.run <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
