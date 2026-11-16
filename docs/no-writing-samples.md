# A voice without writing samples

Not everyone has posts to learn from. Inferno Ghostwriter treats that as a normal way to start, not a workaround. In the setup guide's **Your voice** step (and at the top of a persona's **Samples** tab while it has no posts of its own), choose **I'm starting fresh** and pick one of four ways to get a voice:

| Path | What you do | What it builds from | Model call |
| --- | --- | --- | --- |
| **Pick a voice** | Choose one of 12 ready-made voices (the Skeptical Practitioner, the Friendly Explainer, the Dry-Wit Staff Engineer...). Optionally add a note. | The archetype's brief, example line and dials. | none for the choice |
| **Inspired by writers** | Name 1-4 public writers or blogs and say how much of each. | A web search that reads their public work and extracts abstract style traits. | one research call (kept until you change the writers) |
| **Answer a few questions** | Answer any of 7 short questions (audience, how you would explain something out loud, what annoys you...). | Your own words, which are the best clue to your voice. | none for the choice |
| **Surprise me** | Shuffle a random voice with a second one folded in. | Two archetypes and nudged dials. | none for the choice |

Then generate the voice profile as usual. The voice profile job synthesizes it from the choice (and from any influence posts you added).

## What changes without your own posts

- The voice profile's **Voice Anchors** and examples are *illustrative lines written for the profile*, not quotes from you, and it says so. There is no measured style baseline, so structure targets are ranges.
- The AI-detection report skips the twin test (it needs your paragraphs), Insights stay empty until you have posts, and fidelity shows no score. Writing, images, references, formulas and A/B tests all work.
- The persona's default dials start from the archetype (Pick a voice, Surprise me).

## It grows into you

Nothing is a dead end. Add your own posts any time (upload, URL or **paste text**) and regenerate: the persona's own writing then decides identity, and the chosen voice stays as a starting hint. Edits you make to generated posts and published results also teach it (see [Evolution](evolution.md)).

## Real writers: style traits only

The blend path never copies. The research prompt asks for habits (rhythm, structure, humor devices, point of view), forbids reproducing passages or writing "in the voice of" a person, skips names it cannot find public evidence for, and labels the result *inspired by*. The sources it read are saved with the voice profile version.

## For developers

- `Persona.source` (`samples` default, `archetype`, `random`, `blend`, `interview`) and `Persona.source_spec` (JSON) hold the choice; `voice/sources.py` validates it (`clean_spec`), applies dials (`apply_source`) and builds the persona brief (`build_brief`). Archetypes live in `sample_content/archetypes.json`; interview questions in `INTERVIEW_QUESTIONS`.
- `voice/pipeline.py` accepts a persona with no own samples when it has a source, passes `$persona_brief` and `$mode_note` to `prompts/voice_synthesize.md`, and stores a blend's research on the persona so it is not repeated.
- API: `GET /api/archetypes`, `GET /api/voice-interview`, `GET /api/voice-surprise?seed=`, `PUT`/`DELETE /api/personas/{id}/voice-source`, `POST /api/personas/{id}/samples/text`.
- Frontend: `components/VoiceStart.tsx` (fork and the four builders), `lib/onboarding.ts` (shared setup steps, used by the welcome guide and the Posts checklist).
- Add an archetype by adding an entry to `archetypes.json` (id, name, tagline, brief, preview, six dials); tests check the shape.
