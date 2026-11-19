"""The meme format catalog: the layout, text slots and art regions of every meme Inferno Ghostwriter can make.

Code owns layout and typography; Claude owns the joke, the words and the art inside each region.
The prompt's format menu is rendered from this catalog, so the prompt and the composer never drift.
Famous formats are recreated as *formats* (layout, poses, colors) with our own ghost cast, never
real people's likenesses or someone else's characters.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

Box = tuple[int, int, int, int]  # x, y, width, height in canvas pixels

FAMILIES = {
    "classic": "Famous meme formats, recast with our ghosts",
    "chart": "Chart jokes drawn with real chart machinery",
    "comic": "Short comic strips",
    "artifact": "Fake artifacts: chat, terminal, labels, charts of types",
    "caption": "Classic top/bottom caption meme",
}

CAST = (
    "The star is the Inferno Ghostwriter ghost: a small, friendly spectral blogger (never an evil ghost) with a soft, rounded teardrop "
    "body that fades into flowing wisps, two big glowing oval eyes and an expressive face, and wispy hands that can hold things or type. "
    "Its colors and rendering follow this meme's look. Supporting cast: other ghosts in different colors, or simple stylized people "
    "(dot eyes, no real likenesses, no logos)."
)


@dataclass(frozen=True)
class TextSlot:
    name: str
    box: Box
    max_chars: int
    style: str
    hint: str
    align: str = "center"
    valign: str = "center"
    optional: bool = False
    bubble: bool = False
    fill: str | None = None


@dataclass(frozen=True)
class ArtRegion:
    name: str
    box: Box
    brief: str
    # Opaque regions paint their own full background; transparent ones are drawn over a scene the code paints.
    opaque: bool = True


@dataclass(frozen=True)
class MemeFormat:
    id: str
    name: str
    family: str
    when_to_use: str
    recognizable: str
    size: tuple[int, int]
    slots: tuple[TextSlot, ...]
    regions: tuple[ArtRegion, ...] = ()
    data: str = ""
    background: str = "#ffffff"
    # Slots in one group share a font size, so parallel text (rows, cells, panels) looks even.
    groups: tuple[tuple[str, ...], ...] = ()
    # What must read for the format to be recognized (the review and the tests check these beats).
    signature: tuple[str, ...] = ()
    # The kinds of joke it serves, so the room pitches the classic that fits.
    fit_tags: tuple[str, ...] = ()
    # Drawn by code from the kit (images/memes/stagings.py): no art regions, no drawing call.
    staged: bool = False

    def slot(self, name: str) -> TextSlot | None:
        return next((s for s in self.slots if s.name == name), None)


def _panels(width: int, height: int, cols: int, rows: int, gutter: int) -> list[Box]:
    w = (width - gutter * (cols + 1)) // cols
    h = (height - gutter * (rows + 1)) // rows
    return [(gutter + c * (w + gutter), gutter + r * (h + gutter), w, h) for r in range(rows) for c in range(cols)]


def _comic(fid: str, name: str, width: int, height: int, cols: int, rows: int, max_chars: int) -> MemeFormat:
    panels = _panels(width, height, cols, rows, 18)
    n = len(panels)
    return MemeFormat(
        id=fid,
        name=name,
        family="comic",
        when_to_use=(
            f"A {n}-beat gag: setup with real jargon from the post, a literal-minded or punny misreading, then a deadpan punchline "
            "(e.g. 'single source of truth' -> 'single source of FOODS?' -> 'it's a bachelor, it will always be single')."
        ),
        recognizable=f"{n} bordered panels read left to right, one speech bubble each, the same characters in every panel.",
        size=(width, height),
        background="#1b0c41",
        groups=(tuple(f"p{i + 1}" for i in range(n)),),
        slots=tuple(
            TextSlot(
                f"p{i + 1}",
                (x + 16, y + 14, w - 32, int(h * 0.36)),
                max_chars,
                "bubble",
                "The line spoken in this panel (set speaker to the side the speaking character stands on)."
                + (" The punchline." if i == n - 1 else ""),
                bubble=True,
            )
            for i, (x, y, w, h) in enumerate(panels)
        ),
        regions=tuple(
            ArtRegion(
                f"p{i + 1}",
                box,
                "A full comic panel scene with a flat or gradient background. Keep the top 40% of the panel quiet (plain wall or sky) "
                "because the speech bubble goes there. Characters stand in the lower 60%, big and expressive, reused from cast_defs so "
                "they look identical in every panel.",
            )
            for i, box in enumerate(panels)
        ),
    )


def _retold(
    base: MemeFormat,
    name: str,
    when: str,
    recognizable: str,
    hints: tuple[str, ...],
    briefs: tuple[str, ...],
    optional: tuple[str, ...] = (),
) -> MemeFormat:
    """A comic layout re-cast as a famous multi-panel format: same frames and bubbles, its own roles and staging."""
    return replace(
        base,
        name=name,
        family="classic",
        when_to_use=when,
        recognizable=recognizable,
        slots=tuple(replace(sl, hint=hints[i], optional=sl.name in optional) for i, sl in enumerate(base.slots)),
        regions=tuple(replace(r, brief=briefs[i]) for i, r in enumerate(base.regions)),
    )


_QUIET_TOP = (
    " Keep the top 40% of the panel quiet (plain wall or sky) because the speech bubble goes there; the ghosts stand in the lower 60%."
)


def _grid4(fid: str, name: str, family: str, when: str, recognizable: str, brief: str, hints: tuple[str, ...]) -> MemeFormat:
    """Gru's-plan style 2x2 grid: art on the left of each panel, a whiteboard the code draws on the right."""
    panels = _panels(1200, 900, 2, 2, 12)
    return MemeFormat(
        id=fid,
        name=name,
        family=family,
        when_to_use=when,
        recognizable=recognizable,
        size=(1200, 900),
        background="#1b0c41",
        groups=(("step1", "step2", "step3", "step4"),),
        slots=tuple(TextSlot(f"step{i + 1}", (x + 318, y + 62, 232, 286), 55, "dark", hints[i]) for i, (x, y, _w, _h) in enumerate(panels)),
        regions=tuple(
            ArtRegion(
                f"p{i + 1}",
                (x, y, 300, h),
                brief if i < 3 else "The same character turned toward the board doing a shocked double-take: wide eyes, mouth open.",
                opaque=False,
            )
            for i, (x, y, _w, h) in enumerate(panels)
        ),
    )


