# Model drift scenario

Phase 19 replay fixture: keep the production process stable while shifting the
anomaly-score histogram from the calibrated baseline. The monitoring service
should emit `MODEL_DRIFT` without opening a process Case.
