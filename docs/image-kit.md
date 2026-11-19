# The image kit, palettes and judging panel

Opening images and closing memes used to be freehand SVG that Claude drew from scratch every time. Freehand drawing
caused heads that floated off necks, characters that changed between panels, and famous memes nobody could
recognize. Prompting alone could not fix that, so the work is now split:

- **Claude is the art director.** It picks the concept, the joke, the words, who is cast, their expressions and
  poses, and the layout.
- **Code draws.** The characters, the famous meme stagings, the props and the layouts all come from a hand-built kit.
  Every character is whole, on-model and appealing every time.

Four pieces make this work:

| Piece | Where | What it does |
| --- | --- | --- |
| Character kit | `images/kit/` | Draws our own cast from named parts and exposes anchor points |
| Meme stagings | `images/memes/stagings.py` | Recreates each famous format's staging faithfully |
| Palettes | `images/palettes.py` | The only source of opener and meme colors |
| Judging panel | `images/panel.py` | Many small, independent judges on Haiku, Sonnet and Opus, all at once |

## The character kit (`images/kit/`)

- **Cast** (`rig.py`):
  - the Inferno Ghostwriter **ghost**, the house star
  - a round **dog**
  - a **cat**
  - stylized chibi **people**, four hairstyles and six skin tones, never anyone's likeness
  - a friendly **robot** with a screen face

  Each one is drawn by code from parts. Limbs are "rubber hose" strokes that start inside the body and end at the
  hand. Heads overlap their bodies. A detached head or a floating arm cannot happen.
- **Expressions** (`face.py`): about 20 named expressions, for example happy, beaming, smug, blank stare, hopeful,
  nervous, worried, shocked, panic, calm, thinking, mind-blown, deadpan, sad, nope and sweating. Each name is a fixed
  recipe of eyes, brows, mouth and extras such as blush, sweat drops, sparkles or rays. A "blank stare" is the same
  blank stare in every panel.
- **Poses**: stand, wave, point, arms up, shrug, hold, typing, facepalm, hand on chin, wipe brow, block, reach,
  present, hands on hips, sit, and others.
- **Accessories**: bowler, top hat, cap, glasses, scarf, tie, astronaut helmet, hood, puffer jacket, and more.
- **Hand props**: mug, phone, balloon, flag, cloth, and more.
- **Anchors**: `draw(...)` returns the character's SVG plus named anchor points (`head_top`, `mouth`, `hand_r`,
  `hand_l`, `seat`, `feet`). Scenes use them to aim speech bubbles and place props.
- **Looks** (`style.py`): each meme look changes the treatment, never the colors. The treatment covers outline
  weight, flat, soft or 3D shading, halftone dots, pale linework for blueprint, marker wobble for whiteboard, and a
  pixel grid for pixel arcade (applied to the rendered art, so the text stays crisp).
- **Props and backdrops** (`props.py`):
  - backdrops: meadow, burning room, space with a planet, city street, office, garden, basement
  - about 30 props: laptop, table, chart screen, server rack, flipchart, big red button, folding table and sign,
    butterfly, the expanding-brain heads, and more

Appeal is built into the drawing: big heads and eyes with two highlights, rounded silhouettes, soft blush, a gentle
gradient and one outline weight per look.

**Review the kit by eye** after any change:

```bash
uv run python scripts/kit_sheet.py
```

It writes `data/kit-sheet/index.html`, which has every character in every expression, pose and look, every prop and
every opener layout. It is free and makes no model calls.

**Add a character:** write a body function in `rig.py`. It returns a `_Body` with the head circle, face centre,
shoulders inside the body, arm length and hand style. Then add its colors to `style.coat` and its name to `KINDS`
and `KIND_HINTS`.

**Add an expression, pose or prop:** add it to the table in `face.py` (`EXPRESSIONS`), `rig.py` (`POSES`, `PROPS`,
`ACCESSORIES`) or `props.py` (`PROP_HINTS` plus a branch in `object_`). The prompts read these menus.

## Faithful meme stagings (`images/memes/stagings.py`)

Each famous format is staged by code, so what makes it recognizable is drawn the same way every time: the panels,
the camera framing, who stands where, and each beat's pose and expression. Claude only casts the roles (from
`ROLES`) and writes the words. A staged format has no art regions, so it costs no drawing call.

| Format | The staging |
| --- | --- |
| Right? Right? | 2x2 grid in a sunny meadow. Panel 1 is a two-shot. Panel 2 is a close-up of the hopeful one smiling. Panel 3 is a close-up of the blank stare. Panel 4 is a close-up of the frozen, sweating smile. |
| This is fine | Our dog in a bowler hat, sitting at a table with a mug in a burning room. There is also a two-panel version (wide shot, then close-up). |
| Expanding brain | The same head in profile in four rows. The brain grows brighter until it turns into rays and a galaxy. |
| Nope / Yep | A puffer jacket on yellow. The top row turns away with a hand up. The bottom row is a smug point. |
| Others | Pointing twins, distracted, two buttons, midwit curve, Gru's plan, always has been, change my mind, is this a, shocked strip, Panik / Kalm / Panik, running-away balloon, classic caption. |

