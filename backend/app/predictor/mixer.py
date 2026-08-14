import numpy as np

FEATURE_ORDER = ["transition", "weekday", "recency"]

DEFAULT_WEIGHTS = {
    "transition": 0.4,
    "weekday": 0.1,
    "recency": 0.5,
}


def weight_candidates(candidates: list[dict], weights: dict = DEFAULT_WEIGHTS) -> list[str]:
    """Combines feature vectors into a single score per candidate, sorted descending."""
    scored = [
        (c["exercise"], sum(weights[k] * c["features"][k] for k in FEATURE_ORDER))
        for c in candidates
    ]
    return [name for name, _ in sorted(scored, key=lambda x: x[1], reverse=True)]


def _to_matrix(candidates: list[dict]) -> np.ndarray:
    return np.array([[c["features"][k] for k in FEATURE_ORDER] for c in candidates])


def apply_ranking_update(
    candidates: list[dict],
    chosen_exercise: str,
    weights: dict,
    prior_weights: dict,
    top_k: int = 3,
    lr: float = 0.05,
    l2: float = 0.1,
    mode: str = "miss_only",
) -> tuple[dict, dict]:
    """Structured-perceptron ranking update, generalized over two modes:

    - "miss_only": only update when the chosen exercise falls outside the
      top_k. Hits are free passes.
    - "always": also updates on hits, nudging the chosen exercise past
      whatever's currently ranked #1 (unless it's already #1) — lets the
      model keep sharpening an already-correct ranking instead of treating
      every hit as equally fine.

    Returns (new_weights, info) where info = {"hit": bool, "rank": int, "updated": bool}.
    """
    names = [c["exercise"] for c in candidates]
    if chosen_exercise not in names:
        return weights, {"hit": None, "rank": None, "updated": False}

    w = np.array([weights[k] for k in FEATURE_ORDER])
    w_prior = np.array([prior_weights[k] for k in FEATURE_ORDER])
    features = _to_matrix(candidates)
    chosen_idx = names.index(chosen_exercise)

    scores = features @ w
    order = np.argsort(-scores, kind="stable")
    rank = int(np.where(order == chosen_idx)[0][0])

    k = min(top_k, len(order))
    hit = rank < k

    if hit:
        if mode == "miss_only" or rank == 0:
            return weights, {"hit": True, "rank": rank, "updated": False}
        violators = np.array([order[0]])  # "always": nudge past #1 only
    else:
        violators = order[:k]

    chosen_feat = features[chosen_idx]
    grad = np.mean([features[v] - chosen_feat for v in violators], axis=0)
    grad += l2 * (w - w_prior)
    w_new = w - lr * grad

    new_weights = {k_: float(v) for k_, v in zip(FEATURE_ORDER, w_new)}
    return new_weights, {"hit": hit, "rank": rank, "updated": True}


def apply_miss_only_update(
    candidates: list[dict],
    chosen_exercise: str,
    weights: dict,
    prior_weights: dict,
    top_k: int = 3,
    lr: float = 0.05,
    l2: float = 0.1,
) -> tuple[dict, dict]:
    """Kept as-is for existing callers (predictor/service.py) — thin wrapper
    around apply_ranking_update with mode="miss_only" fixed, so production
    behavior and signature are both unchanged."""
    return apply_ranking_update(
        candidates, chosen_exercise, weights, prior_weights, top_k, lr, l2, mode="miss_only"
    )
