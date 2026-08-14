import numpy as np

FEATURE_ORDER = ["transition", "weekday", "recency"]

DEFAULT_WEIGHTS = {
    "transition": 0.4,
    "weekday": 0.1,
    "recency": 0.5,
}


def weight_candidates(candidates: list[dict], weights: dict = DEFAULT_WEIGHTS) -> list[str]:
    """Score and sort exercise candidates by their weighted feature values.

    Args:
        candidates: Candidate exercise list with feature vectors.
        weights: Mapping of feature names to their scalar weights.

    Returns:
        list[str]: Exercise names in descending score order.
    """
    scored = [
        (c["exercise"], sum(weights[k] * c["features"][k] for k in FEATURE_ORDER))
        for c in candidates
    ]
    return [name for name, _ in sorted(scored, key=lambda x: x[1], reverse=True)]


def _to_matrix(candidates: list[dict]) -> np.ndarray:
    """Convert feature dictionaries into a dense matrix for linear scoring.

    Args:
        candidates: Candidate exercise list with feature vectors.

    Returns:
        np.ndarray: Matrix shaped like (n_candidates, n_features).
    """
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
    """Apply a miss-only perceptron update to the feature weights.

    Args:
        candidates: Scored candidate exercise list.
        chosen_exercise: The exercise actually selected by the user.
        weights: Current model weights used during prediction.
        prior_weights: Reference weights from before the current decision.
        top_k: Number of top-ranked candidates considered in the miss condition.
        lr: Learning rate for the weight update.
        l2: Regularization term for the weight shift.

    Returns:
        tuple[dict, dict]: Updated weight mapping and metadata about hit/rank/update status.
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