Each staged format also carries:

- `signature`: the beats that must read. The review and the tests check these.
- `fit_tags`: the jokes the format serves. At humor 3 or more the writers' room must pitch at least two classics
  whose tags fit.

The **comic** formats are drawn from Claude's per-panel picks (`PanelPick`: backdrop, shot, one to three characters,
props), never from freehand art.

An **Edit** on a staged meme is a restage (`MemeStagingEdit`): Claude changes the words, the casting or the panels,
and the kit redraws the meme. Older memes with freehand art still edit the old way.

The cast is always our own designs. Real people and other creators' characters are never drawn; a format is
recognized by its staging.

## Palettes (`images/palettes.py`)

- A `Scheme` is one ramp (inferno, magma or viridis) on one surface (white, paper, light gray, slate, charcoal,
  near-black or inferno black).
- A new image's scheme rotates against the author's recent images (`choose`), so ramps and light and dark
  backgrounds take turns. A look can prefer a ramp (viridis lab) or a tone (blueprint is dark).
- A brand kit palette still wins, because it is the author's explicit choice.
- A remix palette tweak for an opener or a meme only offers the three house ramps (`HOUSE`).
- `snap_svg` and `snap_tree` move every color in model-drawn SVG to the nearest scheme color (data art, receipts, a
  scene's custom object). The palette is guaranteed, not just requested.
- The scheme is stored in the image's state as `scheme` (`"ramp:surface"`).

## SVG lint (`images/lint.py`)

Lint runs free checks on model-drawn SVG before any model looks at it:

- It removes shapes entirely off the canvas and lone tiny stray marks. Clusters of tiny marks, such as stars, are
  kept.
- It reports references to ids that do not exist, too many shapes, and text outside the crop band.
- It snaps colors to the scheme.

Problems go back to Claude through `draw_with_retry`, so a fix costs one retry instead of a review round.

## The judging panel (`images/panel.py`)

A panel is many small, independent judges, or **seats**, run at the same time with `asyncio.gather`. Each seat
answers one question on its own model and effort. Code adds up the votes as a weighted mean, and a veto rules a
candidate out. A seat that fails is dropped, and the panel stands while at least half of its seats answer.

Seats are set in `Settings` as `role:model:effort` strings, where the model is `opus`, `sonnet`, `haiku` or a model
id. Each role's question is a prompt file, `prompts/panel_<role>.md`.

| Panel | Default seats | Judges |
| --- | --- | --- |
| Meme pitches (`image_panel_meme`) | scroller (Haiku, low), scroller (Sonnet, low), gets it (Haiku, low, veto under 5), comedy editor (Sonnet, medium, may punch up the words), format fan (Sonnet, low), author (Opus, medium, veto under 4) | The pitched jokes, as text |
| Opener pitches (`image_panel_opening`) | scroller ×2, gets it, art director, fact checker (veto under 5), author | The pitched concepts, as text |
| Render (`image_panel_render`) | blind reader (Haiku, low), blind reader (Sonnet, low), craft (Sonnet, medium, veto under 4), appeal (Sonnet, low) | The drawn pictures |
| Final pick (`image_panel_final`) | Opus, medium | The finished candidates as feed cards, plus every seat's notes |

**The blind read.** The blind readers see only the pictures, with no title and no context, and write what each one
says. A Sonnet call then matches those readings against what the pitch meant: the meme's premise, or the opener's
`reader_takeaway`, written as "At a glance a reader sees ___ and understands ___". A picture that does not make
sense to a stranger loses, and a match under 4 rules it out.

**Two candidates.** A fresh opener or meme draws its two best pitches (`image_render_candidates`); kit and template
builds cost no drawing call. The render panel looks at both, and the final pick chooses one and may ask for one
concrete fix. The fix is applied by restaging (memes) or by rebuilding (openers).

Redraws, "New idea", and a pitch the author picked skip the panels, so they stay fast.

With the Claude Code subscription connection, pictures cannot be sent, so the render panel is skipped and the image
says so.

`LLM.structured(..., model=)` runs one call on another model: the API backend sends it, and Claude Code passes it as
`--model`. Haiku has no server-side refusal fallback, so a Haiku seat is sent without one.

## The author's taste (`images/taste.py`)

👍 and 👎 on an opening image or a closing meme (`PUT /api/images/{id}/rating`) are stored as `ProjectImage.rating`.
`taste_of` counts what the author liked and passed on: formats, looks, opening styles, casts and ramps. The meme
room hears it as a note and as look weights for the random look pick. The opening room hears it as a note.

## Evals

```bash
uv run python evals/image_quality.py --demo
uv run python evals/image_quality.py --yes
```

- `--demo` is a free wiring check.
- `--yes` makes real openers and memes for eight posts and costs money. The posts are the three bundled sample posts
  plus briefs on the blog's core topics.

Each run writes a contact sheet of feed cards and memes, with the render verdicts, blind readings, match scores,
pitch totals and seconds per image. It saves `results.json`, so two runs can be compared before and after a change.
