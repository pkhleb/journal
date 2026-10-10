# Predictor guide

The predictor module ranks exercises using a lightweight feature model and updates weights after a user chooses an exercise.

## Module roles

- `features.py`: extracts feature vectors from a user's exercise history
- `mixer.py`: scores candidates and applies miss-only learning updates
- `service.py`: orchestrates prediction and weight persistence for a user

## Scoring logic

The candidate features ('FEATURE_ORDER' in 'config.py') are:

- transition score: how often the previous exercise was followed by the candidate
- phase transition score: the same, but conditioned on early vs late in the session, backing off to the global transition when phase-specific data is sparse
- weekday score: how often the user performs the exercise on the current weekday
- position frequency: how often the candidate appears at this exact position in a session
- recency score: a decay-based freshness signal

The final weights are stored in `ModelWeights` and are updated after a user resolves a prediction event.

## Versioning and stored weights

`config.py` defines two identifiers:

- `FEATURE_SIGNATURE`: hash of `FEATURE_ORDER`. Stored inside each user's weights row (under the reserved key `_feature_signature`). A row whose signature doesn't match the current feature set, or that has no signature, is ignored and `DEFAULT_WEIGHTS` are served until the user's next update replaces it. Adding or removing a feature therefore resets learned weights automatically.
- `CONFIG_VERSION`: hash of the features, default weights and phase parameters. Stamped on every prediciton event as `data.config_version`, so hit rates can be grouped by the configuration that produced them. Compare hit rates only within one version.

Why: Scoring treats a missing weight as 0, while the update path fills it from defaults. A row written before a feature existed would silently serve that feature at weight 0 and log hits against a different model than the one served.

## Data flow

1. `service.predict()` fetches candidate exercise names and feature vectors.
2. `weight_candidates()` applies the stored per-feature weights.
3. A `PredictionEvent` is created to note the prediction context.
4. When a user chooses a real exercise, `resolve()` updates the weights with a miss-only learning rule.

## Operational note

Prediction events are intentionally resolved relative to a stale cutoff and are not automatically retrained indefinitely.
