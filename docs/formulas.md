# Formulas

A **formula** is the shape of a post, chosen part by part:

1. **Article type**: what the reader is promised (a tutorial, a comparison, an opinion piece...).
2. **Opener**: how the first lines earn the second paragraph.
3. **Body**: how the middle is organized.
4. **Closer**: the last lines of text.

The closing meme is not part of the formula. Every post still ends with it, after the closer. The meme does know the formula, though: see [The closing meme](#the-closing-meme).

A formula decides structure only. The voice profile still decides how every sentence sounds, so a "Joke: the confession" opener is a confession in *your* kind of humor. Every part defaults to **automatic**: the post is shaped the way your voice profile says you write, exactly as before formulas existed. You only set the parts you care about.

## The smart default

You do not have to choose anything. With the article type on **Automatic**, Proseferno reads it from your brief: "How to size an A/B test" is a how-to, "X vs. Y" a comparison, "Top 7 ..." a countdown, "What I learned ..." a lessons-learned post. The form shows the guess while you type (*Automatic: How-to*), and the finished post lists it under **Settings used** as read from your brief.

- A signal in the first line of the brief (the working title) is enough. Words further down only count when three of them agree, so one stray bullet never decides the shape of a post.
- When the brief does not say, nothing is assumed and the post takes the shape you usually give one.
- The opener, body and closer stay with your voice profile until you choose or shuffle them.
- A type you choose yourself, on the post or as the persona's default, is never second-guessed.

The rule is `detect_article_type` in `writer/formulas.py` (each article type lists its `signals`), mirrored by `detectArticleType` in `frontend/src/lib/formula.ts` for the live hint.

## Shuffle

- **Shuffle the formula** draws a new opener, body and closer from the styles that suit the article type in force (chosen, or read from the brief). Click again for another draw; every click changes each part that has an alternative.
- The **dice** next to a part redraws only that part.
- With no article type, a shuffle draws the opener and closer from the whole catalog and leaves the body alone, because a body structure only makes sense for the kind of post it was made for.
- At humor 0-2 a shuffle never lands on a joke opener (you can still pick one yourself). Your own instructions are kept.
- On a written post, **Try another formula** (under *Settings used*) opens **Edit brief & settings**: shuffle or change the formula there, then *Regenerate with these settings*. You see the new formula before the current text is replaced.

## Using formulas

- **Per post:** New post → **Formula** (or **Edit brief & settings** on a written post, which regenerates it). Pick an article type, then open *Build the formula* to choose the opener, body and closer. Each menu lists the styles that suit the article type first, best first, then every other style by family. *Use the classic ... formula* fills all three parts with the type's usual choices, which you can then swap one at a time.
- **Your own instructions:** every part has a free-text line. Use it on top of a style ("Cold open" + "start at 3 a.m. with the pager") or instead of one, to describe an opener, body or closer that is not in the catalog.
- **Saved formulas:** *Save as a formula* stores the current combination under a name. Saved formulas are shared by all personas and appear in the *Saved formula* menu; saving again under the same name replaces it.
- **Persona default:** Personas → (persona) → Settings & defaults → **Default formula**. New posts start from it. On a post, setting a part back to automatic switches the persona's default off for that post only.
- The post page shows the formula under **Settings used**.

## The catalog

### Article types

| Article type | The promise to the reader | Classic formula (opener → body → closer) |
| --- | --- | --- |
| **Deep narrative** (`deep_narrative`) | A long-form story that carries the technical ideas inside it. | Cold open → Narrative arc → Full circle |
| **Top N countdown** (`listicle`) | A numbered list of the best, worst or most useful things. | Bold promise → Countdown → Key takeaways |
| **How-to** (`how_to`) | Get one specific task done, for a reader who has the task now. | Name the problem → Step by step → One next step |
| **Tutorial** (`tutorial`) | Teach a skill by having the reader build something end to end. | Show the result first → Start simple, build up → A challenge |
| **X vs. Y comparison** (`comparison`) | Two or more options weighed fairly, ending in a recommendation. | Name the problem → Criterion by criterion → The verdict |
| **Explainer / What is X** (`explainer`) | Make one concept clear: what it is, why it matters, how it works. | Open question → Concept ladder → Key takeaways |
| **Case study / build walkthrough** (`case_study`) | How a real project was built or a real problem solved, with results. | Cold open → Build log → Key takeaways |
| **Hands-on / I tried it** (`hands_on`) | You tested something yourself and report what really happened. | Open question → Experiment report → The verdict |
| **Lessons learned** (`lessons_learned`) | A retrospective: what went wrong or right, and what you took from it. | Joke: the confession → Lessons, one by one → Personal reflection |
| **Opinion / thought leadership** (`opinion`) | Take a position on where the field is or should be going. | Controversial idea → Build the argument → One-line kicker |
| **Tool review / tool update** (`tool_review`) | An honest look at a tool or release: what is new, what works, who should care. | What just changed → Review → The verdict |

### Openers

Five joke openers (each a different comic mechanism), three story openers, four bold ones and four serious ones.

| Family | Style | What it does |
| --- | --- | --- |
| Joke | **Joke: the confession** (`joke_confession`) | Admit your own mistake or bad habit first. |
| Joke | **Joke: the absurd analogy** (`joke_absurd_analogy`) | Explain the topic with a comparison that has no business working. |
| Joke | **Joke: the misdirection** (`joke_misdirection`) | Set up one expectation, then swerve. |
| Joke | **Joke: the exaggeration** (`joke_exaggeration`) | Blow a shared pain up until it is funny. |
| Joke | **Joke: the mock-serious** (`joke_mock_serious`) | Treat something small with far too much gravity. |
| Story | **Personal anecdote** (`anecdote`) | A short true story from your own work. |
| Story | **Cold open** (`cold_open`) | Drop the reader into the middle of the moment. |
| Story | **Show the result first** (`result_first`) | Lead with the finished thing, then explain how. |
| Bold | **Controversial idea** (`contrarian`) | State the unpopular opinion plainly, first line. |
| Bold | **Bust a myth** (`myth_buster`) | Name what everyone believes, then crack it. |
| Bold | **Surprising number** (`surprising_number`) | One figure or result the reader did not expect. |
| Bold | **Bold promise** (`bold_promise`) | Say exactly what the reader can do by the end. |
| Serious | **Straight to the point** (`direct`) | Answer first; no warm-up. |
| Serious | **Name the problem** (`problem_first`) | Start with the reader's pain, precisely described. |
| Serious | **Open question** (`question`) | Ask the one question the post exists to answer. |
| Serious | **What just changed** (`news_peg`) | Start from the release, the update or the news. |

A joke opener is used even when the humor dial is low; the dial still governs the rest of the post.

### Bodies

| Family | Style | What it does |
| --- | --- | --- |
| Story | **Narrative arc** (`narrative_arc`) | Setup, rising trouble, turning point, resolution. |
| Story | **Build log** (`chronological`) | What happened, in the order it happened. |
| Story | **Lessons, one by one** (`lessons_list`) | Each lesson: what happened, what it taught, what to do instead. |
| List | **Countdown** (`countdown`) | Numbered items from good to best; the top pick comes last. |
| List | **Ranked, best first** (`best_first`) | Numbered items with the most useful one at the top. |
| List | **Grouped by theme** (`themed_groups`) | Items sorted into a few named groups. |
| List | **Myth vs. reality** (`myth_reality`) | Each section states a common belief, then what is true. |
| Teach | **Step by step** (`step_by_step`) | Numbered steps: do this, see that. |
| Teach | **Start simple, build up** (`progressive_build`) | The smallest working version first, one addition per section. |
| Teach | **Concept ladder** (`concept_ladder`) | What it is, why it matters, how it works, an example, the traps. |
| Teach | **Question by question** (`question_led`) | Each section answers the next thing the reader would ask. |
| Teach | **Problem, then solution** (`problem_solution`) | The problem, why the obvious fixes fail, the fix, the proof. |
| Weigh | **Criterion by criterion** (`criteria_by_criteria`) | Compare on one criterion per section, with a winner each time. |
| Weigh | **Option by option** (`option_by_option`) | Each option in turn, then the head-to-head. |
| Weigh | **Experiment report** (`experiment`) | The question, the setup, what happened, what surprised you. |
| Weigh | **Review** (`verdict_review`) | What it is, what is new, the good, the bad, who it is for. |
| Argue | **Build the argument** (`argument`) | Thesis, evidence, the best objection, your answer to it. |
| Argue | **Most important first** (`inverted_pyramid`) | The key facts up top, detail in descending order. |

### Closers

| Family | Style | What it does |
| --- | --- | --- |
| Land it | **Full circle** (`full_circle`) | Return to the opening, changed by what the post showed. |
| Land it | **One-line kicker** (`kicker`) | Stop on a single short line that sticks. |
| Land it | **Personal reflection** (`reflection`) | What this changed for you. |
| Hand it over | **Key takeaways** (`takeaways`) | A short recap the skimmer can keep. |
| Hand it over | **One next step** (`next_step`) | A single concrete thing to do today. |
| Hand it over | **A challenge** (`challenge`) | Dare the reader to try it and see. |
| Hand it over | **The verdict** (`verdict`) | A plain recommendation: use this if, that if. |
| Open it up | **Question for readers** (`open_question`) | Ask one real question and invite answers. |
| Open it up | **Zoom out** (`zoom_out`) | Step back to what this means beyond the post. |
| Open it up | **A prediction** (`prediction`) | Make a bet about where this goes next. |
| Open it up | **The honest caveat** (`honest_caveat`) | Say what you still do not know. |
| Open it up | **What comes next** (`teaser`) | Point to the follow-up post. |

## How a formula reaches the post

`writer/formulas.py` holds the catalog and the resolution rules. `resolve()` in `writer/dials.py` merges the post's dials with `Persona.default_formula` (the post wins; an explicit `auto` or an empty note on the post overrides the persona) and produces `ResolvedDials.formula_guide`, a block of instructions with the guide text of each chosen style and the author's notes. That block is the `$formula_guide` placeholder in three prompts:

- `prompts/plan.md`: the planner writes `hook` to the opener, shapes `sections` to the body and writes `closing` to the closer.
- `prompts/draft.md`: the writer follows it in the author's own words.
- `prompts/critique.md`: the editor checks the draft against it and counts misses in the `structure` score, so the revision fixes them.

With no formula the block is one line telling Claude to use the author's usual shape. Where a formula and the platform notes disagree about the opening or ending (LinkedIn's "end with a question", for example), the formula wins. Styles that involve facts (a surprising number, an experiment, a review) tell Claude to use only what the brief provides or the post demonstrates, never to invent figures.

