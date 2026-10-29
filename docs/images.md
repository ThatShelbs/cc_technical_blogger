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
| **meme** | The closing joke | One of 18 meme formats: Claude writes the joke and draws the art, Proseferno owns layout and type ([below](#closing-memes)) |

## Design and rendering

For each slot Claude reads the text around the image, the author's *Images & Captions* guidance from the voice profile, and the post's brand kit (below), then returns a structured design: SVG markup or a chart spec, plus alt text and a caption in the author's caption style. The art direction prompt (`prompts/image_system.md`) asks for layered compositions, gradients, soft shadows and the inferno palette, so hero and illustration images look like finished editorial art rather than clip art.

Nothing a model writes is executed:

- SVG is parsed with `lxml` and sanitized (no scripts, event handlers, `foreignObject` or external references), then rasterized locally by **resvg**.
- Charts are declarative Vega-Lite (remote data URLs are rejected), rendered locally by **vl-convert**.

## Closing memes

The meme is the last thing a reader sees and the thing they share, so it gets its own pipeline (`images/memes/`):

1. **Writers' room** (`prompts/meme_ideas.md`, effort `effort_meme_ideas`, default high). Claude reads the whole post, the plan's closing joke and its running jokes and key concepts, the humor dial and the voice profile's *Humor* section, then pitches five concepts across at least three format families, writes the words for every slot, and scores each on relevance, instant recognizability, surprise, clarity, voice fit and whether it works shared on its own. The best one wins.
2. **Production** (`prompts/meme_build.md`). Claude fills the chosen format: final words for each text slot, SVG art for each art region (characters defined once as `<symbol>`s so they look the same in every panel), and chart data where the format needs it. Missing pieces or overlong text get one retry with the problems quoted back.
3. **Composer** (`compose.py`). Code draws the layout, panel frames, speech bubbles, charts and chrome, places Claude's art in its regions (sanitized, ids made unique), and typesets every string with Pillow: each one is sized to the largest font that fits its box, parallel slots (rows, cells, panels) share one size, and words are only broken when nothing else fits. Text cannot overflow.

If a build still cannot be drawn, the meme falls back to a classic top/bottom caption meme over the Proseferno robot instead of failing.

| Family | Formats |
| --- | --- |
| Famous formats, recast with our robot (no real people or characters) | Nope / Yep (Drake), pointing twins, distracted robot, expanding brain, This is fine, two buttons, midwit bell curve, four-step plan (Gru) |
| Chart jokes, drawn with real chart machinery | terrible 3D exploded pie, spurious correlation (dual-axis Vega-Lite), Venn diagram |
| Comics | three-panel strip, four-panel grid |
| Fake artifacts | team chat thread, terminal session, Nutrition Facts label, alignment chart |
| Caption | classic top/bottom caption meme (also the fallback) |

Chart jokes are captioned *(data: entirely made up)*. A brand kit palette recolors the pie and Venn; Claude's art follows the brand style and palette.

On the meme card, **New idea** moves to the next-best pitch from the writers' room without asking Claude to pitch again (it pitches fresh jokes, avoiding the old ones, once all five are used), **Redraw** draws the same joke again, **Edit** changes words or art by instruction, and the **format** menu remakes the meme in a format you pick (`POST /api/images/{id}/redraw` with `meme_format`; formats from `GET /api/meme-formats`).

To review every format, run `uv run python scripts/meme_gallery.py` (canned builds, free) and open `data/meme-gallery/index.html`. `--real --yes` asks Claude for new memes for your latest posts (costs money).

**Adding a format:** add a `MemeFormat` to `FORMATS` in `images/memes/formats.py` (text slots with boxes and character limits, art regions with briefs, `groups` for slots that should share a size). If the template draws anything (frames, charts, chrome), add a scene function to `SCENES` in `compose.py`. Add canned words to `DEMO_MEME_TEXTS` in `demo.py`; the tests render every format.

## Brand kit (per post)

Each post has its own image brand kit (`Project.brand_kit`): an image style, a palette of up to eight colors, a font for text in images, and a recurring motif. Set it under *Customize* when you start a post, or later in the **Image brand kit** card next to the post, where **Save and redraw images** gives every drawn image the new look (`POST /api/projects/{id}/images/redraw`; uploads and screenshots stay). Empty fields fall back to the persona's visual style and the inferno palette.

## Credits

Each image gets a credit from the persona's template (default `Author: {name}; Made with {tool}`), where `{tool}` names the Claude model that drew it:

> The saddest pie; Author: Shelby Temple; Made with Claude Opus 5.5 (SVG)

Charts read "Made with Claude Opus 5.5 + Vega-Lite", memes "Made with Claude Opus 5.5 (meme)", and charts with made-up numbers are labeled *(illustrative data)*. Captions never name another tool as the image's maker, even if your own posts credit one. You can edit any caption, credit or alt text. Captions and credits live only on the image; caption lines the writer puts in the post body are removed.

## When an image fails

One failed image never fails the post: it shows its error and a **Redraw** button, and the rest of the post is saved as usual. Jobs run in memory, so an image still waiting when the app stopped is marked as failed at the next startup instead of spinning forever.

## Redraw, new idea, replace, versions

- **Edit**: tell Claude what to change ("make the arrows orange", "label the y-axis in percent"). Claude gets the current SVG or chart spec and changes only what you describe (`POST /api/images/{id}/edit`, `prompts/image_edit.md`). Only images Claude drew can be edited this way.
- **Redraw**: Claude draws the same idea again with a different composition or treatment.
- **New idea**: Claude throws out the concept and designs a different image for the same purpose.
- **Replace**: upload your own image (PNG, JPEG, WebP, ...; converted to PNG).
- **Versions**: every version is kept; click one to restore it.
