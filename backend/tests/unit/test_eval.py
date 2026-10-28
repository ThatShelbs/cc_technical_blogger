"""The evals run end to end in demo mode (no API calls)."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from sqlmodel import Session

from proseferno.config import Settings
from proseferno.db import Persona, Project, Sample, VoiceProfile
from proseferno.ingest import parse_markdown
from proseferno.ingest.stylometrics import compute
from proseferno.services import build_services

EVALS = Path(__file__).resolve().parents[2] / "evals"


def load_eval(name: str = "voice_fidelity"):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name, EVALS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered so pydantic can resolve the module's postponed type annotations.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def post(topic: str) -> str:
    paragraph = f"I have opinions about {topic}. You probably do too. Here is why it matters, with a story and a joke. "
    return f"# {topic.title()}\n\n" + "\n\n".join(paragraph * 3 for _ in range(12))


async def test_eval_runs_in_demo_mode(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, demo=True, _env_file=None)  # type: ignore[call-arg]
    services = build_services(settings)
    with Session(services.engine) as session:
        persona = Persona(name="Evaluated", is_active=True)
        session.add(persona)
        session.commit()
        session.refresh(persona)
        for topic in ("pie charts", "uplift modeling", "word clouds"):
            doc = parse_markdown(post(topic))
            session.add(
                Sample(
                    persona_id=persona.id,  # type: ignore[arg-type]
                    kind="own",
                    source_name=f"{topic}.md",
                    source_type="md",
                    title=doc.title,
                    markdown=doc.to_markdown(),
                    word_count=doc.word_count,
                    stylometrics=compute(doc),
                )
            )
        session.add(VoiceProfile(persona_id=persona.id, version=1, markdown="# Voice Profile\n\n## Soul\nWry.", baseline_stylometrics={}))  # type: ignore[arg-type]
        session.commit()
    services.engine.dispose()

    module = load_eval()
    args = argparse.Namespace(persona=None, holdout=2, max_words=2500, seed=1, yes=True, demo=True, demo_dir=str(tmp_path))
    assert await module.run(args) == 0
    reports = list((tmp_path / "evals").glob("voice-fidelity-*.md"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "Judge accuracy" in text and "Evaluated" in text
    assert "Human score from the AI-detection scan" in text


async def test_ai_detection_eval_runs_in_demo_mode(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, demo=True, _env_file=None)  # type: ignore[call-arg]
    services = build_services(settings)
    with Session(services.engine) as session:
        persona = Persona(name="Detected", is_active=True)
        session.add(persona)
        session.commit()
        session.refresh(persona)
        for topic in ("pie charts", "word clouds"):
            doc = parse_markdown(post(topic))
            session.add(
                Sample(
                    persona_id=persona.id,  # type: ignore[arg-type]
                    kind="own",
                    source_name=f"{topic}.md",
                    source_type="md",
                    title=doc.title,
                    markdown=doc.to_markdown(),
                    word_count=doc.word_count,
                    stylometrics=compute(doc),
                )
            )
        session.add(Project(persona_id=persona.id, prompt="x", title="Generated", markdown=post("bar charts")))  # type: ignore[arg-type]
        session.commit()
    services.engine.dispose()

    module = load_eval("ai_detection")
    args = argparse.Namespace(persona=None, judge=True, max_samples=20, yes=True, demo=True, demo_dir=str(tmp_path))
    assert await module.run(args) == 0
    text = next((tmp_path / "evals").glob("ai-detection-*.md")).read_text(encoding="utf-8")
    assert "Real posts:" in text and "Generated posts:" in text and "| Generated | generated |" in text
