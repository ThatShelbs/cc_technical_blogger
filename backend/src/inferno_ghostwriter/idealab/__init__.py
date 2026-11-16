"""Idea Lab: decide what to write next.

A research base of what is happening in the field (free feeds read by code, plus Claude web search scouts), the
author's portfolio, and ranked ideas that each carry a title, brief and outline and can be sent straight to the
writer. See ``docs/idea-lab.md``.
"""

from inferno_ghostwriter.idealab.collect import HttpSignalCollector, NoSignalCollector, SignalCollector
from inferno_ghostwriter.idealab.research import RESEARCH_JOB
from inferno_ghostwriter.idealab.service import BRAINSTORM_JOB, IDEA_JOBS, IdeaLabError, fail_interrupted, idea_brief

__all__ = [
    "BRAINSTORM_JOB",
    "IDEA_JOBS",
    "RESEARCH_JOB",
    "HttpSignalCollector",
    "IdeaLabError",
    "NoSignalCollector",
    "SignalCollector",
    "fail_interrupted",
    "idea_brief",
]
