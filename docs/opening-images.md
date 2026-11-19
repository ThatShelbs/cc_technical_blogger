# Opening images

The opening image sits right under the title and is also the post's thumbnail. In a feed it shows at about 300 pixels wide next to the title, so it decides whether anyone clicks. Inferno Ghostwriter treats it like the closing meme: a room pitches several ideas, an independent panel judges them, and the winner is built, checked and reviewed. The goal is an image people assume a skilled designer made for this exact post: professional, crisp, accurate, on-title and clickable, never generic AI filler.

The code lives in `backend/src/inferno_ghostwriter/images/opening/`:

| Module | Role |
| --- | --- |
| `styles.py` | The catalog: every opening style, what it suits, and the only place a style is defined |
| `room.py` | `OpeningRoom`: pitch, panel, research, build, review, fallback |
| `templates.py`, `charts.py`, `canvas.py` | Code-drawn templates: Claude writes the words and data, code owns layout, type and colour |
| `facts.py` | The fact check for data openers |
| `specs.py` | The structured outputs (`OpeningIdeas`, `OpeningBuild`, `SceneSpec`); judging is `images/panel.py` |
| `scene.py` | Visual-metaphor scenes from the character kit: layouts, the custom object, labels |
| `feedcard.py` | The thumbnail as a feed card (crop plus title) for the final pick |

## The styles

