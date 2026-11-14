# A/B Test Mode

Proseferno has two ways to write a post:

- **Generate & tweak** (the default): one post in your voice, then you refine it with feedback, section rewrites or new settings.
- **A/B test**: two complete posts from the same brief. One is written exactly as your persona is set up (the **control**). The other is written with almost everything nudged (the **challenger**). You read them side by side without knowing which is which, pick the one you like better, and only then find out. If the challenger's choices won, you can make them part of your persona.

An A/B test costs about twice as much as a normal post, because both posts are written and illustrated in full.

## Starting one

- On **New post**, choose **A/B test** under the brief and click **Write two versions**.
- On a post that is already written, use **A/B test** in the Revise card, or **A/B test these settings** in *Edit brief & settings*. The current post stays as it is until you pick a winner, and discarding the test leaves it untouched.
- A post with no text yet also offers **Write two versions (A/B test)**.

Both posts are written at the same time and shown in two columns as they stream in, labeled only **Post 1** and **Post 2**. Which one is the control is chosen at random for every test.

## What the challenger changes

The challenger is built in code (`abtest/perturb.py`), from a random seed, with no extra model call. Every change is small: a step, not a swing.

| Area | Change |
| --- | --- |
| Humor and the five style dials | Each moves by 1 or 2 on the 0-10 scale (turned around at the ends, so it always moves). |
| Education level | One step, one time in three. |
| Images, references | One more or one fewer image; one or two more or fewer references (none stays none). |
| Formula | Two of the opener, body and closer get another style that suits the article type, never a joke opener at humor 2 or below. |
| Example posts | One of the posts the writer is shown is swapped for another of your posts, and one of them is named as the one to lean on most. |
| Voice | Two habits from your voice profile to lean into and one to use more sparingly. |
| Writing principles | Two or three best practices weighed more heavily: from your research when the persona has it, otherwise from a built-in list (titles, story, skim readers, humor, insight, credibility, teaching). |
| Title | One title angle to favor (a question, a number, a bold claim, a how-to, a story hook, a contrast). |
| Images | One style twist added to the image style; palette, font and motif stay. |

What never changes: the brief, the **length**, the platform, the topic, the audience and the article type. Both posts answer the same request at the same length.

The voice, principle, title and example changes reach the writer as an "Emphasis for this post" block in the system prompt (`writer_system(..., emphasis=)`), after the voice profile; the profile's hard rules still win.

## Picking a winner

Nothing can be tweaked, rewritten or regenerated while the test is open. When you pick a post you can also take parts of the other one:

| Part | What happens |
| --- | --- |
| Title & subtitle | The other post's headline and the line under it. |
| Opener | Everything before its first `##` heading, with any image in it. |
| Closer | Its last section (before a *Go deeper* list and the meme), with any image in it. |
| Hero image, closing meme | The other post's image, as drawn. |
| Image style | The other post's look: your post's other images are redrawn in it. |

An optional note ("use the code example from Post 1 in the second section") runs as a normal *Tweak with feedback* that can see the other post. It is not kept as a lesson, because it is about one comparison.

The pick becomes your post: its text, images, references and settings. Both hidden posts are then deleted. The result is the post's new baseline, so persona evolution measures only what you change by hand afterwards.

## The reveal and adopting what won

After the choice, the post shows which version you picked. If you kept the challenger, or took parts of it, **Review the changes** lists every change the challenger made, with the ones in the post you kept already ticked. Adopt all of them, some of them, or **Keep my settings**:

- **Settings, formula parts and the image style** become the persona's defaults.
- **Example posts** are favored when the writer picks examples (`Sample.weight`, which multiplies topical similarity in `voice/exemplars.rank_own`).
- **Voice, principle and title** changes go through [persona evolution](evolution.md): a proposal of kind `ab_test` is applied right away and written into a new, unpinned voice profile version (`Evolved: <title>`), and later voice profile syntheses keep it.

If the control won and you took nothing from the challenger, there is nothing to adopt: your settings held up.

## How it works

| Piece | Where |
| --- | --- |
| The test | `ABTest` table: status (`generating`, `voting`, `deciding`, `decided`, `discarded`, `error`), seed, which role is Post 1, the tweaks, the emphasis block and examples, the winner, parts taken, what was adopted. |
| The two posts | Ordinary `Project` rows with `ab_test_id` and `variant` (`control` or `challenger`), hidden from the post list and Insights. Every pipeline step, image file and meme lookup works on them unchanged. |
| Writing | Job `ab_generate` on the host post runs `generate_article` for both at once; a `LaneReporter` re-sends each one's events as `lane` events (`left`/`right`, never roles), which `useJob` keeps in `JobState.lanes`. A failed post can be retried on its own. |
| Deciding | Job `ab_decide`: `abtest/blend.py` splices the parts (placeholders that come along get free `imgN` slots), image rows and files move to the host, the optional note runs `tweak_post`. |
| Adopting | `abtest/service.adopt`, then `evolution.service.start_apply` for voice changes. |
| API | `POST /api/projects` with `mode: "ab"`, `POST /api/projects/{id}/ab-tests`, `GET /api/ab-tests/{id}` (no roles, settings or scores until decided), `POST .../decide`, `.../adopt`, `.../retry`, `DELETE` to discard. |
| Frontend | `pages/project/ab/` (`ABGenerationView`, `ABCompare`, `ABReveal`), `lib/ab.ts`. |

`ab_generate` and `ab_decide` are text jobs, so only one runs per post. A test that was writing when the app restarted is marked as failed; an unfinished decision can be made again.

Tests: `backend/tests/unit/test_abtest.py`, `backend/tests/api/test_ab_tests.py`, `frontend/src/pages/project/ab/ABTest.test.tsx` and the end of `frontend/e2e/smoke.spec.ts`.
