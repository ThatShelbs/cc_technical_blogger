"""Persona evolution: learn from published posts.

When a post is published, the text the author shipped is compared with the text the app generated, and the
differences become a short action plan for the persona. When a post does well, its "secret sauce" goes into the
persona's playbook. The author reviews every proposal; applying one makes a new voice profile version.
"""

from proseferno.evolution.diff import baseline_hash, diff_digest, diff_segments, edit_rate
from proseferno.evolution.service import (
    EVOLUTION_JOBS,
    OUTCOMES,
    SAUCE_OUTCOMES,
    STAGES,
    EvolutionError,
    analyze,
    apply_evolution,
    change_stage,
    dismiss,
    fail_analyzing,
    latest_evolution,
    start_analysis,
    start_apply,
)

__all__ = [
    "EVOLUTION_JOBS",
    "OUTCOMES",
    "SAUCE_OUTCOMES",
    "STAGES",
    "EvolutionError",
    "analyze",
    "apply_evolution",
    "baseline_hash",
    "change_stage",
    "diff_digest",
    "diff_segments",
    "dismiss",
    "edit_rate",
    "fail_analyzing",
    "latest_evolution",
    "start_analysis",
    "start_apply",
]