FORMATS: tuple[MemeFormat, ...] = (
    MemeFormat(
        id="nope_yep",
        name="Nope / Yep (the Drake format)",
        family="classic",
        when_to_use="Rejecting the obvious or popular option and smugly preferring the clever, lazy or ironic one.",
        recognizable=(
            "Two rows. Left column: the character in an orange puffer jacket on a yellow background, recoiling with a hand up (top), "
            "then smiling and pointing (bottom). Right column: plain white with black text."
        ),
        size=(1080, 1080),
        groups=(("nope", "yep"),),
        slots=(
            TextSlot("nope", (560, 20, 500, 500), 70, "dark", "The thing being rejected."),
            TextSlot("yep", (560, 560, 500, 500), 70, "dark", "The thing being embraced (the punchline)."),
        ),
        regions=(
            ArtRegion(
                "nope",
                (0, 0, 540, 540),
                "Warm yellow background. The ghost in an orange puffer jacket, body facing right but head turned away to the left in "
                "disgust, eyes shut, one mitten hand raised palm-out toward the right as if blocking something.",
            ),
            ArtRegion(
                "yep",
                (0, 540, 540, 540),
                "Same yellow background and jacket. The ghost now faces right with a smug, delighted smile, one finger pointing "
                "approvingly to the right.",
            ),
        ),
    ),
    MemeFormat(
        id="pointing_twins",
        name="Pointing twins (two identical figures accusing each other)",
        family="classic",
        when_to_use="Two things that claim to be different are actually the same (dev vs prod, two dashboards, two 'sources of truth').",
        recognizable="Two identical characters in identical outfits pointing at each other in a dim basement, mirrored poses.",
        size=(1200, 800),
        groups=(("left", "right"),),
        slots=(
            TextSlot("left", (40, 40, 520, 170), 40, "outline", "Label for the left twin."),
            TextSlot("right", (640, 40, 520, 170), 40, "outline", "Label for the right twin."),
            TextSlot("bottom", (100, 650, 1000, 130), 60, "outline", "Optional caption across the bottom.", optional=True),
        ),
        regions=(
            ArtRegion(
                "scene",
                (0, 0, 1200, 800),
                "Dim basement or warehouse with crates and a single hanging light. Two IDENTICAL copies of the ghost (same scarf and "
                "hat pattern, define it once in cast_defs and <use> it twice, mirroring the second with a transform) stand on the "
                "left and right thirds, facing each other, each with one arm fully outstretched pointing at the other. Keep the top "
                "28% and bottom 18% free of detail for labels.",
            ),
        ),
    ),
    MemeFormat(
        id="distracted",
        name="Distracted ghost (the distracted boyfriend format)",
        family="classic",
        when_to_use="Someone committed to the sensible thing gets distracted by the shiny new thing.",
        recognizable=(
            "Street scene: the middle character walks with a partner (right) but turns to stare at a passer-by (left); "
            "the partner glares in disbelief. Labels sit on each figure."
        ),
        size=(1200, 800),
        groups=(("left", "center", "right"),),
        slots=(
            TextSlot("left", (40, 500, 380, 170), 32, "outline", "The shiny new thing (the passer-by)."),
            TextSlot("center", (420, 560, 360, 170), 32, "outline", "The distracted one (you, the team, the industry)."),
            TextSlot("right", (800, 500, 360, 170), 32, "outline", "The sensible thing they should stay committed to."),
        ),
        regions=(
            ArtRegion(
                "scene",
                (0, 0, 1200, 800),
                "Sunny city street, soft blurred buildings. Left third: an eye-catching, glamorous ghost walking away to the left, "
                "glancing back. Center: the ghost walking right but twisting around to stare at the left ghost, mouth open, eyebrows "
                "up. Right third: the ghost's partner ghost, holding its arm, glaring at it in outrage. Keep the torso area of each "
                "figure (y 500-700) simple and low-contrast for labels.",
            ),
        ),
    ),
    MemeFormat(
        id="expanding_brain",
        name="Expanding brain",
        family="classic",
        when_to_use="Four levels of rising 'sophistication' where the last level is absurd or circles back to something silly.",
        recognizable="Four rows: text on the left, a brain on the right that glows brighter each row until it is cosmic.",
        size=(1080, 1320),
        groups=(("level1", "level2", "level3", "level4"),),
        slots=tuple(
            TextSlot(f"level{i + 1}", (24, i * 330 + 20, 500, 290), 60, "dark", hint)
            for i, hint in enumerate(
                (
                    "The basic approach.",
                    "A smarter approach.",
                    "An over-engineered approach.",
                    "The galaxy-brain punchline (absurd, or ironically simple).",
                )
            )
        ),
        regions=tuple(
            ArtRegion(
                f"brain{i + 1}",
                (540, i * 330, 540, 330),
                brief,
            )
            for i, brief in enumerate(
                (
                    "Dark background. A head silhouette in profile with a small, dim pink brain.",
                    "Dark blue background. A head silhouette with a brighter, slightly glowing brain.",
                    "Deep purple background. A head silhouette whose brain glows bright with light rays bursting out.",
                    "A cosmic scene: the whole head radiates blinding white-gold light and galaxy swirls; the brain is pure energy.",
                )
            )
        ),
    ),
    MemeFormat(
        id="this_is_fine",
        name="This is fine",
        family="classic",
        when_to_use="Calmly ignoring a disaster that is obviously happening (tech debt, broken pipelines, drifting models).",
        recognizable="The character sits at a small table with a coffee mug in a room full of flames, smiling: 'This is fine.'",
        size=(1200, 760),
        slots=(
            TextSlot("bubble", (40, 40, 520, 200), 40, "bubble", "What the character says (classic: 'This is fine.').", bubble=True),
            TextSlot("fire", (40, 560, 520, 160), 36, "outline", "Label on the flames: what is burning."),
            TextSlot(
                "character", (700, 600, 460, 130), 30, "outline", "Optional label on the character: who is ignoring it.", optional=True
            ),
        ),
        regions=(
            ArtRegion(
                "scene",
                (0, 0, 1200, 760),
                "A cozy room engulfed in stylized orange-yellow flames along the floor and walls, dark smoke under the ceiling. "
                "The ghost sits on the right half at a small wooden table with a coffee mug, a calm, slightly forced smile and "
                "half-closed eyes, a tiny hat optional. Keep the upper-left quarter as smoke only for the speech bubble.",
            ),
        ),
    ),
    MemeFormat(
        id="two_buttons",
        name="Two buttons",
        family="classic",
        when_to_use="An impossible choice between two options that are both tempting (or both bad).",
        recognizable="Top: a hand hovering between two big red buttons. Bottom: the character sweating, wiping its brow.",
        size=(1080, 1300),
        groups=(("left_button", "right_button"),),
        slots=(
            TextSlot("left_button", (130, 225, 340, 160), 32, "light", "Option on the left button."),
            TextSlot("right_button", (610, 195, 340, 160), 32, "light", "Option on the right button."),
            TextSlot("character", (40, 1160, 1000, 120), 36, "outline", "Label for the sweating character.", optional=True),
        ),
        regions=(
            ArtRegion(
                "hand",
                (0, 0, 1080, 700),
                "A grey-blue control panel surface filling the region. Two big red buttons are drawn on top automatically, centered "
                "at (300, 315) and (780, 285), each about 380x240: leave those areas plain. Draw one ghost hand reaching up from "
                "the bottom edge, its fingertip hovering hesitantly between the buttons near (540, 470), with a few sweat drops.",
            ),
            ArtRegion(
                "sweat",
                (0, 700, 1080, 600),
                "Close-up of the ghost sweating heavily, eyes wide in panic, wiping its forehead with a cloth, plain warm background. "
                "Keep the bottom 20% plain for a label.",
            ),
        ),
    ),
    MemeFormat(
        id="midwit_bell_curve",
        name="Midwit bell curve",
        family="classic",
        when_to_use="The beginner and the true expert both say the same simple thing; the middle of the curve overthinks it.",
        recognizable=(
            "A bell curve of 'expertise' with three characters: simple left tail, anxious overthinker at the peak, serene right tail."
        ),
        size=(1400, 900),
        data="The bell curve, axis and percentages are drawn automatically.",
        groups=(("left_says", "right_says"),),
        slots=(
            TextSlot("left_says", (40, 140, 360, 230), 40, "bubble", "The beginner's simple take.", bubble=True),
            TextSlot("middle_says", (440, 18, 520, 230), 110, "bubble", "The middle's anxious, over-engineered paragraph.", bubble=True),
            TextSlot(
                "right_says", (1000, 140, 360, 230), 40, "bubble", "The expert's take: the same simple thing as the left.", bubble=True
            ),
        ),
        regions=(
            ArtRegion("left", (60, 440, 280, 300), "A simple, happy, slightly goofy ghost smiling with its tongue out.", opaque=False),
            ArtRegion(
                "middle",
                (540, 280, 320, 300),
                "The ghost crying and sweating, steam wisps curling off its head, glasses askew, a halo of sticky notes orbiting it.",
                opaque=False,
            ),
            ArtRegion(
                "right", (1060, 440, 280, 300), "A serene ghost in a dark hooded cloak, eyes calmly closed, glowing faintly.", opaque=False
            ),
        ),
    ),
    _grid4(
        "gru_plan",
        "The four-step plan (Gru's plan format)",
        "classic",
        "A confident plan whose third step hides the fatal flaw, discovered in step four.",
        "A 2x2 grid: the presenter points at a flipchart with steps 1-3; "
        "in panel 4 the board repeats step 3 and the presenter does a double-take.",
        "The ghost stands on the left, confidently pointing at the flipchart on its right, chest out.",
        (
            "Step one: sensible.",
            "Step two: sensible.",
            "Step three: the hidden flaw.",
            "Step four: repeat step three word for word.",
        ),
    ),
    MemeFormat(
        id="joke_pie_3d",
        name="Terrible 3D exploded pie chart",
        family="chart",
        when_to_use="A deadpan breakdown where the biggest slice is the punchline (e.g. zombie apocalypse: 80% 'yummy food').",
        recognizable="A shiny, tilted, exploded 3D pie with a legend, the kind of chart every data person loves to hate.",
        size=(1200, 900),
        background="#fffaf0",
        data="3-6 slices: label = slice name, value = percent (they are normalized to 100). The largest slice is the punchline.",
        slots=(
            TextSlot("title", (40, 26, 1120, 110), 70, "title", "A deadpan chart title."),
            TextSlot(
                "footnote", (40, 822, 1120, 60), 70, "ui", "Optional fake source line, e.g. 'Source: vibes'.", align="left", optional=True
            ),
        ),
    ),
    MemeFormat(
        id="spurious_correlation",
        name="Spurious correlation chart",
        family="chart",
        when_to_use="Two unrelated trends that track each other perfectly; a correlation-vs-causation joke tied to the post.",
        recognizable="A dual-axis line chart in a serious style with two absurdly matched series and a deadpan 'r = 0.98'.",
        size=(1800, 1000),
        data="Two series named exactly 'a' and 'b', 6-10 points each; label = the shared x value (e.g. a year), value = y.",
        slots=(
            TextSlot("title", (0, 0, 0, 0), 80, "title", "Deadpan title linking the two series."),
            TextSlot("series_a", (0, 0, 0, 0), 40, "ui", "Name of series a, with units."),
            TextSlot("series_b", (0, 0, 0, 0), 40, "ui", "Name of series b, with units."),
            TextSlot("note", (0, 0, 0, 0), 60, "ui", "Deadpan subtitle, e.g. 'r = 0.98. Correlation: strong. Causation: none.'"),
        ),
    ),
    MemeFormat(
        id="venn",
        name="Venn diagram",
        family="chart",
        when_to_use="Two or three overlapping ideas whose intersection is the punchline.",
        recognizable="Translucent overlapping circles with labels and a tiny, devastating label in the middle.",
        size=(1200, 1000),
        background="#fffaf0",
        data="Leave 'c' empty for a two-circle Venn.",
        groups=(("a", "b", "c"),),
        slots=(
            TextSlot("title", (40, 20, 1120, 100), 60, "title", "Optional title.", optional=True),
            TextSlot("a", (200, 280, 300, 150), 28, "outline", "Circle A."),
            TextSlot("b", (700, 280, 300, 150), 28, "outline", "Circle B."),
            TextSlot("c", (450, 720, 300, 150), 28, "outline", "Circle C (optional).", optional=True),
            TextSlot("center", (510, 470, 180, 120), 26, "outline", "The intersection: the punchline."),
        ),
    ),
    _comic("comic_strip_3", "Three-panel comic strip", 1500, 560, 3, 1, 80),
    _comic("comic_grid_4", "Four-panel comic (2x2)", 1080, 1080, 2, 2, 80),
    MemeFormat(
        id="chat_thread",
        name="Team chat thread",
        family="artifact",
        when_to_use="A painfully relatable exchange at work; the last message is the punchline.",
        recognizable="A generic team-chat window: channel name, avatars with initials, names, timestamps, messages.",
        size=(1080, 1080),
        groups=(("m1", "m2", "m3", "m4"), ("m1_name", "m2_name", "m3_name", "m4_name")),
        slots=(
            TextSlot("channel", (90, 30, 700, 60), 30, "light", "Channel name without '#', e.g. 'data-eng'.", align="left"),
            *(
                slot
                for i in range(4)
                for slot in (
                    TextSlot(f"m{i + 1}_name", (150, 150 + i * 225, 520, 44), 24, "ui_bold", f"Who sent message {i + 1}.", align="left"),
                    TextSlot(
                        f"m{i + 1}",
                        (150, 198 + i * 225, 880, 150),
                        140,
                        "ui",
                        "The punchline message." if i == 3 else f"Message {i + 1}.",
                        align="left",
                        valign="top",
                    ),
                )
            ),
        ),
    ),
    MemeFormat(
        id="terminal",
        name="Terminal session",
        family="artifact",
        when_to_use="A command and its brutally honest output; great for agents, pipelines, deploys, tests and training runs.",
        recognizable="A dark terminal window with traffic-light dots, '$' prompts and monospaced output.",
        size=(1200, 800),
        background="#120a24",
        groups=(("cmd1", "cmd2", "cmd3", "out1", "out2", "out3"),),
        slots=(
            TextSlot("title", (300, 18, 600, 40), 40, "ui", "Window title, e.g. 'zsh - prod'.", fill="#c9b8e8"),
            TextSlot("cmd1", (100, 92, 1060, 56), 70, "mono", "First command (without '$').", align="left"),
            TextSlot("out1", (60, 152, 1100, 140), 160, "mono", "Its output.", align="left", valign="top", fill="#e7def5"),
            TextSlot("cmd2", (100, 302, 1060, 56), 70, "mono", "Second command.", align="left"),
            TextSlot("out2", (60, 362, 1100, 140), 160, "mono", "Its output.", align="left", valign="top", fill="#e7def5"),
            TextSlot("cmd3", (100, 512, 1060, 56), 70, "mono", "Third command (optional).", align="left", optional=True),
            TextSlot("out3", (60, 572, 1100, 190), 200, "mono", "The punchline output.", align="left", valign="top", fill="#fb9b06"),
        ),
    ),
    MemeFormat(
        id="nutrition_label",
        name="Nutrition Facts label",
        family="artifact",
        when_to_use="Dissecting a tool, model, meeting or practice into its true 'ingredients'.",
        recognizable="A black-and-white Nutrition Facts panel with heavy rules, Calories, and % Daily Value rows.",
        size=(900, 1200),
        groups=(tuple(f"r{i}_name" for i in range(1, 7)) + tuple(f"r{i}_value" for i in range(1, 7)),),
        slots=(
            TextSlot("product", (70, 170, 760, 56), 40, "ui_bold", "What is being labeled, e.g. 'Per 1 AI Agent'.", align="left"),
            TextSlot("serving", (70, 232, 760, 50), 50, "ui", "Serving size line, e.g. 'Serving size: 1 hallucination'.", align="left"),
            TextSlot(
                "calories", (560, 316, 270, 100), 8, "title", "The Calories number (can be a joke like '∞').", align="right", fill="#000000"
            ),
            *(
                slot
                for i in range(6)
                for slot in (
                    TextSlot(f"r{i + 1}_name", (70, 480 + i * 78, 560, 64), 34, "ui_bold", f"Ingredient {i + 1}.", align="left"),
                    TextSlot(
                        f"r{i + 1}_value", (640, 480 + i * 78, 190, 64), 8, "ui_bold", "Its % Daily Value, e.g. '340%'.", align="right"
                    ),
                )
            ),
            TextSlot(
                "footnote",
                (70, 965, 760, 175),
                170,
                "ui",
                "The '* Percent Daily Values...' footnote, the last laugh.",
                align="left",
                valign="top",
            ),
        ),
    ),
    MemeFormat(
        id="alignment_chart",
        name="Alignment chart (lawful good to chaotic evil)",
        family="artifact",
        when_to_use="Classifying nine behaviors or practices around the post's topic, from by-the-book to unhinged.",
        recognizable="A 3x3 grid labeled Lawful/Neutral/Chaotic by Good/Neutral/Evil, one short entry per cell.",
        size=(1200, 1200),
        background="#1b0c41",
        groups=(("lg", "ng", "cg", "ln", "tn", "cn", "le", "ne", "ce"),),
        slots=(
            TextSlot("title", (40, 20, 1120, 90), 50, "light", "The chart's subject, e.g. 'Data science alignment chart'."),
            *(
                TextSlot(
                    code,
                    (24 + c * 388 + 16, 130 + r * 352 + 80, 340, 250),
                    60,
                    "dark",
                    f"{label} entry.",
                )
                for r, row in enumerate((("lg", "ng", "cg"), ("ln", "tn", "cn"), ("le", "ne", "ce")))
                for c, code in enumerate(row)
                for label in (
                    {
                        "lg": "Lawful good",
                        "ng": "Neutral good",
                        "cg": "Chaotic good",
                        "ln": "Lawful neutral",
                        "tn": "True neutral",
                        "cn": "Chaotic neutral",
                        "le": "Lawful evil",
                        "ne": "Neutral evil",
                        "ce": "Chaotic evil",
                    }[code],
                )
            ),
        ),
    ),
    _retold(
        _comic("right_right", "", 1080, 1080, 2, 2, 60),
        "Right? Right? (the 'For the better, right?' format)",
        "A grand, optimistic claim about data, a model, a tool or a plan ('this dataset answers everything'), where the hopeful "
        "listener's growing doubt is the joke. A classic for over-promised data sources, silver-bullet tools and 'it will scale' claims.",
        "Four panels (2x2) of two ghosts in a sunlit meadow: a confident ghost makes a claim; the other smiles hopefully and asks for "
        "reassurance; the confident ghost just stares blankly; the hopeful ghost's smile fades into a nervous 'Right?'.",
        (
            "The confident ghost's grand claim, with real jargon from the post (e.g. 'We can use this dataset to answer everything').",
            "The hopeful ghost's smiling reply that seeks reassurance (e.g. 'For the better, right?').",
            "Optional: a silent beat. Leave blank for the classic, or one flat word such as '...'.",
            "The hopeful ghost again, now nervous, a single word or phrase: 'Right?' (or a sharper twist on it).",
        ),
        (
            "Sunlit green meadow with a pale sky. Two ghosts side by side, the confident one on the left facing right with a calm, "
            "faintly smug smile and eyes front, the hopeful one on the right turned toward it, beaming with big hopeful eyes." + _QUIET_TOP,
            "Same meadow. Close-up on the hopeful ghost on the right, bright eyes, a warm, trusting smile, tilting toward the left."
            + _QUIET_TOP,
            "Same meadow. Close-up on the confident ghost on the left: totally blank, expressionless stare straight ahead, a tiny "
            "wisp of wind blowing past, as if it did not hear the question." + _QUIET_TOP,
            "Same meadow. Close-up on the hopeful ghost: the smile has frozen and tightened, eyes wide and slightly watery, a bead of "
            "sweat, looking pleadingly at the other." + _QUIET_TOP,
        ),
        optional=("p3",),
    ),
    MemeFormat(
        id="always_has_been",
        name="Always has been (two ghosts in space)",
        family="classic",
        when_to_use="A sudden realization that everything is secretly one thing ('wait, it's all just correlations?').",
        recognizable="Deep space: a shocked ghost gazes at a planet; a calmer ghost floats behind it: Wait, it's all X? Always has been.",
        size=(1200, 700),
        groups=(("question", "answer"),),
        slots=(
            TextSlot("planet", (70, 420, 440, 170), 40, "outline", "The planet's label: the thing the post says everything reduces to."),
            TextSlot("question", (520, 24, 640, 170), 60, "bubble", "The shocked ghost: 'Wait, it's all ...?'", bubble=True),
            TextSlot("answer", (700, 260, 460, 150), 40, "bubble", "The calm ghost: 'Always has been.' (or a sharper twist).", bubble=True),
        ),
        regions=(
            ArtRegion(
                "scene",
                (0, 0, 1200, 700),
                "Deep space with stars and a soft nebula. A big planet fills the bottom-left corner (keep its middle, x 70-510 and "
                "y 420-590, plain and calm for a label). On the right, in the lower half, two ghosts float: the front one turned left "
                "toward the planet with huge shocked eyes and an open mouth; the second ghost floats just behind it, facing the same "
                "way with a serene, knowing half-smile. Keep the top-right free for two speech bubbles.",
            ),
        ),
    ),
    MemeFormat(
        id="change_my_mind",
        name="Change my mind (the table and the sign)",
        family="classic",
        when_to_use="A confident, slightly provocative opinion a practitioner would defend at a table (a hot take about the post's topic).",
        recognizable="A ghost sits calmly at a small table with a mug and a big sign on the front reading a hot take.",
        size=(1200, 800),
        slots=(
            TextSlot("sign", (360, 490, 500, 190), 80, "dark", "The hot take written on the sign."),
            TextSlot("caption", (40, 700, 1120, 80), 30, "outline", "Optional line under the table, e.g. 'Change my mind.'", optional=True),
        ),
        regions=(
            ArtRegion(
                "scene",
                (0, 0, 1200, 800),
                "A sunny campus lawn with soft trees. A small folding table in the middle holds a steaming mug; the ghost sits "
                "behind it, relaxed and serene, one wisp hand around the mug. A big blank WHITE sign board hangs on the front of the "
                "table, facing the viewer, covering x 340-880 and y 470-690: leave it perfectly plain and white for the text. Keep "
                "the top 14% and the bottom 10% quiet.",
            ),
        ),
    ),
    _retold(
        _comic("shocked_strip", "", 1500, 560, 3, 1, 70),
        "Shocked ghost strip (the 'surprised face' format)",
        "A predictable consequence of an obvious decision, followed by a shocked reaction ('we skipped the tests' ... 'bugs in prod?!').",
        "Three panels: the setup (what the team did), the obvious consequence, then a close-up of a ghost frozen in wide-eyed surprise.",
        (
            "The setup: the choice that was made, in real jargon from the post.",
            "The predictable consequence, stated flatly.",
            "Optional: the shocked ghost's one-word reaction. Leave blank for the classic silent stare.",
        ),
        (
            "A plain office or desk scene; a ghost proudly making the questionable choice, with a thumbs-up." + _QUIET_TOP,
            "The same scene going quietly wrong: warning lights, a stack of alerts, the ghost not noticing." + _QUIET_TOP,
            "Extreme close-up of the ghost against a flat pastel color: jaw dropped, eyes enormous and round, a shocked gasp." + _QUIET_TOP,
        ),
        optional=("p3",),
    ),
    MemeFormat(
        id="is_this_a",
        name="Is this a...? (the misidentification format)",
        family="classic",
        when_to_use="Someone confidently mislabels something (a vanity metric as insight, a chatbot as an agent).",
        recognizable="A ghost gestures at a glowing butterfly-like thing, with a label on each and a bottom caption asking 'Is this ...?'.",
        size=(1200, 800),
        groups=(("person", "thing"),),
        slots=(
            TextSlot("person", (60, 380, 380, 160), 36, "outline", "Label on the ghost: who is misjudging (the team, the exec, me)."),
            TextSlot("thing", (760, 120, 380, 150), 36, "outline", "Label on the glowing thing: what it actually is."),
            TextSlot("question", (40, 640, 1120, 130), 60, "impact", "The bottom caption: 'Is this ...?' naming the wrong thing."),
        ),
        regions=(
            ArtRegion(
                "scene",
                (0, 0, 1200, 800),
                "A soft garden at dusk. On the left, the ghost stands in a relaxed pose with a wisp hand lifted toward the right, "
                "head tilted in innocent curiosity. On the right a glowing, butterfly-like creature hovers over a flower. Keep the "
                "ghost's body (x 60-440, y 380-540) and the area above the creature (x 760-1140, y 120-270) plain for labels, and the "
                "bottom 22% quiet.",
            ),
        ),
    ),
    MemeFormat(
        id="classic_caption",
        name="Classic caption meme",
        family="caption",
        when_to_use="A reaction image with bold top/bottom captions; good for a single sharp observation.",
        recognizable="One expressive scene with white, black-outlined uppercase captions at the top and bottom.",
        size=(1080, 1080),
        slots=(
            TextSlot("top", (30, 20, 1020, 190), 60, "impact", "Top caption: the setup.", optional=True),
            TextSlot("bottom", (30, 830, 1020, 230), 70, "impact", "Bottom caption: the punchline."),
        ),
        regions=(
            ArtRegion(
                "scene",
                (0, 0, 1080, 1080),
                "One expressive cartoon scene (the ghost or an object reacting) that sets up the joke. Keep the top 18% and bottom 22% "
                "visually quiet (plain background) because the captions go there. No words in the art.",
            ),
        ),
    ),
)

