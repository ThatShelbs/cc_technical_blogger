Plan a new post from the author's brief.

<brief>
$prompt
</brief>

Settings:
- Topic area: $topic
- Target length: about $target_words words
- Humor level $humor/10: $humor_guide
- Education level ($education): $education_guide
- Code snippets / LLM prompts: $include_code
- Publishing platform: $platform
- Images: exactly $image_count image slots

Image slot rules:
- The first slot is the hero (`slot_id` "hero", kind "hero", `section_index` -1): it is also the thumbnail.
- The last slot is the closing meme (`slot_id` "meme", kind "meme", placed in the last section): a funny, relevant joke that lands the ending.
- Every other slot must add real value for the reader: a clarifying diagram, an illustrative chart, a conceptual illustration, a humorous moment, or a screenshot placeholder when a real platform screenshot (UI, console, settings page) would help. Spread them through the post where they serve the text. Give them ids "img2", "img3", and so on.

Title options must follow the author's title formulas from the voice soul. Choose the strongest as `chosen_title`.
