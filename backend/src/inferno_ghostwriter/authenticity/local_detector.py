"""Real AI-text detector models, run locally and calibrated to the author's own posts.

Any mix of these models can score a post (``CATALOG``; the author picks them in Settings, the first one is the default):

- **Light check** (built in, no download): sentence rhythm, voice markers and detail (``light_detector``).
- **Fast-DetectGPT** (zero-shot): how close each sentence is to what a small language model would have written.
- **An AI-text classifier**: a model trained to tell human from machine text, scored per paragraph.

The two trained models run in ``detector_worker.py`` through ``uv run --no-project --with torch --with transformers``: the heavy packages
live in uv's cache, never in the app's environment, and one worker process stays up so models load once. Nothing is
downloaded until the author selects one of them in Settings (``setup_detector``).

Every model is compared with the author's own posts, scored once and cached: the goal is to read like the author,
whose real writing is human by definition, not to chase a number lower than theirs.
"""

from __future__ import annotations

import asyncio
import contextlib
import glob
import hashlib
import json
import logging
import os
import shutil
import statistics
import subprocess
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from inferno_ghostwriter.authenticity.light_detector import light_result
from inferno_ghostwriter.authenticity.passages import split_paragraphs
from inferno_ghostwriter.authenticity.texture import prose_sentences
from inferno_ghostwriter.config import FROZEN, Settings

log = logging.getLogger(__name__)

WORKER = Path(__file__).with_name("detector_worker.py")
PACKAGES = ("torch>=2.6", "transformers>=4.46,<6")
SETUP_TIMEOUT = 3600
SCORE_TIMEOUT = 900
MIN_SENTENCE_WORDS = 6
MAX_OUTLIERS = 10
CALIBRATION_VERSION = 1

# Without the author's own posts: where plain human prose usually sits for each model.
GENERIC = {"light": (0.38, 0.12), "curvature": (0.0, 1.0), "classifier": (0.1, 0.15)}
# Spread floors, so an author whose posts score alike is not held to an impossibly narrow band.
MIN_SPREAD = {"light": 0.06, "curvature": 0.5, "classifier": 0.08}
LABELS = {"light": "Light check (built in)", "curvature": "Fast-DetectGPT (zero-shot)", "classifier": "AI-text classifier"}


class DetectorError(RuntimeError):
    pass


@dataclass
class DetectorInput:
    sentences: list[str]
    paragraphs: list[str]


def detector_input(markdown: str) -> DetectorInput:
    return DetectorInput(
        sentences=prose_sentences(markdown),
        paragraphs=[p.text for p in split_paragraphs(markdown)],
    )


@dataclass(frozen=True)
class DetectorModel:
    """One selectable detector. ``id`` is the key of its result; ``part`` is what it scores inside a post."""

    id: str
    label: str
    summary: str
    part: Literal["sentences", "paragraphs"]
    # Needs the one-time PyTorch and model download (everything else runs in the app's own process).
    heavy: bool
    size: str
    # How much the model counts in the average of the selected ones (the light check is a rougher signal).
    weight: float = 1.0
    # The key the worker process reads the model's name under (trained models only).
    worker_kind: str = ""


CATALOG: tuple[DetectorModel, ...] = (
    DetectorModel(
        "light",
        LABELS["light"],
        "Instant and private: reads sentence rhythm, personal markers and concrete detail. A rougher signal than the trained models.",
        "sentences",
        False,
        "built in",
        weight=0.5,
    ),
    DetectorModel(
        "curvature",
        LABELS["curvature"],
        "Fast-DetectGPT on GPT-2: how close each sentence is to what a small language model would have written.",
        "sentences",
        True,
        "about 0.6 GB with PyTorch",
        worker_kind="zero_shot",
    ),
    DetectorModel(
        "classifier",
        LABELS["classifier"],
        "A RoBERTa model trained to tell human from AI text, scored per paragraph.",
        "paragraphs",
        True,
        "about 0.7 GB with PyTorch",
        worker_kind="classifier",
    ),
)
BY_ID = {m.id: m for m in CATALOG}
DEFAULT_MODELS = ["light"]


def clean_selection(ids: Sequence[str]) -> list[str]:
    """Known detector ids, once each, in catalog order (an empty list turns the detectors off)."""
    return [m.id for m in CATALOG if m.id in set(ids)]


