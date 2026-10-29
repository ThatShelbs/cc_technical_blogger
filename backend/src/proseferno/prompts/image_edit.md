Edit the **$kind** image `$slot_id` exactly as the author asks. This is an edit, not a redraw: keep the concept, composition, content and everything the instruction does not mention, and change only what it asks for.

<instruction>
$instruction
</instruction>

$brand

Current caption: $caption
Current alt text: $alt

The current design (SVG markup, a Vega-Lite spec, or a meme as JSON with its SVG and captions):
<current>
$spec
</current>

Return the complete edited design in the same format, every hard requirement still met. Update the caption and alt text only if the edit changes what they describe.