_STAGED: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    # id: (what it looks like, signature beats, fit tags)
    "right_right": (
        "Four panels (2x2) in a sunlit meadow: a two-shot of a confident character (left) and a beaming hopeful one (right); "
        "a close-up of the hopeful one smiling; a close-up of the confident one's blank stare; a close-up of the hopeful one, "
        "smile frozen, sweating.",
        ("2x2 grid", "panel 1 two-shot in a meadow", "panel 3 blank stare", "panel 4 frozen nervous smile"),
        ("over-promise", "silver bullet", "naive optimism", "it will scale"),
    ),
    "this_is_fine": (
        "Our cartoon dog in a little bowler hat sits at a small table with a coffee mug in a room engulfed in flames, "
        "smiling contentedly: 'This is fine.'",
        ("dog in a hat at a table", "coffee mug", "room on fire", "content smile"),
        ("denial", "ironic calm", "tech debt", "everything is broken"),
    ),
    "expanding_brain": (
        "Four rows: text on the left; on the right the same head in profile, its brain glowing brighter each row until it "
        "is cosmic (rays, then a galaxy).",
        ("four rows", "same head each row", "brain brightens", "galaxy at the bottom"),
        ("escalation", "over-engineering", "galaxy brain", "ironic simplicity"),
    ),
    "nope_yep": (
        "Two rows on yellow: the character in an orange puffer jacket turns away with a hand up (top), then smiles smugly "
        "and points at the text (bottom). Right column: plain white with black text.",
        ("puffer jacket on yellow", "top: turned away, hand up", "bottom: smug point"),
        ("preference", "lazy option", "ironic choice"),
    ),
    "pointing_twins": (
        "Two identical characters in matching scarves point at each other in a dim basement under one hanging light.",
        ("identical twins", "pointing at each other", "basement light"),
        ("same thing", "duplicates", "blame"),
    ),
    "distracted": (
        "A city street: the middle character turns to stare, starry-eyed, at a passer-by in sunglasses (left) while its "
        "partner glares (right).",
        ("three figures", "middle one turns to look", "partner glares"),
        ("shiny object", "temptation", "new tool"),
    ),
    "two_buttons": (
        "Top: a hand hovers between two big red buttons on a control panel. Bottom: close-up of the character sweating, "
        "wiping its brow with a cloth.",
        ("two red buttons", "hovering hand", "sweating close-up"),
        ("dilemma", "false choice", "both bad"),
    ),
    "midwit_bell_curve": (
        "A bell curve of 'expertise': a goofy beaming character on the left tail, a panicking overthinker with glasses at the "
        "peak, and a serene hooded expert on the right tail.",
        ("bell curve", "goofy left", "panicking middle", "hooded calm right"),
        ("overthinking", "simple is best", "beginner and expert agree"),
    ),
    "gru_plan": (
        "A 2x2 grid: a character points proudly at a flipchart with steps 1-3; in panel 4 the board repeats step 3 and it "
        "stares at it in shock.",
        ("flipchart", "four steps", "double-take in panel 4"),
        ("hidden flaw", "plan backfires"),
    ),
    "always_has_been": (
        "Deep space: two astronaut characters float by a big planet; the front one stares at it in shock, the one behind "
        "points calmly: 'Always has been.'",
        ("space and planet", "two astronauts", "shocked front, calm behind"),
        ("realization", "it was always X"),
    ),
    "change_my_mind": (
        "A sunny lawn: a smug character sits behind a folding table with a mug and a big white sign reading a hot take.",
        ("folding table", "white sign", "mug", "smug sitter"),
        ("hot take", "unpopular opinion"),
    ),
    "is_this_a": (
        "A garden at dusk: a character in glasses gestures hopefully at a glowing butterfly; labels on both and a bottom "
        "caption 'Is this a ...?'.",
        ("gesturing character", "glowing butterfly", "'Is this...?' caption"),
        ("misidentification", "hype", "mislabeling"),
    ),
    "shocked_strip": (
        "Three panels: the character proudly makes a choice in an office; works on happily while a chart crashes and a fire "
        "starts; a huge close-up of its shocked face.",
        ("proud choice", "consequence ignored", "shocked close-up"),
        ("predictable consequence", "surprised by the obvious"),
    ),
    "classic_caption": (
        "One character with a strong reaction, big and centered, with bold top and bottom captions.",
        ("one big reaction", "top and bottom captions"),
        ("single observation",),
    ),
}


