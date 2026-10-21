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

Format (Markdown):
- First line `# <title>`, then the subtitle in italics on its own line.
- Section headings with `##` (and `###` only if the author uses subsections).
- Code and LLM prompts in fenced blocks with a language tag.
- Put each image placeholder on its own line exactly where the image belongs: $placeholders. The hero goes right after the subtitle. The meme goes at the very end of the post, after the final line of text.
- Do not write image captions; they are added separately.

Return only the post.
