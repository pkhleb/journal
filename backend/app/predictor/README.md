# Predictor guide

The predictor module ranks exercises using a lightweight feature model and updates weights after a user chooses an exercise.

## Module roles

- `features.py`: extracts feature vectors from a user's exercise history
- `mixer.py`: scores candidates and applies miss-only learning updates
- `service.py`: orchestrates prediction and weight persistence for a user

## Scoring logic

The candidate features use:

- transition score: how often the previous exercise was followed by the candidate
- weekday score: how often the user performs the exercise on the current weekday
- recency score: a decay-based freshness signal

The final weights are stored in `ModelWeights` and are updated after a user resolves a prediction event.

## Data flow

1. `service.predict()` fetches candidate exercise names and feature vectors.
2. `weight_candidates()` applies the stored per-feature weights.
3. A `PredictionEvent` is created to note the prediction context.
4. When a user chooses a real exercise, `resolve()` updates the weights with a miss-only learning rule.

## Operational note

Prediction events are intentionally resolved relative to a stale cutoff and are not automatically retrained indefinitely.