def _restage(f: MemeFormat) -> MemeFormat:
    if f.id in _STAGED:
        looks, signature, tags = _STAGED[f.id]
        return replace(f, recognizable=looks, signature=signature, fit_tags=tags, regions=(), staged=True)
    if f.family == "comic":
        return replace(f, regions=(), staged=True)
    return f


FORMATS = (
    *(_restage(f) for f in FORMATS),
    MemeFormat(
        id="this_is_fine_2",
        name="This is fine (two panels)",
        family="classic",
        when_to_use="The two-panel version: a calm wide shot of the disaster, then a close-up where the character says it is fine.",
        recognizable="Two panels: our dog in a bowler hat with a mug at a table in a burning room, then a close-up: 'This is fine.'",
        size=(1400, 620),
        background="#1b0c41",
        slots=(
            TextSlot("fire", (40, 470, 620, 120), 36, "outline", "Label on the flames: what is burning.", optional=True),
            TextSlot("bubble", (740, 30, 620, 190), 40, "bubble", "What the dog says (classic: 'This is fine.').", bubble=True),
        ),
        signature=("wide shot then close-up", "dog in a hat", "room on fire"),
        fit_tags=("denial", "ironic calm", "everything is broken"),
        staged=True,
    ),
    MemeFormat(
        id="panik_kalm_panik",
        name="Panik / Kalm / Panik",
        family="classic",
        when_to_use="A worry, a reassuring fact, then a twist that brings the worry back worse.",
        recognizable="Three rows: text on the left; on the right the same character panicking, then calm, then panicking again.",
        size=(1080, 1080),
        groups=(("row1", "row2", "row3"),),
        slots=tuple(
            TextSlot(f"row{i + 1}", (24, i * 360 + 20, 492, 320), 70, "dark", hint)
            for i, hint in enumerate(("The worry.", "The reassuring fact.", "The twist that makes it worse."))
        ),
        signature=("three rows", "panic, calm, panic"),
        fit_tags=("false relief", "twist", "worry returns"),
        staged=True,
    ),
    MemeFormat(
        id="running_away_balloon",
        name="Running away balloon",
        family="classic",
        when_to_use="Someone reaching for what they want (the balloon) while something holds them back.",
        recognizable=(
            "Two panels in a meadow: a character reaches for a floating balloon; then another character holds it back as the "
            "balloon drifts off."
        ),
        size=(1400, 700),
        background="#1b0c41",
        groups=(("balloon", "chaser", "holder"),),
        slots=(
            TextSlot("balloon", (980, 30, 400, 120), 30, "outline", "Label on the balloon: what they want."),
            TextSlot("chaser", (170, 560, 420, 110), 30, "outline", "Label on the one reaching: who wants it."),
            TextSlot("holder", (720, 560, 420, 110), 30, "outline", "Label on the one holding them back: what stops them."),
        ),
        signature=("balloon drifting away", "reaching character", "held back in panel 2"),
        fit_tags=("held back", "competing priorities", "what we want vs what we have"),
        staged=True,
    ),
)

