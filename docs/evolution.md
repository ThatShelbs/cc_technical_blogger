# Persona evolution

A persona should get better with every post you publish. Proseferno learns from two things:

1. **What you changed before publishing.** When you mark a post **Published**, the text you shipped is compared with the text Proseferno generated. Your edits become a few small proposed changes to the persona, so the next post needs fewer edits.
2. **What worked.** When you rate a published post **Good traction** or **Viral**, Claude works out its *secret sauce*: the moves readers probably responded to. These go into the persona's **playbook**, so it keeps writing posts like it.

Nothing changes until you review a proposal and apply it.

## Stages and outcomes

Every post has a **stage**, set in the post's header:

| Stage | Meaning |
| --- | --- |
| Draft | Still being written or edited (the default). |
| Ready | Done, waiting to go out. |
| Published | Out in the world. Publishing starts the edit analysis. |

A published post also has an **outcome**:

| Outcome | What happens |
| --- | --- |
| Too early | The default when you publish. No verdict yet. |
| Small traction | Recorded only. |
| Good traction | Starts a secret-sauce analysis. |
| Viral | Starts a secret-sauce analysis. If the post was already rated Good traction and its proposal was not applied yet, the post is read again as a hit. |

Choosing an outcome publishes the post. Moving it back to Draft or Ready clears the outcome. The Posts page shows each post's stage and outcome and filters by stage.

These are separate from the generation `status` (`new`, `generating`, `ready`, `error`), which only says whether Claude is still writing the post.

## The baseline

Each full generation records the finished text, after critique, revision and references, as the post's **baseline** (`Project.baseline_markdown`, `baseline_title`). Every later change counts as an edit: manual saves, *Tweak with feedback*, section rewrites, humanize, reference redraws. *Regenerate post* resets the baseline, so the comparison is always against the version you kept.

The **Teach the persona** card on the post shows how much of the generated text you changed (the **edit rate**: `1 - SequenceMatcher(words).ratio()`, ignoring image placeholders). **Compare** opens a word-by-word view, with cuts struck through and additions highlighted (`GET /api/projects/{id}/baseline-diff`). Posts generated before this feature have no baseline. The card says so, and only the secret-sauce analysis is available for them.

## From your edits

Publishing starts the `evolve_post` job (`evolution/service.py`):

1. If you changed less than 2% of the text, the persona already writes this kind of post the way you want. The proposal is recorded as *Nothing to change*, with its edit rate and no Claude call.
2. Otherwise one structured call (`EvolutionPlan`, `prompts/evolve_edits.md`) runs. Claude gets:
   - the voice profile
   - the changed paragraphs, generated then published (`diff_digest`)
   - the small edit lessons already fed to the writer
   - the playbook
   - the changes you approved before
3. Claude proposes up to six changes. Each is one imperative sentence with its evidence. Its target is either **Voice profile** (how you always write) or **Playbook** (a move to use where it fits).

`prompts/evolve_system.md` tells Claude to propose taste and craft changes only. Fixed facts, added news and changed arguments are content, and are ignored. Publishing the same text again does not run a second analysis. *Analyze again* runs it on the current text, for example after more edits.

This complements [learning from your edits](voice-pipeline.md#learning-from-your-edits). Those lessons are word-level habits picked up on every save. Evolution looks at the whole post once it is final.

## Secret sauce

A Good traction or Viral rating starts a secret-sauce analysis (`SecretSauce`, `prompts/secret_sauce.md`). Claude gets:

- the final post
- its outcome
- the formula it followed (`ResolvedDials.formula_guide`)
- the voice profile
- the playbook

It returns three to six moves that other posts on other topics can reuse. Most of them go to the playbook.

## Reviewing and applying

**Review** opens a checklist with every change ticked. Untick any you disagree with, then **Apply** (the `apply_evolution` job):

- **Playbook** changes are added to `Persona.playbook`, which holds at most 20 entries, sorted by outcome (viral first) and newest first.
- **Voice profile** changes take one structured call (`ProfileEdits`, `prompts/evolve_apply.md`). It returns small find/replace edits to the voice profile in use, applied with `writer.tweak.apply_edits`. Any change Claude could not place is added as a bullet under **Do / Don't**. That section is created before the Voice Anchors if the profile lacks one. The result is saved as a new voice profile version labeled `Evolved: <post title>` and becomes the one in use. To roll back, pin the previous version.

**Dismiss all** drops a proposal. A failed or interrupted analysis is shown as failed and can be run again. Analyses still running when the app stops are marked failed at the next start.

## Where the learning goes

- **Every writer call** gets the top ten playbook entries as a system block: *What has landed with this author's readers*. These calls are plan, draft, critique, revise, titles, tweaks, section rewrites, references and the LinkedIn post (`writer_system(..., playbook=...)`).
- **The next voice profile** generated from samples sees the approved profile changes (`$approved_changes`) and the playbook (`$playbook`) in `prompts/voice_synthesize.md`. Regenerating the profile does not undo what the persona learned.
- **Personas → Evolution** shows:
  - proposals waiting for review
  - the playbook, where you can forget one entry or all of them
  - the edit-rate trend across published posts, which should fall as the persona learns
  - the history of every proposal

## API

| Route | Purpose |
| --- | --- |
| `PATCH /api/projects/{id}` with `stage` / `outcome` | Move a post; starts any analysis now due. |
| `GET /api/projects/{id}/baseline-diff` | Edit rate and word-level segments. |
| `POST /api/projects/{id}/evolutions` `{kind}` | Analyze again (`edits` or `secret_sauce`). |
| `GET /api/personas/{id}/evolution` | Proposals, edit-rate trend and playbook. |
| `POST /api/evolutions/{id}/apply` `{item_ids}` | Apply the chosen changes (returns a job). |
| `POST /api/evolutions/{id}/dismiss` | Dismiss a proposal. |
| `DELETE /api/personas/{id}/playbook?index=` | Forget one playbook entry, or all without `index`. |

`ProjectOut` carries `stage`, `outcome`, `published_at`, `has_baseline`, `edit_rate` and the post's `evolutions`. `PersonaOut` carries `playbook` and `pending_evolutions`. The effort for every evolution call is `PROSEFERNO_EFFORT_EVOLVE` (default `medium`).

## Code map

| File | What it does |
| --- | --- |
| `evolution/diff.py` | Edit rate, compare segments, the prompt digest. |
| `evolution/service.py` | Stage changes, analyses, apply, dismiss, startup clean-up. |
| `evolution/schemas.py` | `EvolutionPlan`, `SecretSauce`, `ProfileEdits`. |
| `voice/playbook.py` | Add, forget and format playbook entries; approved changes for synthesis. It sits in `voice/` so `writer` can import it without a cycle. |
| `db/models.py` | `PersonaEvolution`; `Project.stage`, `outcome`, `published_at`, `baseline_*`; `Persona.playbook`. |
| `api/evolution.py` | The routes above. |
| `frontend/src/pages/project/StageControl.tsx`, `EvolutionCard.tsx` | Stage and outcome controls, *Teach the persona* card, compare view. |
| `frontend/src/components/EvolutionDialog.tsx`, `EvolutionPanel.tsx` | Review dialog; the persona's Evolution tab. |

Tests: `backend/tests/unit/test_evolution.py`, `backend/tests/api/test_evolution.py`, `StageControl.test.tsx`, `EvolutionDialog.test.tsx`, and the publish step of `frontend/e2e/smoke.spec.ts`.