| Style | What it is | Built by | Suits |
| --- | --- | --- | --- |
| **Visual metaphor** (`editorial`) | The post's core mechanism acted out as one physical scene: marketing spend as coins through a plinko board into channel buckets; a single source of truth as specialists each lighting one part of an elephant | Kit scene: Claude casts likeable kit characters and props and draws one custom object; code lays it out ([kit](image-kit.md)) | every post (always in the running) |
| **Data art** (`data_art`) | Abstract and beautiful: flowing lines, particle fields, soft networks, contours. Never literal objects (no coins, dice, people or icons; that is the visual metaphor's job). The subject shows only as a subtle hint in its structure, rhythm and colour, and it shows no numbers, so it claims nothing | Claude SVG | every post, best for data science, ML, analytics and finance |
| **Opening meme** (`meme`) | A joke that sets up the tension the post resolves; with the closing meme it makes a *meme sandwich* | The meme room | opinion, lessons learned, listicles, joke openers; humor 3+ |
| **Cheat sheet** (`cheat_sheet`) | 4-9 numbered tiles: the steps, rules or commands a reader would save | Code template | how-to, tutorial, listicle |
| **Data story chart** (`data_chart`) | One factual chart that makes a big point: annotated line, slope, dumbbell, waterfall, tornado, ranked bars, heatmap or spider | Code templates + verified data | case study, comparison, explainer, news peg, surprising number |
| **Big number** (`big_number`) | One huge sourced figure, what it means and its source | Code template + verified data | case study, opinion, lessons learned, surprising number |
| **Versus split** (`versus`) | Two columns: before and after, myth and reality, old way and new | Code template | comparison, tool review, myth-buster, contrarian |
| **Framework diagram** (`framework`) | The idea in one picture: flow, 2x2 matrix, layered stack, cycle, funnel or timeline | Code templates | explainer, how-to, tutorial |
| **The receipt** (`receipt`) | An oversized, crisp mock of the code, terminal output or prompt that proves the point | Claude SVG | hands-on, tutorial, tool review |

Choose a style per post (*Opening image* on the new-post form and in *Edit brief & settings*), or set a default per persona (*Default formula* card). **Auto** is the default: the panel picks across the styles that suit the post. Which ones suit it comes from the article type (chosen, or read from the brief) and the opener; `GET /api/opening-styles` returns the catalog and `suggested_by_type`, so the form can say "Pitches ideas across Cheat sheet and Framework diagram, plus open visual metaphors and data art". An optional note ("coins through a plinko board") goes to the room and the panel as the author's direction.

## How one is made

1. **Pitch** (`prompts/opening_ideas.md`, effort `effort_opening_ideas`, default high). Claude reads the post, its title and alternatives, the plan's hook, the formula, the humor dial and the author's note. On Auto it pitches six concepts across at least three styles, **at least two of them open visual metaphors and one data art**, so imaginative ideas always compete with the literal ones; a pitch that misses the mix is sent back once. With a style chosen it pitches four ideas in that style. Every concept has a hook (why someone clicks), what the picture shows, the real words it needs, and for data styles the factual claim and the numbers behind it. The room is told the styles of the author's last three openings, so posts don't all look alike.
2. **Panel** (`image_panel_opening`, [the seat panel](image-kit.md#the-judging-panel-imagespanelpy)). Independent seats on Haiku, Sonnet and Opus, all at once, so the pitcher never grades itself: two **scrollers** (would I click at 300px?), the **cold reader** (does it make sense in five seconds?), the **art director** (cohesive, appealing, one focal point, likeable characters), the **fact checker** (true, specific, sourceable) and the **author**. Code adds the votes; the cold reader, fact checker or author can rule a concept out (it stays on the board, ranked last). Every pitch also carries a `reader_takeaway` ("At a glance a reader sees ___ and understands ___"): a concept that cannot fill it in does not make sense as a picture.
3. **Research** (data styles only). The winning claim's numbers are looked up with web search (`opening_max_searches`, default 4).
4. **Build**. A fresh opener builds its **two best concepts at once**. A visual metaphor is a kit scene (`prompts/opening_build_scene.md`, `SceneSpec`, `scene.py`): a layout preset, a backdrop, up to three kit characters, kit props, at most one custom object Claude draws in its own box (linted and snapped to the scheme) and up to four fitted labels, all inside the crop band by construction. Data art and receipts are Claude SVG (`prompts/opening_build_svg.md`), linted (stray marks, dead references, text outside the band) and snapped to the scheme. Code-drawn styles get their words and data from Claude (`prompts/opening_build_template.md`, `OpeningBuild`) and are laid out by `templates.py` in the scheme. An opening meme goes to the meme room with the winning premise as its brief (see [Meme sandwich](#meme-sandwich)); at most one of the two candidates is a meme. A build that fails validation is retried once with the problems quoted. Colors: inferno, magma or viridis on white, gray or near-black, rotated against the author's recent images; a brand kit palette wins.
5. **Render panel** (`image_panel_render`, `image_panel_final`). Blind readers see only the pictures and say what each means (matched against its `reader_takeaway`), a craft seat looks for jank and an appeal seat for likeable characters, and Opus looks at both as **feed cards** (the thumbnail crop with the title under it) and picks one, optionally asking for one fix, which is rebuilt. Redraws and a picked pitch skip it. This needs an API connection: Claude Code (the subscription connection) cannot be shown an image, so it skips the panel and the image says so.
6. **Fallback**. A concept that cannot be built (no verifiable numbers, a drawing that fails twice) gives way to the next best one, up to three; the last resort is a visual metaphor of the post's idea. The card says which style was tried first.

Pitches and verdicts are stored on the image (`ProjectImage.spec`, `"room": "opening"`), so the Ideas board, Redraw and New idea never pitch or judge again until every idea has been used.

## Facts

A data opener prints only numbers it can stand behind (`facts.py`):

- Every number in the data, the big number and the words (headline, subhead, items, annotation) must appear in the research, a citation's quoted text or the post itself, allowing for rounding and forms like 1,234 / 1.2k / 12% / $3.4M. Years are dates, not claims.
- A waterfall's steps may be the difference between two found numbers; words never get that allowance.
- Every source URL must be one the research cited (or empty for "This post").
- The source line is printed on the image and added to the caption; the card links to the sources.

This guarantees no figure is invented. Whether a number means what the image says is for the fact-checker judge and the render review. If nothing verifiable is found, the next best idea is used: data openers are never "illustrative".

## Templates

Code-drawn styles share one 1600x900 canvas (`canvas.py`). Shapes are SVG written by code and rendered by resvg; every string is fitted to its box with Pillow in the bundled fonts (parallel texts share one size), so text is crisp and never overflows. Everything that matters stays inside the centre 1600x640 band, which every platform's thumbnail crop keeps. A brand kit palette of three or more colours recolours the templates (its darkest colour becomes the background when it is dark enough, otherwise the image is light).

| Style | Templates |
| --- | --- |
| Cheat sheet | `cheat_grid` (4-9 numbered tiles) |
| Versus split | `versus` (2-5 matched rows) |
| Big number | `big_number` |
| Framework diagram | `flow`, `matrix_2x2`, `stack`, `cycle`, `funnel`, `timeline` |
| Data story chart | `line_annotated`, `slope`, `dumbbell`, `waterfall`, `tornado`, `ranked_bar`, `heatmap`, `spider` |

Charts are drawn by code too (not Vega-Lite), so scales, labels and colours are consistent at thumbnail size: the leader or biggest mover is highlighted, end labels and callouts are placed clear of the lines, and axes close on a labelled tick.

## On the card

- **Ideas** opens the board: every pitch ranked as the panel scored it, with each judge's score and note. *Use this one* builds a stored pitch (`POST /api/images/{id}/redraw` with `opening_concept`), *Next best idea* moves to the best untried one, and *Try as…* pitches four new ideas in one style (`opening_style`).
- **Words** retypes a code-drawn opening's text (`PUT /api/images/{id}/opening-words`) with no call to Claude. Numbers and sources cannot be changed this way, and new words cannot add a number that was not researched.
- **Redraw** critiques the current image and builds the same idea again to fix its weakest point, with an experiment (colors, cast, staging or medium, as the style allows); **Remix** lets you choose the experiment; **Edit** changes it by instruction; **Replace** uploads your own. See *Redraw that improves* in `docs/images.md`.
- **Open with a meme…** on the Ideas board opens the post with a meme in any format from the meme bank (`POST /api/images/{id}/redraw` with `meme_format`): the meme room pitches five jokes in that format as an opener and draws the best, and the earlier pitches stay on the board.

Data art stays abstract in four places: the style's rules, the pitching prompt, a check on the pitch (`room.literal_objects` sends a data-art pitch that names coins, dice, people and the like back once), and the render review, which fails a data-art image that shows recognizable objects.

## Meme sandwich

Choosing **Opening meme** (or Auto picking one) opens the post with a meme as well as closing with one. The opening meme is pitched by the meme room as an opener: it sets up the tension, works for someone who has not read the post, and saves the payoff. The closing meme is made after it and is told about it, so it uses a different format family, never repeats the joke, and ideally pays it off as a bookend. Both memes keep the meme tools (Ideas, any format from the bank, Look, Words, Edit, Remix). Memes are rarely 16:9, so an opening meme's platform thumbnail is padded to keep the whole meme instead of cropped (`thumbnail_fit: contain`).

## Reviewing and tuning

`uv run python scripts/kit_sheet.py` renders every opener layout with kit characters (free). `uv run python evals/image_quality.py --yes` makes openers and memes for eight posts and lays them out as feed cards with panel verdicts and timings (costs money; `--demo` is free). `uv run python scripts/opening_gallery.py` renders every template with canned words (free) into `data/opening-gallery/index.html`, with the crop band marked; `--palette "#0b1d2a #38bdf8 #f472b6"` shows a brand palette. `--real --yes` pitches, judges and builds new openings for your latest posts and prints the panel's scores and the review (costs money; `--style` limits it to one style).

## Adding a style or template

- **A style:** add an `OpeningStyle` to `STYLES` in `styles.py` (`builder`: `scene`, `svg`, `template` or `meme`; `suits`; `templates`; `needs_data`; `thumbnail_fit`). An SVG style also needs its drawing rules in `SVG_RULES` in `room.py`. Add canned pitch words to `_DEMO_OPENING_CONCEPTS` in `demo.py`.
- **A template:** write a layout function in `templates.py` (or a chart in `charts.py`) that draws on a `Canvas` inside the body box, register a `Template` with its item, series and field limits, list it on its style, and add a canned build to `DEMO_OPENING_BUILDS` in `demo.py` (every number in `DEMO_OPENING_RESEARCH` for data templates). The tests render every template and check that its text stays in the crop-safe band.