BY_ID = {f.id: f for f in FORMATS}
FALLBACK = BY_ID["classic_caption"]


def get_format(format_id: str) -> MemeFormat | None:
    return BY_ID.get(format_id.strip())


def menu(only: str | None = None) -> str:
    """The format menu for the ideation prompt."""
    lines = []
    for family, label in FAMILIES.items():
        formats = [f for f in FORMATS if f.family == family and (only is None or f.id == only)]
        if not formats:
            continue
        lines.append(f"### {label} (`{family}`)")
        for f in formats:
            slots = ", ".join(f"{s.name}{'?' if s.optional else ''} (<= {s.max_chars} chars)" for s in f.slots)
            data = f" Chart data: {f.data}" if f.data else ""
            fits = f" Fits: {', '.join(f.fit_tags)}." if f.fit_tags else ""
            cast = _cast_line(f)
            lines.append(
                f"- `{f.id}`: **{f.name}**. Use for: {f.when_to_use} Looks like: {f.recognizable}{fits} Text slots: {slots}.{data}{cast}"
            )
        lines.append("")
    return "\n".join(lines).strip()


def _cast_line(fmt: MemeFormat) -> str:
    """How a staged format is cast (comics: per-panel picks)."""
    if not fmt.staged:
        return ""
    if fmt.family == "comic":
        panels = 4 if fmt.id == "comic_grid_4" else 3
        return f" Drawn from the kit: give `panels` ({panels} entries)."
    from inferno_ghostwriter.images.memes.stagings import roles_menu

    roles = roles_menu(fmt.id)
    return f" Drawn from the kit. Cast roles: {roles}." if roles else " Drawn from the kit."


