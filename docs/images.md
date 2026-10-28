# Images

Every post gets images that add value for the reader. The plan decides how many (about one per 350 words by default, at least two, or the persona's default) and what each is for.

Claude draws every image itself: vector art as SVG and data visualizations as Vega-Lite specs. There is no third-party image model and nothing to configure.

| Kind | Purpose | Made by |
| --- | --- | --- |
| **hero** | Opening image and thumbnail: an editorial "stock-style" illustration made for this post | Claude SVG (16:9) |
| **illustration** | A conceptual image or visual metaphor for a section | Claude SVG (16:9) |
| **icon** | One concept icon, or a row of 2-4, anchoring a list of steps or principles | Claude SVG |
| **diagram** | Concepts, workflows, architectures, comparisons, decision trees | Claude SVG |
| **chart** | Data visualization (real numbers from the post, or labeled illustrative data) | Claude Vega-Lite spec with inline data |
| **screenshot** | A real UI/console screenshot would help | Placeholder card; replace it with your screenshot |
| **meme** | The closing joke | Claude SVG cartoon + classic top/bottom captions drawn with Pillow |

## Design and rendering

For each slot Claude reads the text around the image, the author's *Images & Captions* guidance from the voice profile, and the persona's visual style, then returns a structured design: SVG markup or a chart spec, plus alt text and a caption in the author's caption style. The art direction prompt (`prompts/image_system.md`) asks for layered compositions, gradients, soft shadows and the inferno palette, so hero and illustration images look like finished editorial art rather than clip art.

Nothing a model writes is executed:

- SVG is parsed with `lxml` and sanitized (no scripts, event handlers, `foreignObject` or external references), then rasterized locally by **resvg**.
- Charts are declarative Vega-Lite (remote data URLs are rejected), rendered locally by **vl-convert**.

## Credits

Each image gets a credit from the persona's template (default `Author: {name}; Made with {tool}`), where `{tool}` names the Claude model that drew it:

> The saddest pie; Author: Shelby Temple; Made with Claude Opus 5.5 (SVG)

Charts read "Made with Claude Opus 5.5 + Vega-Lite", and charts with made-up numbers are labeled *(illustrative data)*. You can edit any caption, credit or alt text. Captions and credits live only on the image; caption lines the writer puts in the post body are removed.

## When an image fails

One failed image never fails the post: it shows its error and a **Redraw** button, and the rest of the post is saved as usual. Jobs run in memory, so an image still waiting when the app stopped is marked as failed at the next startup instead of spinning forever.

## Redraw, new idea, replace, versions

- **Redraw**: Claude draws the same idea again with a different composition or treatment.
- **New idea**: Claude throws out the concept and designs a different image for the same purpose.
- **Replace**: upload your own image (PNG, JPEG, WebP, ...; converted to PNG).
- **Versions**: every version is kept; click one to restore it.
