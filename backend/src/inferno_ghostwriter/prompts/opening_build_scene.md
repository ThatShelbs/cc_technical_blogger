Stage the opening image for this post as a **visual metaphor** scene.

Post title: $title
The concept the panel chose:
<concept>
$concept
</concept>
$colors
Visual style: $visual_style
$brand
$variation
$fix

What you can use (code draws all of it; you choose):
<kit>
$kit
</kit>

How to stage it:
- One focal point, read in under two seconds at 300px wide. Pick the layout that puts it on a third or dead centre.
- Characters carry the emotion: pick the kind, expression and pose that make a reader feel the post's tension or payoff (a shocked ghost at a plinko board, a smug dog pointing at a chart). One to three characters; none only when the object says it all.
- The custom object is the post's specific metaphor (the plinko board, the elephant and flashlights, the leaky pipeline). Draw it as clean SVG elements in viewBox `0 0 600 500` on a transparent background: bold simple shapes, paths and curves, gradients for depth, clean outlines, under about 250 elements, no text, nothing outside the box. Leave `object_svg` empty when kit props say it better.
- Labels (at most four, one to three words each, from the post) only where they make the metaphor click. Never the title.
- `tone` picks a dark or light background when the idea clearly wants one; leave it empty otherwise.

The author's guidance on images and captions:
<image_guidance>
$image_guidance
</image_guidance>

The post's opening:
<post>
$post
</post>

Return the scene, the alt text and a caption.
