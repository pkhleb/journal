"""Model variants for backtesting. Each implements predict()/update() and
wraps the same production functions in app.predictor.mixer — no logic is
reimplemented here, so a model that wins offline behaves identically online.
"""
from typing import Protocol
from app.predictor.mixer import DEFAULT_WEIGHTS, weight_candidates, apply_ranking_update

# Isolated weight configs — comparing these directly shows what each signal
# contributes independently, rather than only ever seeing them combined.
NONE_WEIGHTS = {
    "transition": 0.4, "weekday": 0.1, "recency": 0.5,
}
PHASE_ONLY_WEIGHTS = {
    "transition": 0.25, "phase_transition": 0.15, "weekday": 0.1, "recency": 0.5,
}
POSITION_ONLY_WEIGHTS = {
    "transition": 0.25, "weekday": 0.1, "position_freq": 0.15, "recency": 0.5,
}
PRECEDENCE_ONLY_WEIGHTS = {
    "transition": 0.25, "weekday": 0.1, "session_precedence": 0.15, "recency": 0.5,
}
# DEFAULT_WEIGHTS (imported above) = all three signals combined

NO_PHASE_NO_POSITION_WEIGHTS = NONE_WEIGHTS  # kept for backward compatibility
PRE_PHASE_WEIGHTS = NONE_WEIGHTS  # kept for backward compatibility


class RankerModel(Protocol):
    name: str
    def predict(self, candidates: list[dict]) -> list[str]: ...
    def update(self, candidates: list[dict], chosen_exercise: str) -> None: ...


class StaticWeightsModel:
    """No learning — just fixed weights. Used both as the original baseline
    (PRE_PHASE_WEIGHTS) and as the new baseline (DEFAULT_WEIGHTS, which now
    includes phase_transition) — comparing these two IS the "does phase
    awareness help at all" experiment, independent of any online learning."""

    def __init__(self, weights: dict | None = None, name: str = "static_weights"):
        self.weights = dict(weights or DEFAULT_WEIGHTS)
        self.name = name

    def predict(self, candidates: list[dict]) -> list[str]:
        return weight_candidates(candidates, self.weights)

    def update(self, candidates: list[dict], chosen_exercise: str) -> None:
        pass  # intentionally static


class MixerModel:
    """Online mixer in either update mode."""

    def __init__(
        self, mode: str = "miss_only", weights: dict | None = None,
        prior: dict | None = None, top_k: int = 3, lr: float = 0.05, l2: float = 0.1,
        name: str | None = None,
    ):
        self.mode = mode
        self.name = name or f"{mode}_mixer"
        self.weights = dict(weights or DEFAULT_WEIGHTS)
        self.prior = dict(prior or DEFAULT_WEIGHTS)
        self.top_k = top_k
        self.lr = lr
        self.l2 = l2

    def predict(self, candidates: list[dict]) -> list[str]:
        return weight_candidates(candidates, self.weights)

    def update(self, candidates: list[dict], chosen_exercise: str) -> None:
        new_weights, _info = apply_ranking_update(
            candidates, chosen_exercise, self.weights, self.prior,
            top_k=self.top_k, lr=self.lr, l2=self.l2, mode=self.mode,
        )
        self.weights = new_weights


def default_model_factories() -> dict[str, callable]:
    """Isolates each new feature's contribution before looking at online
    learning at all: none -> phase_only/position_only/precedence_only ->
    all_signals (DEFAULT_WEIGHTS) shows what each signal adds independently
    and whether they stack additively when combined."""
    return {
        "none": lambda: StaticWeightsModel(weights=NONE_WEIGHTS, name="none"),
        "phase_only": lambda: StaticWeightsModel(weights=PHASE_ONLY_WEIGHTS, name="phase_only"),
        "position_only": lambda: StaticWeightsModel(weights=POSITION_ONLY_WEIGHTS, name="position_only"),
        "precedence_only": lambda: StaticWeightsModel(weights=PRECEDENCE_ONLY_WEIGHTS, name="precedence_only"),
        "all_signals": lambda: StaticWeightsModel(weights=DEFAULT_WEIGHTS, name="all_signals"),
        "miss_only_mixer": lambda: MixerModel(mode="miss_only"),
        "always_update_mixer": lambda: MixerModel(mode="always"),
    }