### The closing meme

The meme's writers' room (`prompts/meme_ideas.md`, see [images](images.md#closing-memes)) is told the formula the writer followed: the article type, the opener, the body and the closer, with your own instructions (`meme_note` in `writer/formulas.py`, resolved the same way as for the text, including an article type read from the brief). Three rules come with it:

- The meme is a new beat after the closer. It never restates the closer's last line, its takeaways or its verdict.
- A post that opens on a joke should get at least one pitch that brings that joke back, changed by what the post showed.
- With a **Full circle** closer the text already returns to the opening, so the meme lands somewhere else.

With no formula in force the room is told nothing extra. The other images need no such note: their briefs are written by the planner, which plans to the formula (a *Show the result first* opener can put the result in the opening image, an *Experiment report* body asks for charts of the results).

### The opening image

The article type and the opener also decide which [opening image styles](opening-images.md) suit the post: a how-to suggests a cheat sheet or framework diagram, a comparison a versus split or data chart, a *Surprising number* or *Show the result first* opener a big number or data chart, a joke opener an opening meme. On Auto the panel pitches across those styles plus open visual metaphors and data art, and the room is told the formula. The opening image is not part of the formula; choose it next to the formula on the new-post form.

Stored values are catalog ids. An id that is no longer in the catalog resolves to automatic, so removing a style never breaks an old post.

| Where | What |
| --- | --- |
| `Project.dials` | `article_type`, `opener`, `body`, `closer`, `opener_note`, `body_note`, `closer_note` (only what was set) |
| `Persona.default_formula` | the same keys, as the persona's default |
| `Formula` table | saved formulas: a name plus the same fields |
| `GET /api/formulas/catalog` | the catalog (the frontend reads every label and description from here) |
| `GET/POST /api/formulas`, `PUT/DELETE /api/formulas/{id}` | saved formulas |

## Adding a style

1. Add a row to `OPENERS`, `BODIES` or `CLOSERS` in `writer/formulas.py`: an id, a label, a one-line summary for the menu and a `guide` for Claude. Write the guide as concrete moves ("state the belief, let it stand for a line, then show the crack"), say what to avoid, and never name third-party products.
2. List its id under every article type it suits (`tests/unit/test_formulas.py` fails if a style suits none). The first id in each list is the type's classic choice.
3. Run `uv run pytest tests/unit/test_formulas.py tests/api/test_formulas.py`. No frontend change is needed.
4. Update the tables in this file.

A new article type is one `ArticleType` entry with its suggested openers, bodies and closers, and the `signals` that give it away in a brief. Signals are case-insensitive regular expressions that must be valid in both Python and JavaScript; add the brief you had in mind to `BRIEFS` in `tests/unit/test_formulas.py`.

Because voice quality is the product, check a new or changed guide on real writing: generate the same brief with and without the formula and compare the editor's voice score, or run `evals/voice_fidelity.py` (see [voice-pipeline.md](voice-pipeline.md)).

## Where the catalog comes from

The styles are drawn from common practice in content strategy, journalism, documentation and humor writing, adapted to technical posts:

- **Article types:** the usual blog archetypes ([Animalz](https://www.animalz.co/blog/types-of-blog-posts)), the engineering-blog patterns in [*Writing for Developers*](https://www.manning.com/books/writing-for-developers) (the bug hunt, "how we built it", thoughts on trends), and the [Diátaxis](https://diataxis.fr/) distinction between a tutorial (learning by doing) and a how-to guide (getting a task done).
- **Openers:** journalism's lede types (summary, anecdotal, scene-setting, question, delayed; see [MasterClass on ledes](https://www.masterclass.com/articles/how-to-write-a-lede-in-journalism)) and copywriting hooks ([Copyblogger](https://copyblogger.com/hook-and-idea/)). The joke openers are separate comic mechanisms: self-deprecation, incongruous analogy, misdirection, exaggeration and mock-seriousness ([Writer's Digest](https://writersdigest.com/write-better-fiction/how-to-mix-humor-into-your-writing)).
- **Bodies:** narrative and inverted-pyramid story structures ([story structures in journalism](https://courses.rodrigozamith.com/intro-to-journalism/creating-news-content/story-structures/)), problem-agitate-solve from copywriting, and the point-by-point and block patterns of comparison writing.
- **Closers:** circular endings, zooming out and ending on a line rather than a recap ([Pomona College on conclusions](https://www.pomona.edu/node/4608)), and the blog conventions of one next step or one question ([MasterClass](https://www.masterclass.com/articles/how-to-end-a-blog-post)).

The backend mirrors the shuffle in `formulas.shuffle_part` (same rules as `shufflePart` in `frontend/src/lib/formula.ts`; change both together). An [A/B test](ab-testing.md) uses it to give its challenger two new formula parts.
