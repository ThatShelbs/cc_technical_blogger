Work the researched references below into the finished post, in the author's voice. Each slot comes with web research; use it and nothing else. This is a light pass: change as little as you can, and keep the post's flow, structure and voice.

How to write each placement:
- inline: `find` is the slot's anchor, copied exactly from the post. `replace` is that same text with the reference worked in as a Markdown link, phrased the way the author would cite something ("as [the official docs](url) put it", "[one study](url) found"). Keep the sentence's meaning; a few added words are fine.
- blockquote: `find` is the anchor. `replace` is the anchor text unchanged, a blank line, then the quote or post as a blockquote with an attribution link, for example `> "Exact words." — [Name](url)` or `> Exact words. — [Name (@handle) on Bluesky](url)`. You may add a short lead-in of a few words to the anchor if the quote needs one.
- go_deeper: `find` is empty. `replace` is a single list line, `- [Title](url) — one line in the author's voice on why it is worth the reader's time`. The lines are gathered under `go_deeper_heading`, a short heading in the author's voice (e.g. "Go deeper").

Rules:
- Every reference links its URL, copied exactly from that slot's sources. Never invent, shorten or alter a URL, and never use a URL from another slot.
- Quotes and social posts use the exact words found in the research, attributed to the person who said them. Put those words in `quote` and the person in `speaker`. Never paraphrase a quote or invent one.
- Only claim what the source supports. If a slot's research does not give you something real that fits, return its edit with an empty `replace`.
- Do not add "Source:" or "Credit:" lines, footnotes, TODOs, or anything next to an `{{image:...}}` placeholder. Leave every other sentence, heading, code block and placeholder exactly as it is.
- Platform ($platform): $platform_guide

<slots>
$slots
</slots>

<post>
$markdown
</post>
