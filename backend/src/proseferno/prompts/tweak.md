The author read the finished post below and left feedback. Apply the feedback as a small set of surgical edits, in the author's voice.

<feedback>
$feedback
</feedback>

Rules:
- Change only what the feedback asks for. Leave every other sentence, heading, code block and image placeholder exactly as it is: no polishing, tightening or re-voicing of text the feedback does not concern. A tweak is not a rewrite.
- Make the edit as large as the feedback needs and no larger. "Rewrite the intro" means replacing the intro; "fix this typo" means one word. Only make sweeping changes when the feedback directly asks for them.
- Each edit's `find` is text copied exactly from the post (including Markdown), long enough to appear only once: usually a whole sentence or paragraph. `replace` is the new text for that span. To insert something, `find` the sentence it should follow and `replace` it with that sentence plus the new text. To delete, `replace` with an empty string. Edits are applied in order and must not overlap.
- Keep every `{{image:...}}` line on its own line and do not add captions or credits next to them. If the feedback is about a specific image, add an `image_changes` entry with its `slot_id` and a new brief for what it should show; the image is redrawn and the others stay. Leave `image_changes` empty otherwise.
- Stay consistent with the post's settings: about $target_words words, audience $audience, humor $humor/10, education level $education, platform $platform.
- Keep facts and code correct. Avoid the AI-writing tells listed in the voice profile in anything you write.
- `summary` tells the author in one or two plain sentences what you changed.

Images in the post:
$images

<post>
$markdown
</post>
