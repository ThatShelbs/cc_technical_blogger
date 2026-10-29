Plan a new post from the author's brief.

<brief>
$prompt
</brief>

Settings:
- Topic area: $topic
- Audience: $audience
- Target length: about $target_words words
- Humor level $humor/10: $humor_guide
- Education level ($education): $education_guide
- Code snippets / LLM prompts: $include_code
- Publishing platform ($platform): $platform_guide
- Images: exactly $image_count image slots

Style dials (5 = the author's natural level; adjust emphasis within the author's voice, never abandon it):
$style_guide

Image slot rules (every image is drawn by Claude as SVG or a Vega-Lite chart, so plan images that vector art can do brilliantly):
- The first slot is the hero (`slot_id` "hero", kind "hero", `section_index` -1): it is also the thumbnail.
- The last slot is the closing meme (`slot_id` "meme", kind "meme", placed in the last section): a funny, relevant joke that lands the ending.
- Every other slot must add real value for the reader. Choose the kind that serves the text best:
  - "diagram" for workflows, architectures, pipelines, comparisons, decision trees and concept maps;
  - "chart" for anything quantitative (a data visualization with realistic or real numbers);
  - "illustration" for a conceptual editorial image or visual metaphor that sets up a section;
  - "icon" for a set of 2-4 concept icons that anchors a list of steps, principles or options;
  - "screenshot" when a real platform screenshot (UI, console, settings page) would help; the author replaces the placeholder.
  Spread them through the post where they serve the text. Give them ids "img2", "img3", and so on.

Callbacks (threads the post comes back to, so it feels written by a person with a point rather than a list of sections):
- Plan one to three. A **key concept** is the idea the reader should leave with; set it up early, bring it back in later sections where it does new work (applied, extended, or tested), and land it in the closing.
- A **running joke** is a gag specific to this post, set up once and called back with a twist. Plan one only at humor level 3 or higher, and only in the author's kind of humor; at humor 0-2 plan key concepts only.
- Each revisit must add something (a new angle, an escalation, a payoff); never repeat the same line.

Title options must follow the author's title formulas from the voice profile. Choose the strongest as `chosen_title`.
