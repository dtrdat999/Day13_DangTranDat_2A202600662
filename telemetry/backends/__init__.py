"""Observability backends: where a finished trace is sent (Track 4).

Same factory/abstraction pattern as src/core providers: pick a backend via the
OBS_BACKEND env var. Default backends need NO API key (file/console/sqlite) so the
zero-key path works; the langfuse backend activates only when keys are present.
"""
