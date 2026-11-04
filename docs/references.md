# References

Every post includes real references that back it up and give the reader something to explore next. By default there are at least five, chosen from five kinds:

| Kind | What it is | Where it goes |
| --- | --- | --- |
| **Source** | Evidence for a claim or key concept: a paper, official docs, a well-known report, book or benchmark | A link worked into the sentence it supports |
| **Quote** | A famous quote, preferably from someone known in statistics, causal inference, AI/ML research or tech, credited to who said it | A blockquote after the paragraph it sharpens, or inline |
| **Social post** | A widely shared post on X, Bluesky, Threads, LinkedIn or Mastodon from an AI/ML voice | A blockquote with the author, handle and a link to the post |
| **Resource** | A tutorial, Python package or YouTube video | Inline if the post mentions it, otherwise the short *Go deeper* list before the closing meme |
| **Related article** | A closely related article or post | Same as a resource |

The default count is `max(5, 5 + (words − 2,000) / 500)`, capped at 12: five for a typical post, seven for 3,000 words. Change it, or pick which kinds may be used, per post (New post → Customize, or **Edit brief & settings**) or per persona (Personas → Settings & defaults). Set it to 0 for no references.

## How they are added

References are a later pass, like the images, so they never get in the way of the voice edit. After the draft is critiqued and revised, `writer/references.py`:

1. **Plans** where references would strengthen the finished post (`prompts/reference_plan.md`, structured output `ReferencePlan`). Each slot has a kind, a placement, an *anchor* sentence copied from the post, and a search query. Code keeps only slots that can really be placed: allowed kinds, at most two of a kind (more only when the count requires it), one per paragraph, never in the title, a heading, a code block or an image placeholder, and at most three *Go deeper* items.
2. **Researches** each slot with web search (`llm.research`, `prompts/reference_research.md`), three at a time, up to `reference_max_searches` searches each. URLs already tried are excluded. With `check_reference_links` on, every URL is fetched once: a 404, 410 or a host that does not resolve counts as dead, and the slot searches again once without it. Sites that block bots (403, 429, timeouts) are kept.
3. **Weaves** them in with one structured call (`prompts/reference_weave.md`, `ReferenceEdits`) that returns a small find/replace edit per slot, written in the author's voice with the same cached system prompt as the rest of the post.
4. **Checks** every edit in code before applying it (`check_edit`):
   - every new link must be one of that slot's search citations;
   - a quote (or the words of a social post) must appear in the research, ignoring case, curly quotes and spacing, and the post must quote the same words;
   - the edit must not rewrite much more than its anchor.

   An edit that fails stays out of the post, and that one reference shows an error with **Redraw**. Nothing is invented, and a failed reference never fails the post.

Then the AI-detection report and the images run on the final text.

**Virality cannot be verified.** The prompt asks for widely shared posts by recognized voices, and the checks prove the post exists and the words are real, but a search cannot prove how far a post spread.

## The post stays plain Markdown

References are ordinary links, blockquotes and a list, so exports, word counts and the section toolbar need nothing special. Each one is a `ProjectReference` row (`db/models.py`) that remembers:

- `original`: the text it replaced;
- `inserted`: the exact text it put in the post;
- `tried_urls`: links already tried;
- `history`: every version, oldest first.

The API reports `in_post: false` when the author has edited a reference's text away; the card shows "Edited out".

## Redraw, versions, remove

In the editor, every reference link has a small chip; click it for **Redraw**, **Switch to…** another kind, and **Remove**. The **References** card in the sidebar lists them all with the same actions plus **Versions**, **Show in post**, and **Find references / Add another**.

| Action | Route | Notes |
| --- | --- | --- |
| Redraw (optionally as another kind) | `POST /api/references/{id}/redraw` `{kind?}` | Job `redraw_reference`. Searches again without the tried URLs, writes the new reference into the same spot, adds a version and an undo entry. |
| Swap a version back | `POST /api/references/{id}/revert` `{index}` | |
| Remove | `DELETE /api/references/{id}` | The sentence goes back to how it read; an empty *Go deeper* list loses its heading. |
| Add references to an existing post | `POST /api/projects/{id}/references` `{count?, kinds?}` | Job `enrich_post`; for older posts or posts written with references off. |

Both jobs are text jobs (`TEXT_JOBS`), so they never run alongside a tweak or another rewrite. *Undo last change* reverses any of them. A full regeneration replaces all references.

*Add source* and *Add quote* from the section toolbar use the same checks, and what they add appears in the References card with **Redraw** too.

## Settings

| Setting | Default | Where |
| --- | --- | --- |
| References per post | automatic (at least 5) | Per post or persona; `reference_count` dial, `Persona.default_reference_count` (null = automatic, 0 = none) |
| Kinds allowed | all five | Per post; `reference_kinds` dial |
| `PROSEFERNO_EFFORT_REFERENCES` | `medium` | Effort for planning, research and weaving |
| `PROSEFERNO_REFERENCE_MAX_SEARCHES` | `3` | Web searches per reference |
| `PROSEFERNO_CHECK_REFERENCE_LINKS` | `true` | Fetch each URL once and drop dead ones |

Tests and demo mode never go online: they use `NoLinkChecker`, and `demo.FakeLLM` returns example.com links and canned quotes.