def selected_models(settings: Settings) -> list[str]:
    return clean_selection(settings.detector_models)


class Detector(Protocol):
    """Scores texts with the selected detectors. Each result holds one entry per detector id (``light``, ``curvature``,
    ``classifier``); ``models`` maps each id to the model's name."""

    models: dict[str, str]

    async def score(self, items: Sequence[DetectorInput]) -> list[dict[str, Any]]: ...


# -- the worker process --------------------------------------------------------------------


def find_uv() -> str | None:
    """uv sets UV for the processes it starts; otherwise PATH, then the usual install folders."""
    candidates = [os.environ.get("UV"), shutil.which("uv")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates += sorted(glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "astral-sh.uv_*", "uv.exe")))
    home = Path.home()
    candidates += [str(home / ".local" / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")), str(home / ".cargo" / "bin" / "uv")]
    return next((c for c in candidates if c and Path(c).is_file()), None)


def detector_home(settings: Settings) -> Path:
    return settings.data_dir / "detector"


def _ready_marker(settings: Settings) -> Path:
    return detector_home(settings) / "ready.json"


def worker_models(settings: Settings, ids: Sequence[str] | None = None) -> dict[str, str]:
    """The worker's ``{kind: Hugging Face id}`` for these trained detectors (default: all of them)."""
    names = _names(settings)
    return {BY_ID[i].worker_kind: names[i] for i in (ids if ids is not None else names) if names.get(i)}


def _names(settings: Settings) -> dict[str, str]:
    return {"curvature": settings.detector_zero_shot_model, "classifier": settings.detector_classifier_model}


def installed_models(settings: Settings) -> dict[str, str]:
    """The ``{kind: Hugging Face id}`` the one-time setup has downloaded."""
    marker = _ready_marker(settings)
    try:
        data = json.loads(marker.read_text(encoding="utf-8")).get("models") if marker.is_file() else {}
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _is_installed(settings: Settings, model_id: str) -> bool:
    if not BY_ID[model_id].heavy:
        return True
    return worker_models(settings, [model_id]).items() <= installed_models(settings).items()


def _uv(settings: Settings) -> str | None:
    return None if FROZEN else find_uv()


def active_models(settings: Settings) -> list[str]:
    """The selected detectors that can run right now: the built-in one always, trained ones once set up."""
    selected = selected_models(settings)
    if settings.demo:
        return selected
    uv = _uv(settings)
    return [i for i in selected if not BY_ID[i].heavy or (uv is not None and _is_installed(settings, i))]


class UvDetector:
    """The real models, in one long-lived worker process started with uv."""

    def __init__(self, settings: Settings, uv: str, models: dict[str, str] | None = None) -> None:
        self.settings = settings
        self.uv = uv
        # {worker kind: Hugging Face id} of the models this process loads.
        self.models = models if models is not None else worker_models(settings)
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def _command(self, *, serve: bool) -> list[str]:
        command = [self.uv, "run", "--no-project", "--quiet"]
        for package in PACKAGES:
            command += ["--with", package]
        command += ["python", "-I", str(WORKER)]
        return [*command, "--serve"] if serve else command

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "VIRTUAL_ENV", "UV_PROJECT"))}
        home = detector_home(self.settings)
        env["HF_HOME"] = str(home / "hf")
        env["HF_HUB_DISABLE_TELEMETRY"] = "1"
        env["TRANSFORMERS_VERBOSITY"] = "error"
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _start(self) -> subprocess.Popen[str]:
        detector_home(self.settings).mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            self._command(serve=True),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=self._env(),
            cwd=str(detector_home(self.settings)),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert process.stdout is not None
        hello = process.stdout.readline()
        if not hello.strip():
            process.kill()
            raise DetectorError("The detector models could not start. Turn them off and on again in Settings to reinstall.")
        return process

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for attempt in (1, 2):
                if self._process is None or self._process.poll() is not None:
                    self._process = self._start()
                process = self._process
                assert process.stdin is not None and process.stdout is not None
                try:
                    process.stdin.write(json.dumps(payload) + "\n")
                    process.stdin.flush()
                    line = process.stdout.readline()
                except OSError:
                    line = ""
                if line.strip():
                    reply = json.loads(line)
                    if "error" in reply:
                        raise DetectorError(f"Detector models failed: {reply['error']}")
                    return dict(reply)
                self.close()
                if attempt == 2:
                    raise DetectorError("The detector models stopped unexpectedly.")
            raise AssertionError("unreachable")

    def close(self) -> None:
        if self._process is not None:
            with contextlib.suppress(OSError):
                self._process.kill()
            self._process = None

    async def score(self, items: Sequence[DetectorInput]) -> list[dict[str, Any]]:
        payload = {**self.models, "texts": [{"sentences": i.sentences, "paragraphs": i.paragraphs} for i in items]}
        reply = await asyncio.wait_for(asyncio.to_thread(self._request, payload), SCORE_TIMEOUT)
        return list(reply.get("results", []))

    def warmup(self) -> dict[str, Any]:
        """Install the packages and download the models (the one-time setup), in a throwaway process."""
        detector_home(self.settings).mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            self._command(serve=False),
            input=json.dumps({**self.models, "warmup": True}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self._env(),
            cwd=str(detector_home(self.settings)),
            timeout=SETUP_TIMEOUT,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not result.stdout.strip():
            tail = (result.stderr or "").strip().splitlines()[-3:]
            raise DetectorError("Setting up the detector models failed: " + (" ".join(tail) or f"exit code {result.returncode}"))
        return dict(json.loads(result.stdout.strip().splitlines()[-1]))


_DETECTORS: dict[tuple[str, tuple[tuple[str, str], ...]], UvDetector] = {}


def model_info(settings: Settings) -> list[dict[str, Any]]:
    """Every selectable detector, with whether it is selected and (the trained ones) set up."""
    selected = set(selected_models(settings))
    return [
        {
            "id": m.id,
            "label": m.label,
            "summary": m.summary,
            "heavy": m.heavy,
            "size": m.size,
            "selected": m.id in selected,
            "installed": settings.demo or _is_installed(settings, m.id),
        }
        for m in CATALOG
    ]


def status(settings: Settings) -> dict[str, Any]:
    uv = _uv(settings)
    selected = selected_models(settings)
    missing = [i for i in selected if BY_ID[i].heavy and not (settings.demo or _is_installed(settings, i))]
    if settings.demo:
        detail = "Demo mode: simulated detector scores."
    elif not selected:
        detail = "No detector selected: pick at least one to check posts against your own writing."
    elif missing and uv is None:
        detail = "The trained models need uv (the app's installer tool), which is not available in this build."
    elif missing:
        names = " and ".join(BY_ID[i].label for i in missing)
        detail = f"{names}: not set up yet. A one-time download of about 1 GB (PyTorch and the model), shared by the trained models."
    elif any(BY_ID[i].heavy for i in selected):
        detail = "Ready. Models run on this computer; nothing is sent anywhere."
    else:
        detail = "Ready. The light check is built in and runs on this computer; nothing is sent anywhere."
    return {
        "available": settings.demo or uv is not None,
        "ready": settings.demo or not missing,
        "enabled": bool(active_models(settings)),
        "selected": selected,
        "models": model_info(settings),
        "detail": detail,
    }


class MultiDetector:
    """Runs the selected detectors together: the light check in this process, the trained models in the uv worker."""

    def __init__(self, settings: Settings, ids: Sequence[str], worker: UvDetector | None) -> None:
        self.ids = tuple(ids)
        self.worker = worker
        names = {"light": "built in", **_names(settings)}
        self.models = {i: names[i] for i in self.ids if i in names}

    async def score(self, items: Sequence[DetectorInput]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = [{} for _ in items]
        if "light" in self.ids:
            for result, item in zip(results, items, strict=True):
                result["light"] = light_result(item.sentences)
        if self.worker is not None:
            for result, scored in zip(results, await self.worker.score(items), strict=True):
                result.update({k: v for k, v in scored.items() if k in self.ids})
        return results


def get_detector(settings: Settings) -> Detector | None:
    """The detector for this check: the selected models that can run, or None when none is selected."""
    ids = active_models(settings)
    if not ids:
        return None
    if settings.demo:
        return FakeDetector(ids=ids)
    heavy = [i for i in ids if BY_ID[i].heavy]
    worker: UvDetector | None = None
    uv = _uv(settings)
    if heavy and uv is not None:
        models = worker_models(settings, heavy)
        key = (uv, tuple(sorted(models.items())))
        if key not in _DETECTORS:
            _DETECTORS[key] = UvDetector(settings, uv, models)
        worker = _DETECTORS[key]
    return MultiDetector(settings, ids, worker)


def setup_detector(settings: Settings, ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Install and download the selected trained models once, then mark them ready. Blocking: run it in a job thread."""
    heavy = [i for i in (ids if ids is not None else selected_models(settings)) if i in BY_ID and BY_ID[i].heavy]
    if not heavy:
        return {}
    uv = _uv(settings)
    if uv is None:
        raise DetectorError("The detector models need uv, which is not available in this build.")
    wanted = worker_models(settings, heavy)
    info = UvDetector(settings, uv, wanted).warmup()
    marker = _ready_marker(settings)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"models": {**installed_models(settings), **wanted}, "torch": info.get("torch")}), encoding="utf-8")
    return info


def shutdown() -> None:
    for detector in _DETECTORS.values():
        detector.close()
    _DETECTORS.clear()


# -- the fake, for tests and demo mode --------------------------------------------------------


class FakeDetector:
    """Deterministic scores from the text's shape: even, generic sentences read as "machine"."""

    def __init__(self, curvature: float | None = None, classifier: float | None = None, ids: Sequence[str] | None = None) -> None:
        self.ids = tuple(ids) if ids is not None else ("curvature", "classifier")
        names = {"light": "built in", "curvature": "fake-curvature", "classifier": "fake-classifier"}
        self.models = {i: names[i] for i in self.ids}
        self.fixed_curvature = curvature
        self.fixed_classifier = classifier
        self.calls = 0

    @staticmethod
    def _sentence(sentence: str) -> float:
        from inferno_ghostwriter.authenticity.texture import is_specific

        words = len(sentence.split())
        score = 1.2 if 12 <= words <= 24 else 0.3
        return round(score - (0.8 if is_specific(sentence) else 0.0) + (0.6 if "," in sentence else 0.0), 3)

    async def score(self, items: Sequence[DetectorInput]) -> list[dict[str, Any]]:
        self.calls += 1
        out = []
        for item in items:
            sentences = [self._sentence(s) for s in item.sentences]
            curvature = self.fixed_curvature if self.fixed_curvature is not None else (statistics.fmean(sentences) if sentences else None)
            paragraphs: list[float | None] = [
                min(0.99, max(0.01, 0.25 + 0.1 * self._sentence(p))) if len(p.split()) >= 8 else None for p in item.paragraphs
            ]
            known = [p for p in paragraphs if p is not None]
            classifier = self.fixed_classifier if self.fixed_classifier is not None else (statistics.fmean(known) if known else None)
            everything: dict[str, Any] = {
                "light": light_result(item.sentences),
                "curvature": {"score": curvature, "sentences": sentences},
                "classifier": {"score": classifier, "paragraphs": paragraphs},
            }
            out.append({k: v for k, v in everything.items() if k in self.ids})
        return out


# -- calibration and the report -----------------------------------------------------------------


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


@dataclass
class AuthorRange:
    """How the author's own posts score with each model: post-level values and the 90th percentile of the parts."""

    posts: dict[str, list[float]]
    part_p90: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {"posts": self.posts, "part_p90": self.part_p90}


def _range_from(results: Sequence[dict[str, Any]]) -> AuthorRange:
    posts: dict[str, list[float]] = {m.id: [] for m in CATALOG}
    parts: dict[str, list[float]] = {m.id: [] for m in CATALOG}
    for result in results:
        for model in CATALOG:
            entry = result.get(model.id) or {}
            if entry.get("score") is not None:
                posts[model.id].append(float(entry["score"]))
            parts[model.id].extend(float(v) for v in entry.get(model.part, []) if v is not None)
    return AuthorRange(posts=posts, part_p90={k: _percentile(v, 0.9) for k, v in parts.items() if len(v) >= 10})


def _cache_path(settings: Settings, detector: Detector, author_texts: Sequence[str]) -> Path:
    digest = hashlib.sha256(
        json.dumps([CALIBRATION_VERSION, detector.models, sorted(hashlib.sha256(t.encode()).hexdigest() for t in author_texts)]).encode()
    ).hexdigest()[:16]
    return detector_home(settings) / f"calibration-{digest}.json"


async def author_range(settings: Settings, detector: Detector, author_texts: Sequence[str]) -> AuthorRange | None:
    """Score the author's own posts once (cached on disk by content and model)."""
    texts = [t for t in author_texts if t.strip()]
    if not texts:
        return None
    path = _cache_path(settings, detector, texts)
    if path.is_file() and not isinstance(detector, FakeDetector):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return AuthorRange(posts=data["posts"], part_p90=data["part_p90"])
        except (OSError, ValueError, KeyError):
            pass
    found = _range_from(await detector.score([detector_input(t) for t in texts]))
    if not isinstance(detector, FakeDetector):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(found.as_dict()), encoding="utf-8")
        except OSError:
            log.warning("Could not cache the detector calibration at %s", path)
    return found


def model_score(key: str, value: float, author: Sequence[float]) -> tuple[int, float, float]:
    """0-100 (100 = inside the author's own range) and the range (low, high) the value was compared with."""
    if len(author) >= 2:
        mean = statistics.fmean(author)
        spread = max(statistics.pstdev(author), MIN_SPREAD[key])
        low, high = min(author), max(mean + spread, max(author))
    else:
        mean, spread = GENERIC[key]
        low, high = mean - spread, mean + spread
    z = (value - mean) / spread
    score = 100 if z <= 1 else max(0, round(100 - 30 * (z - 1)))
    return score, round(low, 3), round(high, 3)


def _verdict(key: str, score: int) -> str:
    if score >= 85:
        return "Within your own range"
    if score >= 55:
        return "A little more machine-like than your posts"
    return "Reads as machine-written to this model"


_REASONS = {
    "light": "reads as even and impersonal to the light check",
    "curvature": "reads as machine-written to the zero-shot model",
}


async def detector_report(*, settings: Settings, detector: Detector, markdown: str, author_texts: Sequence[str]) -> dict[str, Any]:
    """Score a post with every selected model, compare with the author's range, and list the passages that read as machine."""
    data = detector_input(markdown)
    author = await author_range(settings, detector, author_texts)
    [result] = await detector.score([data])
    models: list[dict[str, Any]] = []
    outliers: list[dict[str, Any]] = []
    weighted: list[tuple[int, float]] = []
    for model in CATALOG:
        entry = result.get(model.id) or {}
        value = entry.get("score")
        if value is None:
            continue
        key = model.id
        parts = data.sentences if model.part == "sentences" else data.paragraphs
        posts = author.posts.get(key, []) if author else []
        part_score, low, high = model_score(key, float(value), posts)
        weighted.append((part_score, model.weight))
        models.append(
            {
                "id": key,
                "label": model.label,
                "model": detector.models.get(key, ""),
                "value": round(float(value), 3),
                "author_low": low,
                "author_high": high,
                "calibrated": len(posts) >= 2,
                "score": part_score,
                "verdict": _verdict(key, part_score),
            }
        )
        generic_mean, generic_spread = GENERIC[key]
        threshold = (author.part_p90.get(key) if author else None) or generic_mean + 2 * generic_spread
        for text, part_value in zip(parts, entry.get(model.part, []), strict=False):
            if part_value is None or part_value <= threshold or len(text.split()) < MIN_SENTENCE_WORDS:
                continue
            outliers.append(
                {
                    "quote": text.strip() if model.part == "sentences" else _first_sentences(text),
                    "reason": _REASONS.get(key) or f"the classifier gives this paragraph a {round(100 * part_value)}% AI probability",
                    "suggestion": "",
                    "source": "detector",
                    "strength": round(float(part_value) - threshold, 3),
                }
            )
    outliers.sort(key=lambda o: o["strength"], reverse=True)
    total = sum(w for _, w in weighted)
    score = round(sum(v * w for v, w in weighted) / total) if total else None
    return {"score": score, "models": models, "outliers": outliers[:MAX_OUTLIERS]}


def _first_sentences(paragraph: str, limit: int = 2) -> str:
    from inferno_ghostwriter.ingest.stylometrics import split_sentences

    return " ".join(split_sentences(paragraph)[:limit]).strip() or paragraph.strip()
