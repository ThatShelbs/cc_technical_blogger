Write the full post from this plan, in the author's voice.

<brief>
$prompt
</brief>

<plan>
$plan
</plan>

Settings:
- About $target_words words (excluding code)
- Humor level $humor/10: $humor_guide
- Education level ($education): $education_guide
- Code snippets / LLM prompts: $include_code
- Publishing platform ($platform): $platform_guide

Style dials (5 = the author's natural level; adjust emphasis within the author's voice, never abandon it):
$style_guide

Sound human, because the author is human: vary sentence length and paragraph shape the way the author does, use their real verbal habits, and avoid the generic AI-writing tells listed in the voice soul (stock vocabulary like "delve", "tapestry" or "game-changer", "it's not X, it's Y" constructions, reflexive rule-of-three lists, "Moreover/Furthermore" transitions, em dashes beyond the author's measured rate, and tidy upbeat summaries).

Format (Markdown):
- First line `# <title>`, then the subtitle in italics on its own line.
- Section headings with `##` (and `###` only if the author uses subsections).
- Code and LLM prompts in fenced blocks with a language tag.
- Put each image placeholder on its own line exactly where the image belongs: $placeholders. The hero goes right after the subtitle. The meme goes at the very end of the post, after the final line of text.
- Each placeholder line stands alone. Do not write captions, credits, photo or data sources, or italic caption lines before or after it (no "Photo by ...", "Image: ...", "Visualization: ...", "Source: ..."); every image gets its own caption and credit automatically.

Return only the post.
