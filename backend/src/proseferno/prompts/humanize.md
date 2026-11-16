A detector pass found the parts of this post that read as machine-written. Some were flagged by AI-text detector models, some by a blind test where an editor could tell them apart from the author's real writing (the `why` says what gave them away), and some by a texture check against the author's posts. Under most targets is a real paragraph by the author to write next to.

Rewrite only those parts so they read like the author wrote them on a good day:
- Make them specific and lived-in: a concrete moment, a number, a named tool, the mistake, a line of dialogue, a small opinion with an edge. Invent these the way the author would; prefer showing to explaining.
- Use the author's rhythm from their paragraph: how long their sentences run, how they start them, where they break a thought, their asides. Break up runs of same-length sentences.
- Fix the giveaway named in `why`. Cut stock phrasing, tidy summaries and hedging.
- Keep the meaning and every technical fact, and keep the flow with the text around each edit.
- Never touch code blocks, `{{image:...}}` lines, headings, links or quoted words from sources.

<targets>
$targets
</targets>

<post>
$post
</post>

Return `edits`: each `find` copies the exact text from the post (a whole sentence or paragraph, long enough to appear only once) and `replace` is the rewritten version. Rewrite every target unless it already reads like the author. `image_changes` is empty. `summary` says in a sentence what you changed.
