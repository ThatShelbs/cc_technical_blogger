# AI-generation detection and humanizing

Every generated post gets a **"reads as human" score from 0 to 100**. 100 means it reads like your own writing; 0 means an AI-text detector would almost certainly flag it. The score appears in the editor sidebar, **Full report** explains it, and **Re-check** scores the current text again after you edit.

The same checks also steer the writing: after the editor's pass, a **humanize** round rewrites only the passages that read as machine-made, and keeps the new version only if it reads more like you.

| Score | Meaning |
| --- | --- |
| 80-100 | Reads as authentic human writing |
| 60-79 | Mostly human, with a few AI tells |
| 40-59 | Mixed: AI detectors may flag it |
| 0-39 | Highly probable AI generation |

## How it is scored

Four parts, each compared with **your own posts** (`backend/src/inferno_ghostwriter/authenticity/`). The weights are 40 / 30 / 15 / 15. When a part does not run, its weight is shared out among the others. A persona with no posts of its own (see [no-writing-samples.md](no-writing-samples.md)) has nothing to compare with, so the twin test is skipped and the rest are scored against a generic human range until you add posts.

1. **Detectors** (`local_detector.py`, `light_detector.py`, `detector_worker.py`). Pick any mix in Settings; each runs on your computer and scores every post against your own range (the average weights the light check half as much as a trained model):
   - **the light check** (default, built in): instant, no download. It reads what language models smooth out: even sentence lengths, few personal markers (contractions, "I" and "you", questions, asides), little concrete detail and repeated openings. A rougher signal than the trained models, so select one of them as well for a firmer read;
   - **Fast-DetectGPT** (zero-shot, on a small open language model, default `openai-community/gpt2`) scores each sentence by how close it is to what a language model would write;
   - **an AI-text classifier** (default `fakespot-ai/roberta-base-ai-text-detection-v1`, Apache-2.0) gives each paragraph an AI probability.

   Your own posts are scored once (cached in `data/detector/`), and a post is judged against **your** range. The goal is to read like you, not to score lower than your real writing. Sentences above your 90th percentile are flagged.
2. **The twin test** (`twin.py`, prompts `twin_system.md` / `twin.md`). Four passages from the post are shown blind to Claude. Each sits next to a real paragraph of yours that does the same job (an opening next to an opening, a story next to a story), and Claude says which one a human wrote, how sure it is, and what gave the other away.
   - A pair Claude cannot tell apart scores 100.
   - A giveaway is exactly what the humanize pass fixes.
   - Without posts of your own, a Claude judge (`detect_system.md`) reads the post the way a skeptical editor would instead.
3. **The tell scan** (`heuristics.py`). It is free, instant and explainable. Each of these costs points:
   - stock AI vocabulary ("delve", "game-changer");
   - formulaic constructions ("it's not X, it's Y");
   - uniform rhythm;
   - em dashes beyond your own rate;
   - essay transitions;
   - rule-of-three lists;
   - "**Term:** explanation" bullets;
   - emoji headings;
   - a stock summary ending;
   - fewer contractions than you use.

   Habits found in your own posts are not held against you.
4. **Texture** (`texture.py`). The shape of the post's sentences is compared with yours: the sentence-length mix, runs of same-length sentences, how many sentences carry a specific number, name or identifier, first person, the small-word fingerprint (*the, and, just, really*), and overused sentence openers. It lists the sentences that cause the biggest gaps.

## Humanizing

The writer works like a copilot that fills in the blanks the way you would. When the brief is thin, it invents vivid, plausible anecdotes, examples, scenarios and illustrative numbers in your storytelling style, because specific, lived-in prose is what reads as human. Technical facts, APIs, quotes and sources are never invented: references are checked against web search (see [references](references.md)). Review the post before publishing and change anything that is not yours.

Humanizing happens in four places:

- **While drafting:** each part of the plan is written next to two real paragraphs of yours that do the same job (`passages.section_anchors`). The writer sees your opening paragraphs for the hook, your closest body paragraphs for each section, and your closings for the ending.
- **In the editor's pass:** the critique sees the texture gaps and outlier sentences next to the scan's tells.
- **Humanize rounds** (`writer/humanize.py`, prompt `humanize.md`) run after the editor's pass and before references:
  1. Claude gets the flagged passages: detector outliers first, then twin giveaways, then texture and scan.
  2. Each comes with one of your real paragraphs, and Claude returns find/replace edits for those passages only.
  3. The post is checked again, and the edit is kept only if the score did not drop.
  4. Rounds are set in **Settings → Humanizing** (default 1, 0 to turn off).
