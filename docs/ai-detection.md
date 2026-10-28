# AI-generation detection

Every generated post gets a **"reads as human" score from 0 to 100**: 100 means it reads as authentic human prose, 0 means an AI-text detector would almost certainly flag it. The score appears in the editor sidebar; **Full report** explains it and **Re-check** re-scores the current text after you edit.

| Score | Meaning |
| --- | --- |
| 80-100 | Reads as authentic human writing |
| 60-79 | Mostly human, with a few AI tells |
| 40-59 | Mixed: AI detectors may flag it |
| 0-39 | Highly probable AI generation |

## How it is scored

Two independent checks, combined (60% judge, 40% scan; the scan alone when the judge is off or unavailable):

1. **The scan** (`backend/src/proseferno/authenticity/heuristics.py`): free, instant and explainable. Each signal costs points:
   stock AI vocabulary ("delve", "game-changer", "it's important to note"), formulaic constructions ("it's not X, it's Y", "not just X, but Y", "Here's the thing"), uniform sentence rhythm (low variation in sentence length), uniform paragraph shapes, em dashes beyond your own rate, essay transitions ("Moreover,", "Furthermore,"), reflexive rule-of-three lists, "**Term:** explanation" bullet lists, emoji in headings, a stock summary ending, and fewer contractions than you normally use.
2. **The Claude judge** (`authenticity/detector.py`, prompts `detect_system.md` and `detect.md`): reads the post the way a detector and a skeptical editor would, confirms or overrules the scan, and quotes the passages most likely to be flagged with a suggestion for each.

The scan is **calibrated to you**: it learns from your own writing samples which "tells" are really your habits. If you use em dashes or the word "robust" in your own posts, the scan does not hold them against you. The judge sees your voice profile for the same reason.

## Fixing flagged passages

The report lists the passages a detector would catch. **Humanize** rewrites one in your voice with the tell removed (the same rewrite used by *Rewrite selection*), then **Re-check** re-scores the post.

The scan also runs inside generation: the editor pass sees the AI tells in the draft and the revision fixes them, so most posts arrive already cleaned up.

## Settings

**Settings → Advanced → AI-detection judge** turns the Claude judge on or off (the scan always runs). The judge is one short structured call per check at `low` effort (`PROSEFERNO_EFFORT_DETECT`), a few cents with Claude Opus 5.5.

## Eval

`backend/evals/ai_detection.py` scores the persona's own posts (calibration: they should score high, each held out of its own calibration) and every post Proseferno generated for it, then writes a Markdown and JSON report to `data/evals/`, like the [voice-fidelity eval](voice-pipeline.md#measuring-voice-fidelity).

```bash
cd backend
uv run python evals/ai_detection.py --persona "Your persona"               # scan only, free
uv run python evals/ai_detection.py --persona "Your persona" --judge --yes  # adds the Claude judge
uv run python evals/ai_detection.py --demo --judge --yes                    # wiring check, no API calls
```

The report gives the mean score of real and generated posts, the gap between them (0 = indistinguishable), how many generated posts fall below 60, and the most common tells. The voice-fidelity eval also reports scan scores for each held-out post and its generated twin.

No detector is perfect. Treat the score as an editor's second opinion, not a verdict.
