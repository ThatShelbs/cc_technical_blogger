Produce the final meme for this concept.

Post title: $title

The concept:
<concept>
$concept
</concept>

<format_spec>
$spec
</format_spec>

Cast: $cast
Visual style: $visual_style
$brand
$variation

Caption guidance from the author's voice profile (the caption sits under the image; keep it short, never repeat the meme's words, and do not include the credit):
<image_guidance>
$image_guidance
</image_guidance>

Return:
- `texts`: final words for every text slot (tighten the concept's draft if you can; obey each character limit).
- `cast_defs` and `art`: the drawings, following the region briefs exactly so the format is instantly recognizable.
- `data`: chart data, if the format needs it.
- `alt`: what the image shows, including every word in it, for a reader who cannot see it.
- `caption`: a short caption in the author's style.
