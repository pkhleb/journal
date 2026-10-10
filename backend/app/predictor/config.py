"""Single source of truth for predictor configuration.

Everything here was previously scattered — FEATURE_ORDER/DEFAULT_WEIGHTS
lived in mixer.py, PHASE_CUTOFF/MIN_PHASE_SUPPORT lived in features.py, and
experiments/weight_sweep.py had accidentally redefined its own copy of
FEATURE_ORDER. That's exactly the kind of drift that causes silent bugs —
change one copy, forget the others, and features/weights/experiments
quietly disagree with each other. Everything importing any of these values
should import from here, not redefine them locally.
"""

import hashlib
import json

# The five validated features currently in production. Order matters here —
# it's the canonical ordering used to build feature vectors as arrays
# wherever numpy is involved (mixer.py's _to_matrix).
FEATURE_ORDER = ["transition", "phase_transition", "weekday", "position_freq", "recency"]

# Hand-tuned starting point / regularization anchor for the online mixer.
# Validated via backtest — see experiments/signals_validate.py results.
DEFAULT_WEIGHTS = {
    "transition": 0.135,
    "phase_transition": 0.396,
    "weekday": 0.236,
    "position_freq": 0.198,
    "recency": 0.034,
}

# A session's first PHASE_CUTOFF sets are "early" (compounds tend to go
# here), everything after is "late" (accessories). Validated via
# experiments/phase_sweep.py — best found: cutoff=15, support=2.
PHASE_CUTOFF = 15

# Below this many observed transitions for a given (phase, prev_exercise)
# pair, phase-specific data is too sparse to trust — fall back to the
# global (non-phased) transition signal instead.
MIN_PHASE_SUPPORT = 2

# session_precedence was tried and did NOT validate on held-out data (see
# journal-app memory / experiments/signals_validate.py results) — the
# feature computation still exists in features.py for future
# reconsideration with more data, but it's intentionally left out of
# FEATURE_ORDER/DEFAULT_WEIGHTS above so it isn't live.

def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:10]

# Identifies the *shape* of the model: which features exist, in what order.
# Stored alongside each user's learned weights. If it doesn't match, those
# weights were learned for a different features set and are discarded rather
# than served - a row written before a feature existed would otherwise score
# that feature at weight 0 and quietly serve an unvalidated model.

FEATURE_SIGNATURE = _digest(FEATURE_ORDER)

# Identifies the full configuration (features, default weights, phase
# parameters). Stamped on every prediction event so hit rates can be grouped
# by the config that produced them, and a metric shift tied to a deploy.
CONFIG_VERSION = _digest({
    "features": FEATURE_ORDER,
    "default_weights": DEFAULT_WEIGHTS,
    "phase_cutoff": PHASE_CUTOFF,
    "min_phase_support": MIN_PHASE_SUPPORT,
})
