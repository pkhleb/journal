"""How often does phase_transition actually have enough support to differ
from the global transition score, vs falling back to it? Run this before
tuning PHASE_CUTOFF further — if backoff is near-universal, the cutoff
value can't matter much no matter what it's set to.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.phase_support_check your@email.com
"""
import asyncio
import sys
from collections import defaultdict
from zoneinfo import ZoneInfo

from app.predictor.features import PHASE_CUTOFF, MIN_PHASE_SUPPORT
from experiments.run import load_entries

LOCAL_TZ = ZoneInfo("America/New_York")


async def main(email: str):
    entries = await load_entries(email)
    print(f"Loaded {len(entries)} entries. PHASE_CUTOFF={PHASE_CUTOFF}, MIN_PHASE_SUPPORT={MIN_PHASE_SUPPORT}")

    last_in_day = {}
    day_position = defaultdict(int)
    phase_transition_counts = {"early": defaultdict(lambda: defaultdict(int)), "late": defaultdict(lambda: defaultdict(int))}

    total_predictions = 0
    supported_predictions = 0

    for entry in entries:
        day = entry["created_at"].astimezone(LOCAL_TZ).date()
        last_exercise = last_in_day.get(day)
        session_len = day_position[day]

        if last_exercise:
            phase = "early" if session_len < PHASE_CUTOFF else "late"
            phase_total = sum(phase_transition_counts[phase][last_exercise].values())
            total_predictions += 1
            if phase_total >= MIN_PHASE_SUPPORT:
                supported_predictions += 1

            phase_transition_counts[phase][last_exercise][entry["name"]] += 1

        last_in_day[day] = entry["name"]
        day_position[day] = session_len + 1

    rate = supported_predictions / total_predictions if total_predictions else 0
    print(f"\n{supported_predictions}/{total_predictions} predictions had enough phase-specific support ({rate:.1%})")
    print("If this is near 0%, phase_transition is almost always just backing off to the global transition score.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.phase_support_check <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
