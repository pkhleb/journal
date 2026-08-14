"""Model variants for backtesting. Each implements predict()/update() and
wraps the same production functions in app.predictor.mixer — no logic is
reimplemented here, so a model that wins offline behaves identically online.
"""
from typing import Protocol
from app.predictor.mixer import DEFAULT_WEIGHTS, weight_candidates, apply_ranking_update


class RankerModel(Protocol):
    name: str
    def predict(self, candidates: list[dict]) -> list[str]: ...
    def update(self, candidates: list[dict], chosen_exercise: str) -> None: ...


class StaticWeightsModel:
    """The original hand-tuned baseline — no learning at all. This is what
    every other variant needs to beat to justify its added complexity."""
    name = "static_weights"

    def __init__(self, weights: dict | None = None):
        self.weights = dict(weights or DEFAULT_WEIGHTS)

    def predict(self, candidates: list[dict]) -> list[str]:
        return weight_candidates(candidates, self.weights)

    def update(self, candidates: list[dict], chosen_exercise: str) -> None:
        pass  # intentionally static


class MixerModel:
    """Online mixer in either update mode — this is what's actually live in
    production today, with mode="miss_only"."""

    def __init__(
        self, mode: str = "miss_only", weights: dict | None = None,
        prior: dict | None = None, top_k: int = 3, lr: float = 0.05, l2: float = 0.1,
    ):
        self.mode = mode
        self.name = f"{mode}_mixer"
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
    """The three-way comparison to start with. Each factory returns a fresh
    model instance — backtests need a clean model per run, not a shared one."""
    return {
        "static_weights": lambda: StaticWeightsModel(),
        "miss_only_mixer": lambda: MixerModel(mode="miss_only"),
        "always_update_mixer": lambda: MixerModel(mode="always"),
    }
