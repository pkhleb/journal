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

def apply_miss_only_update(
    candidates: list[dict],
    chosen_exercise: str,
    weights: dict,
    prior_weights: dict,
    top_k: int = 3,
    lr: float = 0.05,
    l2: float = 0.1,
) -> tuple[dict, dict]:
    """Miss-only structured-perceptron raning update.

    Returns (new_weights, info) where info = {"hit": bool, "rank": int, "updated": bool}
    If chosen_exercise wasn't among candidates at all, returns the weights
    unchanged with updated=False - nothing to learn from.
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
        return weights, {"hit": True, "rank": rank, "updated": False}

    violators = order[:k]
    chosen_feat = features[chosen_idx]
    grad = np.mean([features[v] - chosen_feat for v in violators], axis=0)
    grad += l2 * (w - w_prior)
    w_new = w - lr * grad

    new_weights = {k_: float(v) for k_, v in zip(FEATURE_ORDER, w_new)}
    return new_weights, {"hit": False, "rank": rank, "updated": True}