- **The Humanize button:** on a flagged passage in the report, or *Humanize* in the highlight toolbar, it rewrites one passage next to your own paragraphs. If the rewrite reads less like you than the original (detector models, or the twin test), nothing changes and you are told so.

## The detectors

**Settings → Humanizing → AI detectors** is a list you can tick in any combination. The light check is selected by default and works on a fresh install. Selecting a trained model shows **Set up the trained models**, which downloads after a confirmation:

- **What it downloads, once:** PyTorch and the trained models you selected, up to about 1.3 GB for both. Models already downloaded are reused when you tick another.
- **Adding more models:** `local_detector.CATALOG` lists the detectors; a new one is a catalog entry (and, for a trained one, a worker kind in `detector_worker.py`).
- **How it runs:** in its own process through `uv run --no-project --with torch --with transformers`. The heavy packages live in uv's cache, never in the app's environment, so `uv sync` does not remove them. The models are stored under `data/detector/hf` and run on the CPU. Nothing is sent anywhere.
- **Where the trained models are not available:** the Windows installer build (no uv). The light check still runs.
- **Checking it:** `inferno-ghostwriter doctor` reports their status.

To check them on real text (your posts should land inside your own range, model-written text outside it):

```bash
cd backend
uv run python scripts/check_detector.py --setup --models light,curvature,classifier --human my_posts/*.md --ai drafts/*.md
```

Change the models with `INFERNO_GHOSTWRITER_DETECTOR_ZERO_SHOT_MODEL` and `INFERNO_GHOSTWRITER_DETECTOR_CLASSIFIER_MODEL`, using any Hugging Face causal language model and any `AutoModelForSequenceClassification` AI-text classifier. The AI label is found by name.

## The interview (optional)

Turn on **Interview me first** on *New post* (or as a persona default). Claude asks 3-5 questions about the post: your stories, opinions, numbers and mistakes. You answer any of them, or skip them all, and the post is written with your answers woven in close to your own words. The writer still fills everything else in your voice. With the interview off, writing works exactly as before. Answers can be edited, or new questions asked, in *Edit brief & settings*. See `writer/interview.py`.

## Settings

| Setting | Where | Default |
| --- | --- | --- |
| Humanize rounds | Settings → Humanizing (`INFERNO_GHOSTWRITER_HUMANIZE_ROUNDS`) | 1 |
| AI detectors (any mix of `light`, `curvature`, `classifier`) | Settings → Humanizing (`INFERNO_GHOSTWRITER_DETECTOR_MODELS`, a JSON list) | `["light"]` |
| Twin test / Claude judge | Settings → Advanced → AI-detection judge (`INFERNO_GHOSTWRITER_AI_DETECTION`) | on |
| Twin test pairs and effort | `INFERNO_GHOSTWRITER_TWIN_PAIRS`, `INFERNO_GHOSTWRITER_EFFORT_TWIN` | 4, `low` |

## Eval

`backend/evals/ai_detection.py` scores the persona's own posts and every post Inferno Ghostwriter generated for it. Each own post is held out of its own calibration, so it is compared with the others. The eval writes a Markdown and JSON report to `data/evals/`. It uses the detector models when they are set up.

```bash
cd backend
uv run python evals/ai_detection.py --persona "Your persona"               # scan, texture and detector models; no Claude calls
uv run python evals/ai_detection.py --persona "Your persona" --judge --yes  # adds the twin test
uv run python evals/ai_detection.py --demo --judge --yes                    # wiring check, no API calls
```

What to expect from the local models: they are small enough to run on a laptop. The classifier reliably catches generic, stock AI prose. Fast-DetectGPT on GPT-2 is weak against modern models' text, and posts that already pass the twin test usually pass both. Commercial detectors use much larger models and can still flag a post these pass, so the twin test and your own edits matter most.

No detector is perfect, and the ones here are not the one a publishing platform uses. They read the same machine texture, so treat the score as a strong second opinion, not a guarantee.
