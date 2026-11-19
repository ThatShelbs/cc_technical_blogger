# Images

Every post gets images that add value for the reader. The plan decides how many (by default as often as the author uses images in their own posts, measured in the voice profile's baseline, never more than one per 150 words; one per 350 words when there is no measurement; at least two, at most twelve; or the persona's default) and what each is for. Every example the post introduces ("Here is the file:") gets its image or code block; see [Examples the post introduces](#examples-the-post-introduces).

Claude draws every image itself: vector art as SVG and data visualizations as Vega-Lite specs. There is no third-party image model and nothing to configure.

| Kind | Purpose | Made by |
| --- | --- | --- |
| **hero** | Opening image and thumbnail, in one of nine styles a judging panel picks from: visual metaphor, data art, opening meme, cheat sheet, sourced data chart, big number, versus split, framework diagram or screen mock ([Opening images](opening-images.md)) | Claude SVG, a code template with Claude's words and verified data, or the meme room (16:9) |
| **illustration** | A conceptual image or visual metaphor for a section | Claude SVG (16:9) |
| **icon** | One concept icon, or a row of 2-4, anchoring a list of steps or principles | Claude SVG |
| **diagram** | Concepts, workflows, architectures, comparisons, decision trees | Claude SVG |
| **chart** | Data visualization (real numbers from the post, or labeled illustrative data) | Claude Vega-Lite spec with inline data |
| **screenshot** | The post shows what a screen looks like (an app page, settings, a chat, an editor, a terminal) | Claude SVG: a faithful mock of that screen with the post's real content; **Replace** it with a real capture if you have one |
| **meme** | The closing joke | One of 23 meme formats: Claude writes the joke and draws the art, Inferno Ghostwriter owns layout and type ([below](#closing-memes)) |

Each image is told what the post's other images show, so the set looks like one piece of work and no two images repeat each other. Platforms crop the thumbnail from the center of the opening image (as wide as 5:2), so it keeps everything that matters in the middle band. The opening image has its own pitch, panel and review; see [Opening images](opening-images.md).

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

The meme is the last thing a reader sees and the thing they share, so it gets its own pipeline (`images/memes/`). The same room makes an opening meme when a post opens with one (a [meme sandwich](opening-images.md#meme-sandwich)); the closing meme is then made after it and told about it.

1. **Writers' room** (`prompts/meme_ideas.md`, effort `effort_meme_ideas`, default high). Claude reads the whole post (a very long post keeps its opening and its ending, where callbacks pay off), the plan's closing joke and its running jokes and key concepts, the humor dial and the voice profile's *Humor* section, then pitches five concepts across at least three format families. Each pitch has the final words for every slot, chart data where the format needs it and a caption, and is scored on relevance, instant recognizability, surprise, clarity, voice fit and whether it works shared on its own. The best one wins. The room is told which formats the author's last three memes used, so posts do not all end the same way. It is also told the post's [formula](formulas.md#the-closing-meme) (article type, opener, body, closer), because the meme lands straight after the closer: it must add a beat, not repeat the closer, and a post that opened on a joke can have that joke brought back.
2. **Staging** (no drawing call). The famous formats and the comics are drawn by code from the [character kit](image-kit.md): each classic's staging (panels, framing, who stands where, each beat's pose and expression) is fixed in `stagings.py`, so *Right? Right?* is always the meadow two-shot, the hopeful close-up, the blank stare and the frozen smile, and *This is fine* is always our dog in a bowler hat with a mug in a burning room. Claude only casts the roles (`cast`: our ghost, dog, cat, person or robot) and, for comics, picks each panel's backdrop, characters, expressions and poses (`panels`). Art-free formats (chat, terminal, Nutrition Facts, alignment chart, pie, spurious correlation, Venn) are composed from the pitch too. Production (`prompts/meme_build.md`) is only asked for older pitches that lack their data.
3. **Composer** (`compose.py`). Code draws the layout, panel frames, speech bubbles, charts and chrome, the kit's staged art in the meme's [scheme](image-kit.md#palettes-imagespalettespy), and typesets every string with Pillow: each one is sized to the largest font that fits its box, parallel slots (rows, cells, panels) share one size, and words are only broken when nothing else fits. Text cannot overflow.

If a build still cannot be drawn, the meme becomes the best other pitch in a format with no art (which cannot fail), so the reader still gets a whole joke. Only when there is none (for example, the author asked for one format) does it fall back to a classic top/bottom caption meme over the Inferno Ghostwriter ghost at its laptop. Either way the card says which format could not be drawn (`fallback_from` in the meme's state).

| Family | Formats |
| --- | --- |
| Famous formats, staged faithfully with our own cast (no real people or characters) | Nope / Yep (Drake), pointing twins, distracted, expanding brain, This is fine (one or two panels, our dog), two buttons, midwit bell curve, four-step plan (Gru), **Right? Right?** (the "For the better, right?" format), always has been, change my mind, shocked strip, is this a...?, Panik / Kalm / Panik, running-away balloon |
| Chart jokes, drawn with real chart machinery | terrible 3D exploded pie, spurious correlation (dual-axis Vega-Lite), Venn diagram |
| Comics | three-panel strip, four-panel grid |
| Fake artifacts | team chat thread, terminal session, Nutrition Facts label, alignment chart |
| Caption | classic top/bottom caption meme (also the fallback) |

Chart jokes are captioned *(data: entirely made up)*. A brand kit palette recolors the pie and Venn; Claude's art follows the brand style and palette.

### Looks, the judging panel and the review

Memes are meant to look different from one another. Each meme is drawn in one **look** (`images/memes/looks.py`, the only place a look is defined): inferno flat (the brand look), kawaii, soft 3D, viridis lab, magma noir, corporate slate, retro comic, pixel arcade, whiteboard doodle, blueprint and inferno robots. A look sets the kit's treatment (outline weight, flat, soft or 3D shading, halftone, linework, marker wobble, a pixel grid) and the **theme** the composer paints templates with: comic gutters, chat header, chart marks, alignment bands, bubble outlines. Colors never come from the look: every meme is drawn in a **scheme**, inferno, magma or viridis on white, gray or near-black (`images/palettes.py`), rotated against the author's recent images; a look may prefer a ramp or a tone, and a brand kit palette still wins.

The look comes from, in order: the author's pick (the *Look* chips on the Ideas board, `meme_look`), the room's suggestion for that joke unless the author used it in one of their last two memes, or a weighted random pick among the looks they have not used lately. Redraw and *New idea* move to a different look; *Words* and *Edit* keep it. The look is stored in the meme's state (`look`); older memes read as inferno flat.

Two [judging panels](image-kit.md#the-judging-panel-imagespanelpy) make the first meme a winner, both many small independent seats on Haiku, Sonnet and Opus run at once:

- **Pitch panel** (`image_panel_meme`). The writers no longer grade their own jokes. Scrollers, a cold reader (rules a joke out below 5), a comedy editor (may punch up the winner's words, used only within every slot's limit), a meme connoisseur (is the format used the way the internet uses it?) and the author score every pitch. Code adds the votes; the totals rank *Next best idea*. If too few seats answer, the writers' own scores are used.
- **Render panel and final pick** (`image_panel_render`, `image_panel_final`, setting `meme_review`). The two best pitches are drawn (no drawing call), blind readers say what each picture means with no context (matched against the premise), a craft and an appeal seat look closely, and Opus picks one and may ask for one fix (applied by restaging). Skipped for redraws, a picked pitch, with a Claude Code subscription connection (it cannot receive images), and for opening memes (the opening room judges them). The card shows *Why this one* and what strangers read in it.

The writers' room is also told how the joke should be built (one specific truth, the punch word last, callbacks, an exaggerated picture, the ghost as an earnest, slightly anxious overachiever), lists about 12 raw angles before pitching, and must include a callback, a visual gag and an art-free format among its five.

On the meme card:

- **Ideas** opens the pitch board: all five jokes with their format and words. *Use this idea* draws one (`POST /api/images/{id}/redraw` with `meme_concept`), *Next best idea* moves to the best untried pitch (fresh pitches, avoiding the old ones, once all five are used), and the format menu asks for five new pitches in a format you pick (`meme_format`; formats from `GET /api/meme-formats`). Moving between pitches never asks Claude to pitch again, and a pitch with no art appears at once.
- **Words** lets you retype any text in the meme (`PUT /api/images/{id}/meme-words`). The art is kept, the text is refitted, the alt text is rebuilt from the new words, and Claude is not called.
- **Redraw** draws the same joke in a different look and scheme.
- **Edit** changes the words, the casting or the comic panels by instruction ("make it a robot", "the second panel is a close-up"); the kit redraws it.
- 👍 / 👎 teach the persona's taste ([taste](image-kit.md#the-authors-taste-imagestastepy)).

To review every format, run `uv run python scripts/meme_gallery.py` (canned builds, free; add `--looks` to see every format in every look) and open `data/meme-gallery/index.html`. `--real --yes` asks Claude for new memes for your latest posts (costs money).

**Adding a format:** add a `MemeFormat` to `FORMATS` in `images/memes/formats.py` (text slots with boxes and character limits, `groups` for slots that should share a size). A famous format gets a staging function in `stagings.py` (`STAGINGS`, its cast roles in `ROLES`) and its look, `signature` beats and `fit_tags` in `_STAGED`; if it needs chart data, describe it in `data` (the pitch menu shows that text). If the template draws anything (frames, charts, chrome), add a scene function to `SCENES` in `compose.py`. Add canned words to `DEMO_MEME_TEXTS` in `demo.py`; the tests render every format.

## Brand kit (per post)

Each post has its own image brand kit (`Project.brand_kit`): an image style, a palette of up to eight colors, a font for text in images, and a recurring motif. Set it under *Customize* when you start a post, or later in the **Image brand kit** card next to the post, where **Save and redraw images** gives every drawn image the new look (`POST /api/projects/{id}/images/redraw`; uploads stay). Empty fields fall back to the persona's visual style and the inferno palette.

## Credits

Each image gets a credit from the persona's template (default `Author: {name}; Made with {tool}`), where `{tool}` names the Claude model that drew it:

> The saddest pie; Author: Shelby Temple; Made with Claude Opus 5.5 (SVG)

Charts read "Made with Claude Opus 5.5 + Vega-Lite", memes "Made with Claude Opus 5.5 (meme)", code-laid-out opening images "Made with Claude Opus 5.5 (layout)", and charts with made-up numbers are labeled *(illustrative data)*. Captions never name another tool as the image's maker, even if your own posts credit one. You can edit any caption, credit or alt text. Captions and credits live only on the image; caption lines the writer puts in the post body are removed.

## When an image fails

One failed image never fails the post: it shows its error and a **Redraw** button, and the rest of the post is saved as usual. Jobs run in memory, so an image still waiting when the app stopped is marked as failed at the next startup instead of spinning forever.

## Redraw, new idea, replace, versions

- **Edit**: tell Claude what to change ("make the arrows orange", "label the y-axis in percent"). Claude gets the current SVG or chart spec and changes only what you describe (`POST /api/images/{id}/edit`, `prompts/image_edit.md`). Only images Claude drew can be edited this way. Your edits are remembered (`ProjectImage.edits`): a later **Redraw** or **Remix** builds on the edited picture (its current design goes into the draw prompt) and applies only the new look, instead of going back to the original idea. **New idea**, picking another pitch, style or format, or uploading a replacement starts over.
- **Redraw**: Claude makes the image better, not just different. It first looks at the current image and names its weakest point and the concrete fixes (`ImprovementPlan`, `prompts/image_improve.md`; the PNG is sent when the connection can show images, else its source), then redraws the same idea with those fixes plus one or two experiments: other colors, another cast (dogs, cats, people, robots or objects instead of the ghost), another staging or another medium. The card says what was tried, and the next redraw avoids the last eight experiments. See *Redraw that improves* below.
- **Remix**: choose the experiment yourself (colors, who is in it, staging, medium); anything left on *Surprise me* is picked for you.
- **Builds on**: draw this image from an earlier one so both share data, colors and shapes. See *Images that build on each other* below.
- **New idea**: Claude throws out the concept and designs a different image for the same purpose.
- **Replace**: upload your own image (PNG, JPEG, WebP, ...; converted to PNG).
- **Versions**: every version is kept; click one to restore it.

## Redraw that improves

`images/remix.py` is the only place a redraw experiment is defined, and every image goes through it: the opening image, the closing meme and everything between.

| Dimension | Options | Applies to |
| --- | --- | --- |
| Colors (`palette`) | inferno, viridis, ocean, sunrise pastel, forest, one flame on grey, magma noir, candy pop, blueprint, sepia print | every image (charts, code-drawn openers and meme templates take the colors in code) |
| Who is in it (`cast`) | the ghost, friendly robots, dogs, cats, stylized people, woodland animals, an octopus, living objects, no characters | illustrations, visual-metaphor openers, memes |
| Staging (`staging`) | close-up, wide shot, isometric, top-down, before/after split, strict symmetry, diagonal | illustrations, diagrams, visual-metaphor and data-art openers |
| Medium (`medium`) | flat vector, paper cut, line art, soft 3D clay, woodcut/risograph | illustrations, icons, visual-metaphor and data-art openers |

- `choose_tweaks` picks up to two experiments with no model call, from the dimensions that suit the image (`remix_dimensions`), skipping what the last eight redraws tried (`ProjectImage.remix["recent"]`).
- A post's brand-kit palette is never replaced at random; a palette you pin in **Remix** is.
- The ghost stays the house character. A redraw may try another cast because you asked for experiments; real people's likenesses and other companies' characters are never used.
- `POST /api/images/{id}/redraw` takes `tweaks` (`{"palette": "viridis", "cast": "dogs"}`) and `improve` (false = only the twist). `GET /api/remix-options` lists the catalog. `ImageOut.remix` holds the critique and the experiments; `ImageOut.remix_dimensions` what can vary.
- Picking a stored pitch or a format (the Ideas boards) skips the critique: you chose the idea. **Redraw all images** redraws plainly, with no critique and no experiments, so a brand-kit change does not also change the look.
- A failed critique never fails the redraw: the experiments still apply.

## Images that build on each other

Two images that tell one story (a single fitted line, then the same points split into groups for Simpson's paradox) must look like the same data taken further, not two unrelated datasets.

- The planner sets `builds_on` on an image slot to the id of the earlier image it extends (`ImageSlot.builds_on`, `prompts/plan.md`); `normalize_slots` keeps only links to an earlier image that is still in the post.
- The later image waits for the earlier one, then is designed with that image's source in the prompt (`ImageService._builds_on`): a chart copies the base chart's data rows, scales, colors and size and adds only what is new; other kinds reuse the palette, shapes, labels and layout.
- On the card, **Builds on** links an image to any earlier drawn image and redraws it from it (`POST /api/images/{id}/build-on`), or unlinks it (`DELETE`).
- Redrawing the earlier image leaves the later ones drawn from its old version; the card says so and offers **Redraw them to match** (`POST /api/images/{id}/redraw-dependents`).
- The opening image and the closing meme stand on their own, and uploads cannot be built on (they have no source).

## Text that follows the image

An image and the sentences around it should agree. Two things keep them in step (`writer/image_text.py`, `writer/add_image.py`).

**After a redraw, the text is checked.** When Redraw, New idea, a meme format or pitch, an opening style or pitch, **Edit** or *Redraw all* changes what an image is, the same job asks Claude for small find/replace edits to any sentence that described the old picture (a "Drake" line after the meme became a different format, "the left column" after the labels changed) (`prompts/image_text_sync.md`, task `image text sync`). Claude is told what each image was and what it is now (`describe_image`: kind, purpose, meme format and joke, opening style and idea, alt text, caption) and returns no edits when the text never mentioned the picture, so most redraws change nothing and cost one cheap call. Redraw all makes one combined call after every image is drawn. When text changes, the image card shows a note and the change is one **Undo last change** away (`Project.revisions`, kind `image`). The check never fails a redraw (a failure is reported as `text_error`), is skipped while another text job runs, and does not run for uploads, version restores, a meme's **Words** (you typed them) or the redraws a feedback tweak makes (the text was just written for them).

**Add an image at a highlight.** Highlight text in the Preview (or the Markdown editor) and click **Add image** (`POST /api/projects/{id}/images`, job `add_image`, one of the text jobs). Claude (`prompts/image_add.md`, task `image placement`) picks the kind that adds the most (diagram, chart, illustration or icon), what it shows, the paragraph or sentence it follows, and any adjacent sentence that should change ("as the diagram below shows"). Code then picks the break: the end of the paragraph, or a split after the sentence when the paragraph is long; never inside a code block, list, table or quote, never between a lead-in ("Here is the file:") and its example, never after the closing meme (`place_placeholder`). The image gets the next free `imgN` slot in the plan (so later edits and regenerations keep it) and its row is put in reading order. At most 15 images per post. **Undo last change** takes the image and its text edits out together.
