# Images

Every post gets images that add value for the reader. The plan decides how many (by default as often as the author uses images in their own posts, measured in the voice profile's baseline, never more than one per 150 words; one per 350 words when there is no measurement; at least two, at most twelve; or the persona's default) and what each is for. Every example the post introduces ("Here is the file:") gets its image or code block; see [Examples the post introduces](#examples-the-post-introduces).

Claude draws every image itself: vector art as SVG and data visualizations as Vega-Lite specs. There is no third-party image model and nothing to configure.

| Kind | Purpose | Made by |
| --- | --- | --- |
| **hero** | Opening image and thumbnail: an editorial "stock-style" illustration made for this post | Claude SVG (16:9) |
| **illustration** | A conceptual image or visual metaphor for a section | Claude SVG (16:9) |
| **icon** | One concept icon, or a row of 2-4, anchoring a list of steps or principles | Claude SVG |
| **diagram** | Concepts, workflows, architectures, comparisons, decision trees | Claude SVG |
| **chart** | Data visualization (real numbers from the post, or labeled illustrative data) | Claude Vega-Lite spec with inline data |
| **screenshot** | The post shows what a screen looks like (an app page, settings, a chat, an editor, a terminal) | Claude SVG: a faithful mock of that screen with the post's real content; **Replace** it with a real capture if you have one |
| **meme** | The closing joke | One of 18 meme formats: Claude writes the joke and draws the art, Proseferno owns layout and type ([below](#closing-memes)) |

Each image is told what the post's other images show, so the set looks like one piece of work and no two images repeat each other. Platforms crop the thumbnail from the center of the hero (as wide as 5:2), so the hero keeps its subject in the middle band.

## Examples the post introduces

Authors lead into examples ("Here is the top of the file:", "This is what it looks like:"). A post must never point at something that is not there, so (`writer/examples.py`):

- The plan gives every visual example a slot, and the writer and reviser are told that the lead-in is followed right away by its example: a placeholder for a screen or visual, a fenced code block for code, prompts, file excerpts and terminal output (even when the author's own posts show those as screenshots, which the app cannot paste).
- The editor gets every lead-in with nothing after it (`find_dangling_leadins`: a paragraph that ends in a colon and promises to show something, followed by prose or a section heading) and tells the reviser to add what is missing.
- A placeholder the writer made up right after a lead-in becomes a real slot instead of being dropped.
- Whatever is still missing after editing becomes a new image slot right after its lead-in (`add_example_slots`; usually a drawn *screenshot*), briefed with the lead-in and the text around it, so it is drawn with the post's other images. The text is not changed. At most eight images are added this way.
- A post written before this check can get the same fix: `POST /api/projects/{id}/examples` (job `fill_examples`, `fill_missing_examples`) adds and draws the missing images, keeps every existing image, and saves the old text in the history.

## Design and rendering

For each slot Claude reads the text around the image, the author's *Images & Captions* guidance from the voice profile, and the post's brand kit (below), then returns a structured design: SVG markup or a chart spec, plus alt text and a caption in the author's caption style. The art direction prompt (`prompts/image_system.md`) asks for layered compositions, gradients, soft shadows and the inferno palette, so hero and illustration images look like finished editorial art rather than clip art.

Nothing a model writes is executed:

- SVG is parsed with `lxml` and sanitized (no scripts, event handlers, `foreignObject` or external references), then rasterized locally by **resvg**.
- Charts are declarative Vega-Lite (remote data URLs are rejected), rendered locally by **vl-convert**. A brand kit palette of three or more colors becomes the chart's color scheme in code, and a chart whose numbers are made up says *Illustrative data* under its title, so the label survives when the image is shared without its caption.

A design that cannot be drawn (SVG that is not SVG, a chart spec Vega-Lite rejects) is sent back to Claude once with the error quoted (`draw_with_retry` in `images/base.py`). Smaller slips never get that far: a bare `&` or an unclosed tag is repaired by the parser (`render.parse_xml`) before sanitizing.

Fonts are bundled in `images/memes/fonts/` (Anton, Inter, Comic Neue and JetBrains Mono, all under the SIL Open Font License; the license texts sit next to them). Meme text always uses them, and SVG text falls back to them when it names a font the machine lacks, so images look the same on Windows, macOS, Linux and in the packaged app.

## Closing memes

The meme is the last thing a reader sees and the thing they share, so it gets its own pipeline (`images/memes/`):

1. **Writers' room** (`prompts/meme_ideas.md`, effort `effort_meme_ideas`, default high). Claude reads the whole post (a very long post keeps its opening and its ending, where callbacks pay off), the plan's closing joke and its running jokes and key concepts, the humor dial and the voice profile's *Humor* section, then pitches five concepts across at least three format families. Each pitch has the final words for every slot, chart data where the format needs it and a caption, and is scored on relevance, instant recognizability, surprise, clarity, voice fit and whether it works shared on its own. The best one wins. The room is told which formats the author's last three memes used, so posts do not all end the same way. It is also told the post's [formula](formulas.md#the-closing-meme) (article type, opener, body, closer), because the meme lands straight after the closer: it must add a beat, not repeat the closer, and a post that opened on a joke can have that joke brought back.
2. **Production** (`prompts/meme_build.md`), only for formats with art. Claude draws SVG art for each art region (characters defined once as `<symbol>`s so they look the same in every panel) and may tighten the words. Missing pieces or overlong text get one retry with the problems quoted back. The seven formats with no art (chat, terminal, Nutrition Facts, alignment chart, pie, spurious correlation, Venn) skip this call: they are composed straight from the pitch.
3. **Composer** (`compose.py`). Code draws the layout, panel frames, speech bubbles, charts and chrome, places Claude's art in its regions (sanitized, ids made unique), and typesets every string with Pillow: each one is sized to the largest font that fits its box, parallel slots (rows, cells, panels) share one size, and words are only broken when nothing else fits. Text cannot overflow.

If a build still cannot be drawn, the meme becomes the best other pitch in a format with no art (which cannot fail), so the reader still gets a whole joke. Only when there is none (for example, the author asked for one format) does it fall back to a classic top/bottom caption meme over the Proseferno robot. Either way the card says which format could not be drawn (`fallback_from` in the meme's state).

| Family | Formats |
| --- | --- |
| Famous formats, recast with our robot (no real people or characters) | Nope / Yep (Drake), pointing twins, distracted robot, expanding brain, This is fine, two buttons, midwit bell curve, four-step plan (Gru) |
| Chart jokes, drawn with real chart machinery | terrible 3D exploded pie, spurious correlation (dual-axis Vega-Lite), Venn diagram |
| Comics | three-panel strip, four-panel grid |
| Fake artifacts | team chat thread, terminal session, Nutrition Facts label, alignment chart |
| Caption | classic top/bottom caption meme (also the fallback) |

Chart jokes are captioned *(data: entirely made up)*. A brand kit palette recolors the pie and Venn; Claude's art follows the brand style and palette.

On the meme card:

- **Ideas** opens the pitch board: all five jokes with their format and words. *Use this idea* draws one (`POST /api/images/{id}/redraw` with `meme_concept`), *Next best idea* moves to the best untried pitch (fresh pitches, avoiding the old ones, once all five are used), and the format menu asks for five new pitches in a format you pick (`meme_format`; formats from `GET /api/meme-formats`). Moving between pitches never asks Claude to pitch again, and a pitch with no art appears at once.
- **Words** lets you retype any text in the meme (`PUT /api/images/{id}/meme-words`). The art is kept, the text is refitted, the alt text is rebuilt from the new words, and Claude is not called.
- **Redraw** draws the same joke with new art (hidden for formats with no art).
- **Edit** changes words or art by instruction.

To review every format, run `uv run python scripts/meme_gallery.py` (canned builds, free) and open `data/meme-gallery/index.html`. `--real --yes` asks Claude for new memes for your latest posts (costs money).

**Adding a format:** add a `MemeFormat` to `FORMATS` in `images/memes/formats.py` (text slots with boxes and character limits, art regions with briefs, `groups` for slots that should share a size). A format with no `regions` is drawn from the pitch alone; if it needs chart data, describe it in `data` (the pitch menu shows that text). If the template draws anything (frames, charts, chrome), add a scene function to `SCENES` in `compose.py`. Add canned words to `DEMO_MEME_TEXTS` in `demo.py`; the tests render every format.

## Brand kit (per post)

Each post has its own image brand kit (`Project.brand_kit`): an image style, a palette of up to eight colors, a font for text in images, and a recurring motif. Set it under *Customize* when you start a post, or later in the **Image brand kit** card next to the post, where **Save and redraw images** gives every drawn image the new look (`POST /api/projects/{id}/images/redraw`; uploads stay). Empty fields fall back to the persona's visual style and the inferno palette.

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