def build_spec(fmt: MemeFormat) -> str:
    """Everything the build call needs to fill one format."""
    width, height = fmt.size
    lines = [f"Format `{fmt.id}`: {fmt.name}", f"Looks like: {fmt.recognizable}", f"Canvas: {width}x{height}.", "", "Text slots:"]
    if fmt.staged:
        lines.insert(2, "Drawn by code from the character kit." + _cast_line(fmt))
    for s in fmt.slots:
        size = f", box {s.box[2]}x{s.box[3]}px" if s.box[2] else ""
        extra = " Speech bubble: set `speaker` to left/right/center." if s.bubble else ""
        lines.append(f"- `{s.name}`{' (optional)' if s.optional else ''}: {s.hint} At most {s.max_chars} characters{size}.{extra}")
    if fmt.regions:
        lines += ["", "Art regions (draw each in its own coordinate space, viewBox `0 0 <width> <height>`):"]
        for r in fmt.regions:
            backdrop = (
                "Paint a full background for the region." if r.opaque else "TRANSPARENT background: the scene behind is drawn for you."
            )
            lines.append(f"- `{r.name}`: {r.box[2]}x{r.box[3]}. {r.brief} {backdrop}")
    else:
        lines += ["", "No art regions: return an empty `art` list and empty `cast_defs`. Everything visual is drawn by the template."]
    if fmt.data:
        lines += ["", f"Chart data: {fmt.data}"]
    else:
        lines += ["", "No chart data: return an empty `data` list."]
    return "\n".join(lines)
