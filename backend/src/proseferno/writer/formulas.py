"""Article formulas: the shape of a post, chosen part by part.

A formula is four choices: the **article type** (what the reader is promised), the **opener**,
the **body** structure and the **closer** (the last lines of text; the closing meme always follows
and is not part of the formula). Every part defaults to ``auto``: the author's usual way, as the
voice profile describes it. The formula decides structure only; the voice profile still decides
how every sentence sounds.

The catalog is data, served to the frontend by ``GET /api/formulas/catalog``. To add a style,
add an entry here (see ``docs/formulas.md``); unknown ids in stored dials resolve to ``auto``, so
removing one never breaks an old post.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

AUTO = "auto"
NOTE_MAX = 400


class FormulaOption(BaseModel):
    """One opener, body or closer style."""

    id: str
    label: str
    # Shown in the picker.
    summary: str
    # Picker grouping, e.g. the joke openers.
    group: str
    # What the planner, writer and editor are told.
    guide: str


class ArticleType(BaseModel):
    id: str
    label: str
    summary: str
    guide: str
    # Styles that suit this type, best first; the first of each is the type's classic formula.
    openers: list[str]
    bodies: list[str]
    closers: list[str]


class FormulaParts(BaseModel):
    """A formula as stored: on a post's dials, as a persona default, or saved under a name. None = not set."""

    article_type: str | None = Field(None, max_length=40)
    opener: str | None = Field(None, max_length=40)
    body: str | None = Field(None, max_length=40)
    closer: str | None = Field(None, max_length=40)
    # The author's own instructions for a part: on top of the chosen style, or instead of one.
    opener_note: str | None = Field(None, max_length=NOTE_MAX)
    body_note: str | None = Field(None, max_length=NOTE_MAX)
    closer_note: str | None = Field(None, max_length=NOTE_MAX)


PART_FIELDS: tuple[str, ...] = ("article_type", "opener", "body", "closer")
NOTE_FIELDS: tuple[str, ...] = ("opener_note", "body_note", "closer_note")


def _options(group: str, *rows: tuple[str, str, str, str]) -> list[FormulaOption]:
    return [FormulaOption(id=i, label=label, summary=summary, group=group, guide=guide) for i, label, summary, guide in rows]


OPENERS: list[FormulaOption] = [
    *_options(
        "Joke",
        (
            "joke_confession",
            "Joke: the confession",
            "Admit your own mistake or bad habit first.",
            "Open with a self-deprecating confession: a specific, slightly embarrassing thing the author did, believed or shipped that "
            "the reader has probably done too. The author is the butt of the joke, never the reader or a colleague. One or two lines, "
            "then turn it into the reason this post exists.",
        ),
        (
            "joke_absurd_analogy",
            "Joke: the absurd analogy",
            "Explain the topic with a comparison that has no business working.",
            "Open with an absurd but accurate analogy: compare the technical subject to something everyday and far outside tech, and "
            "commit to it for a few lines with concrete detail. The comparison must really explain the idea, because the post may "
            "return to it later.",
        ),
        (
            "joke_misdirection",
            "Joke: the misdirection",
            "Set up one expectation, then swerve.",
            "Open with a deadpan setup that leads the reader to expect one thing, then swerve in the next line to the real, less "
            "glamorous truth. Keep the setup straight-faced and short; the swerve is the first true statement about the topic.",
        ),
        (
            "joke_exaggeration",
            "Joke: the exaggeration",
            "Blow a shared pain up until it is funny.",
            "Open by exaggerating a pain every reader in this field shares, with specific and escalating detail (numbers, durations, "
            "counts that go one step too far). The exaggeration must be obviously an exaggeration and rest on a real problem the "
            "post then takes seriously.",
        ),
        (
            "joke_mock_serious",
            "Joke: the mock-serious",
            "Treat something small with far too much gravity.",
            "Open in a mock-serious register: describe a small, familiar technical annoyance as if it were a historic event, a nature "
            "documentary or an official incident report. Hold the straight face for two or three lines, then drop it and speak plainly.",
        ),
    ),
    *_options(
        "Story",
        (
            "anecdote",
            "Personal anecdote",
            "A short true story from your own work.",
            "Open with a short personal anecdote from the author's own work: who, where, what went wrong or right, told with one or "
            "two concrete details. Use only what the brief supplies or what any practitioner could plausibly have lived; never "
            "invent employers, clients or numbers. End the anecdote on the question the post answers.",
        ),
        (
            "cold_open",
            "Cold open",
            "Drop the reader into the middle of the moment.",
            "Open in the middle of the action with no preamble: the alert firing, the chart that made no sense, the meeting going "
            "wrong. Present-tense or close past, sensory and specific, three to six lines. Then step back ('Here is how we got "
            "there') and give the context.",
        ),
        (
            "result_first",
            "Show the result first",
            "Lead with the finished thing, then explain how.",
            "Open by showing the end result: the finished build, the final chart, the before-and-after number, the output the reader "
            "will have. State it plainly in the first two lines, then promise the path to it. The hero image or the first snippet "
            "can carry the result.",
        ),
    ),
    *_options(
        "Bold",
        (
            "contrarian",
            "Controversial idea",
            "State the unpopular opinion plainly, first line.",
            "Open with the contrarian thesis as a flat statement in the first line, with no hedging and no 'some might say'. In the "
            "next lines, concede what the mainstream view gets right, then say what it misses. The claim must be one the post can "
            "defend with evidence; it provokes, it does not troll.",
        ),
        (
            "myth_buster",
            "Bust a myth",
            "Name what everyone believes, then crack it.",
            "Open by stating a belief most readers hold, in the words they would use, and let it stand for a line. Then show the "
            "crack: one fact, result or experience that does not fit. The rest of the post explains what is true instead.",
        ),
        (
            "surprising_number",
            "Surprising number",
            "One figure or result the reader did not expect.",
            "Open with a single surprising number or result and nothing else in the first sentence. The second sentence says why it "
            "is surprising; the third, what it means for the reader. Use a figure from the brief, or one the post derives or "
            "demonstrates itself; never invent a statistic or a source for it.",
        ),
        (
            "bold_promise",
            "Bold promise",
            "Say exactly what the reader can do by the end.",
            "Open with a concrete promise: what the reader will be able to do, decide or stop worrying about by the end, and roughly "
            "how long it takes. Be specific enough to be checkable, and make sure the post delivers exactly that.",
        ),
    ),
    *_options(
        "Serious",
        (
            "direct",
            "Straight to the point",
            "Answer first; no warm-up.",
            "Open with the answer or the main point in the first two sentences, as you would brief a busy colleague. No scene, no "
            "joke, no throat-clearing. Then say who this is for and what the rest of the post adds (the evidence, the how, the "
            "caveats).",
        ),
        (
            "problem_first",
            "Name the problem",
            "Start with the reader's pain, precisely described.",
            "Open by describing the reader's problem so precisely that they recognise their own week in it: the symptom, where it "
            "shows up, what it costs. Do not offer the fix yet. Close the opening by saying a fix exists and this post is it.",
        ),
        (
            "question",
            "Open question",
            "Ask the one question the post exists to answer.",
            "Open with one real question the reader wants answered and cannot answer with yes or no. Follow it with why the obvious "
            "answer is not enough. Ask one question only; a stack of rhetorical questions reads as filler.",
        ),
        (
            "news_peg",
            "What just changed",
            "Start from the release, the update or the news.",
            "Open with what changed and when: the release, the new feature, the result that came out. One or two factual lines, then "
            "'why you should care' in the author's words. Stay with facts given in the brief; do not invent version numbers or dates.",
        ),
    ),
]

BODIES: list[FormulaOption] = [
    *_options(
        "Story",
        (
            "narrative_arc",
            "Narrative arc",
            "Setup, rising trouble, turning point, resolution.",
            "Build the body as one story: the situation and what was at stake; the trouble getting worse (attempts that failed and "
            "why); the turning point (the insight or decision); the resolution and what it changed. Technical explanation arrives "
            "when the story needs it, not in a separate block. Headings mark beats of the story, not topics.",
        ),
        (
            "chronological",
            "Build log",
            "What happened, in the order it happened.",
            "Tell it in order, as a build log: each section is a phase (the starting point, the first attempt, what broke, the fix, "
            "the final state), with the decision made in that phase and the reason for it. Keep the dead ends in; they are the "
            "useful part. Show real artefacts at each phase: a snippet, a config, an error, a result.",
        ),
        (
            "lessons_list",
            "Lessons, one by one",
            "Each lesson: what happened, what it taught, what to do instead.",
            "One section per lesson, most valuable first. Each has the same three moves: what happened (a specific moment), what it "
            "taught (stated as a rule the reader can reuse), and what to do instead next time. Headings state the lesson itself, "
            "not a label like 'Lesson 3'.",
        ),
    ),
    *_options(
        "List",
        (
            "countdown",
            "Countdown",
            "Numbered items from good to best; the top pick comes last.",
            "A numbered countdown that ends on number one. Order the items so each beats the one before, and say in a line why. "
            "Every item gets the same anatomy (what it is, why it earns its place, one concrete example or snippet) and roughly the "
            "same length. The number in the title must match the number of items.",
        ),
        (
            "best_first",
            "Ranked, best first",
            "Numbered items with the most useful one at the top.",
            "A numbered list with the most valuable item first, so a reader who stops early still wins. Every item gets the same "
            "anatomy (the claim in the heading, why it matters, one concrete example or snippet). Later items may be shorter. The "
            "number in the title must match the number of items.",
        ),
        (
            "themed_groups",
            "Grouped by theme",
            "Items sorted into a few named groups.",
            "Sort the points into three to five named groups, each a section with its own short framing line, and list the items "
            "inside each group. Use this when the items are not comparable enough to rank. Say up front how the groups are divided.",
        ),
        (
            "myth_reality",
            "Myth vs. reality",
            "Each section states a common belief, then what is true.",
            "Each section takes one common belief: state it fairly in the heading or the first line, say why people believe it, then "
            "give the reality with evidence (a result, a snippet, an example). End each section with what to do differently.",
        ),
    ),
    *_options(
        "Teach",
        (
            "step_by_step",
            "Step by step",
            "Numbered steps: do this, see that.",
            "Numbered steps in the order the reader performs them. Start with what they need before step one (prerequisites, "
            "versions, data). Each step has one action, the exact command, code or prompt for it, and what the reader should see "
            "when it worked. Put warnings before the step they apply to, not after. Do not skip steps that feel obvious.",
        ),
        (
            "progressive_build",
            "Start simple, build up",
            "The smallest working version first, one addition per section.",
            "Begin with the smallest version that works and show it running. Each later section adds exactly one capability or "
            "fixes one weakness of the version before, and shows what changed (only the new or changed code). The reader has "
            "something that works at the end of every section. Finish with the complete version in one place.",
        ),
        (
            "concept_ladder",
            "Concept ladder",
            "What it is, why it matters, how it works, an example, the traps.",
            "Climb in a fixed order: what it is in one plain sentence; why it exists (the problem it solves); how it works, with one "
            "diagram-worthy mental model; a worked example small enough to follow by eye; where it breaks or gets misused; when to "
            "reach for it and when not to. Define each term on first use and never use one before it is defined.",
        ),
        (
            "question_led",
            "Question by question",
            "Each section answers the next thing the reader would ask.",
            "Every heading is a question the reader would ask next, in the order they would ask it, and the first sentence under it "
            "is the direct answer. Detail and examples follow the answer. Each answer should raise the next question.",
        ),
        (
            "problem_solution",
            "Problem, then solution",
            "The problem, why the obvious fixes fail, the fix, the proof.",
            "Four movements: the problem with a concrete instance; why it is harder than it looks and why the usual fixes fall short; "
            "the solution, shown and not only described; proof that it works (a result, a comparison, a before-and-after) with its "
            "limits. Spend real space on the second movement; it is what makes the solution land.",
        ),
    ),
    *_options(
        "Weigh",
        (
            "criteria_by_criteria",
            "Criterion by criterion",
            "Compare on one criterion per section, with a winner each time.",
            "State the criteria up front and why these ones. Then one section per criterion: how each option does on it, shown with "
            "the same test or example for all of them, and a one-line winner for that criterion. Give every option equal care. A "
            "summary table or list of the round winners comes before the verdict.",
        ),
        (
            "option_by_option",
            "Option by option",
            "Each option in turn, then the head-to-head.",
            "Give each option its own section with the same sub-points in the same order (what it is, where it shines, where it "
            "hurts, who it suits), so the reader can compare across sections. Then one head-to-head section on the differences that "
            "decide the choice. Give every option equal care and length.",
        ),
        (
            "experiment",
            "Experiment report",
            "The question, the setup, what happened, what surprised you.",
            "Write it up as an experiment: the question and what the author expected; the setup in enough detail to repeat it (data, "
            "versions, settings); what was actually run; the results, shown as numbers, charts or output; what was surprising; what "
            "the test does not show. Report only results the brief provides or the post itself demonstrates; never invent benchmark "
            "numbers.",
        ),
        (
            "verdict_review",
            "Review",
            "What it is, what is new, the good, the bad, who it is for.",
            "A review in a fixed order: what it is and what the author used it for; what is new or different; what works well, with "
            "an example of each; what does not, just as specifically; how it compares with the alternative the reader already uses; "
            "who should adopt it now, who should wait. Praise and criticism both need evidence from real use.",
        ),
    ),
    *_options(
        "Argue",
        (
            "argument",
            "Build the argument",
            "Thesis, evidence, the best objection, your answer to it.",
            "An argument in the open: the thesis in one sentence; the two or three strongest pieces of evidence, each in its own "
            "section, strongest last; the best objection stated as its smartest holder would put it; the author's answer to it, "
            "conceding what is fair; what follows if the thesis is right (what the reader should do or stop doing).",
        ),
        (
            "inverted_pyramid",
            "Most important first",
            "The key facts up top, detail in descending order.",
            "Order by importance, not by time: the section after the opening holds everything a reader must know if they read "
            "nothing else; each later section is less essential than the one before (detail, background, edge cases). Any section "
            "can be the last one a reader sees, so none depends on a later one.",
        ),
    ),
]

CLOSERS: list[FormulaOption] = [
    *_options(
        "Land it",
        (
            "full_circle",
            "Full circle",
            "Return to the opening, changed by what the post showed.",
            "Close by returning to the opening scene, joke, question or number, now seen differently because of what the post "
            "established. Echo a phrase or image from the opening without repeating the sentence. Do not summarise; the echo is the "
            "ending.",
        ),
        (
            "kicker",
            "One-line kicker",
            "Stop on a single short line that sticks.",
            "End on one short, quotable line that states the point at its sharpest or twists it once. No recap before it and nothing "
            "after it. If the last paragraph can be cut and the post still ends well, cut it.",
        ),
        (
            "reflection",
            "Personal reflection",
            "What this changed for you.",
            "Close in the first person: what this changed in how the author works or thinks, said plainly and specifically, "
            "including anything they are still unsure about. Keep it short and unsentimental.",
        ),
    ),
    *_options(
        "Hand it over",
        (
            "takeaways",
            "Key takeaways",
            "A short recap the skimmer can keep.",
            "Close with a short recap: three to five takeaways as a tight list, each a complete, specific statement the reader could "
            "act on (not a section title). One closing sentence after the list at most. Use a heading in the author's voice; never "
            "'Conclusion'.",
        ),
        (
            "next_step",
            "One next step",
            "A single concrete thing to do today.",
            "Close with exactly one concrete action the reader can take in the next ten minutes (run this, check that, try it on one "
            "real case), and what they should expect to see. One action, not a menu.",
        ),
        (
            "challenge",
            "A challenge",
            "Dare the reader to try it and see.",
            "Close with a small, specific dare: a thing to try on the reader's own work this week and a way to know whether it "
            "worked. Friendly, a little cheeky, and something they can actually finish.",
        ),
        (
            "verdict",
            "The verdict",
            "A plain recommendation: use this if, that if.",
            "Close with the bottom line as a decision: which option, tool or approach the author recommends and for whom ('choose X "
            "if..., Y if...'), in two to four lines. Commit to it; 'it depends' is only allowed with what it depends on.",
        ),
    ),
    *_options(
        "Open it up",
        (
            "open_question",
            "Question for readers",
            "Ask one real question and invite answers.",
            "Close with one real question for the reader, one the author wants answered and that practitioners will have different "
            "answers to. Ask it directly and specifically; not 'What do you think?'.",
        ),
        (
            "zoom_out",
            "Zoom out",
            "Step back to what this means beyond the post.",
            "Close by stepping back one level: what this means for the reader's team, the practice or the field, in a few grounded "
            "sentences. Stay concrete; no grand claims about the future of everything.",
        ),
        (
            "prediction",
            "A prediction",
            "Make a bet about where this goes next.",
            "Close with a specific, falsifiable prediction about where this is heading, with a rough time frame and the author's "
            "reason for it. Own it as a bet in the first person.",
        ),
        (
            "honest_caveat",
            "The honest caveat",
            "Say what you still do not know.",
            "Close on what remains unsolved, untested or uncertain, stated plainly, and what the author would check next. End "
            "without tying it up; the open edge is the ending.",
        ),
        (
            "teaser",
            "What comes next",
            "Point to the follow-up post.",
            "Close by naming the question this post leaves open and saying it is the subject of the next one. Tease the problem, "
            "not the answer. Use the brief's own follow-up if it names one; do not promise dates.",
        ),
    ),
]

ARTICLE_TYPES: list[ArticleType] = [
    ArticleType(
        id="deep_narrative",
        label="Deep narrative",
        summary="A long-form story that carries the technical ideas inside it.",
        guide="A long-form narrative essay: one story or line of thought runs from the first line to the last, and the technical "
        "substance is carried inside it. Depth over coverage; a few ideas explored fully. Few headings, long sections, scenes and "
        "reasoning rather than lists.",
        openers=["cold_open", "anecdote", "joke_confession", "contrarian", "question"],
        bodies=["narrative_arc", "chronological", "argument", "problem_solution"],
        closers=["full_circle", "reflection", "zoom_out", "kicker", "honest_caveat"],
    ),
    ArticleType(
        id="listicle",
        label="Top N countdown",
        summary="A numbered list of the best, worst or most useful things.",
        guide="A numbered list post: N items, each worth reading on its own, with the number in the title. Every item must earn its "
        "place (no padding to reach a round number) and add something a search would not. The intro says how the items were "
        "chosen.",
        openers=["bold_promise", "joke_exaggeration", "direct", "surprising_number", "problem_first"],
        bodies=["countdown", "best_first", "themed_groups", "myth_reality"],
        closers=["takeaways", "open_question", "next_step", "kicker", "challenge"],
    ),
    ArticleType(
        id="how_to",
        label="How-to",
        summary="Get one specific task done, for a reader who has the task now.",
        guide="A how-to guide: the reader has a specific task and wants it done. Goal-oriented and economical: the shortest reliable "
        "path, with only the explanation needed to avoid mistakes. The title names the task. Assume the reader already knows why "
        "they want it.",
        openers=["problem_first", "direct", "result_first", "bold_promise", "joke_confession"],
        bodies=["step_by_step", "problem_solution", "question_led", "progressive_build"],
        closers=["next_step", "takeaways", "challenge", "honest_caveat", "teaser"],
    ),
    ArticleType(
        id="tutorial",
        label="Tutorial",
        summary="Teach a skill by having the reader build something end to end.",
        guide="A tutorial: the reader learns by doing, building one small complete thing alongside the author. Learning-oriented: "
        "every step works when followed exactly, explains just enough to understand what happened, and the reader ends with "
        "something running and the confidence to change it. Say up front what gets built and what is needed.",
        openers=["result_first", "bold_promise", "problem_first", "anecdote", "joke_absurd_analogy"],
        bodies=["progressive_build", "step_by_step", "concept_ladder"],
        closers=["challenge", "next_step", "takeaways", "teaser", "full_circle"],
    ),
    ArticleType(
        id="comparison",
        label="X vs. Y comparison",
        summary="Two or more options weighed fairly, ending in a recommendation.",
        guide="A comparison: two or more options weighed on stated criteria for a reader who has to choose. Fair to every option "
        "(same tests, same care, real strengths for each), honest about the author's own experience with each, and it ends with a "
        "usable recommendation rather than 'it depends'.",
        openers=["problem_first", "question", "contrarian", "direct", "joke_misdirection"],
        bodies=["criteria_by_criteria", "option_by_option", "experiment", "question_led"],
        closers=["verdict", "takeaways", "open_question", "honest_caveat", "prediction"],
    ),
    ArticleType(
        id="explainer",
        label="Explainer / What is X",
        summary="Make one concept clear: what it is, why it matters, how it works.",
        guide="An explainer: one concept made clear for a reader who has heard the term and wants to really understand it. "
        "Understanding-oriented: plain definitions, one strong mental model, a small worked example, and the common "
        "misunderstandings. It explains; it does not walk through a task.",
        openers=["question", "joke_absurd_analogy", "myth_buster", "direct", "anecdote"],
        bodies=["concept_ladder", "question_led", "myth_reality", "problem_solution", "inverted_pyramid"],
        closers=["takeaways", "zoom_out", "full_circle", "next_step", "teaser"],
    ),
    ArticleType(
        id="case_study",
        label="Case study / build walkthrough",
        summary="How a real project was built or a real problem solved, with results.",
        guide="A case study or real build walkthrough: one real project from the situation to the outcome. Specific above all: the "
        "context and constraints, the decisions and their reasons (including the ones that were wrong), the architecture or "
        "approach, and the measured result. Use the facts in the brief; do not invent metrics, clients or team details.",
        openers=["cold_open", "result_first", "problem_first", "surprising_number", "anecdote"],
        bodies=["chronological", "problem_solution", "narrative_arc", "lessons_list"],
        closers=["takeaways", "reflection", "honest_caveat", "full_circle", "next_step"],
    ),
    ArticleType(
        id="hands_on",
        label="Hands-on / I tried it",
        summary="You tested something yourself and report what really happened.",
        guide="A hands-on report: the author tried something for real and reports what happened, so the reader does not have to. "
        "First-person and evidence-led: the setup, what was run, the output, the surprises and the rough edges. Opinion is "
        "welcome but comes after the evidence. Report only what the brief provides or the post demonstrates.",
        openers=["question", "joke_confession", "result_first", "surprising_number", "cold_open"],
        bodies=["experiment", "chronological", "progressive_build", "question_led"],
        closers=["verdict", "honest_caveat", "challenge", "takeaways", "prediction"],
    ),
    ArticleType(
        id="lessons_learned",
        label="Lessons learned",
        summary="A retrospective: what went wrong or right, and what you took from it.",
        guide="A lessons-learned retrospective: the author looks back on a project, a role or a failure and draws out what they "
        "would do differently. Honest and blameless: real mistakes owned in the first person, each turned into a rule the reader "
        "can reuse. Hindsight is the value; do not just narrate.",
        openers=["joke_confession", "cold_open", "anecdote", "surprising_number", "contrarian"],
        bodies=["lessons_list", "narrative_arc", "chronological", "myth_reality"],
        closers=["reflection", "takeaways", "full_circle", "open_question", "kicker"],
    ),
    ArticleType(
        id="opinion",
        label="Opinion / thought leadership",
        summary="Take a position on where the field is or should be going.",
        guide="An opinion piece: the author takes a clear position on a question practitioners disagree about and argues it. One "
        "thesis, stated early; evidence from experience and from the field; the strongest counter-argument treated fairly. It "
        "should leave the reader with something to do or reconsider, not only a mood.",
        openers=["contrarian", "myth_buster", "anecdote", "joke_misdirection", "surprising_number"],
        bodies=["argument", "myth_reality", "problem_solution", "narrative_arc"],
        closers=["kicker", "prediction", "open_question", "zoom_out", "challenge"],
    ),
    ArticleType(
        id="tool_review",
        label="Tool review / tool update",
        summary="An honest look at a tool or release: what is new, what works, who should care.",
        guide="A tool review or tool update: an honest assessment of a tool, platform or new release from someone who used it. Say "
        "what it is, what changed, and what that means in practice, with examples from real use. Both strengths and weaknesses "
        "need evidence. Never invent features, versions, prices or benchmarks; stay with the brief and what the post shows.",
        openers=["news_peg", "direct", "question", "joke_mock_serious", "result_first"],
        bodies=["verdict_review", "inverted_pyramid", "experiment", "criteria_by_criteria", "question_led"],
        closers=["verdict", "takeaways", "prediction", "honest_caveat", "next_step"],
    ),
]

_TYPES = {t.id: t for t in ARTICLE_TYPES}
_PARTS: dict[str, dict[str, FormulaOption]] = {
    "opener": {o.id: o for o in OPENERS},
    "body": {o.id: o for o in BODIES},
    "closer": {o.id: o for o in CLOSERS},
}
_AUTO_TEXT = {
    "article_type": "the kind of post the brief calls for.",
    "opener": "the author's usual way of opening (see the voice profile).",
    "body": "the structure the author would naturally give this post (see the voice profile).",
    "closer": "the author's usual way of ending (see the voice profile).",
}
_PART_LABEL = {"opener": "Opener", "body": "Body", "closer": "Closer"}


class ResolvedFormula(BaseModel):
    article_type: str = AUTO
    opener: str = AUTO
    body: str = AUTO
    closer: str = AUTO
    opener_note: str = ""
    body_note: str = ""
    closer_note: str = ""

    @property
    def is_set(self) -> bool:
        return any(getattr(self, f) != AUTO for f in PART_FIELDS) or any(getattr(self, f) for f in NOTE_FIELDS)


def known(field: str, value: Any) -> str:
    """A catalog id for this part, or ``auto`` for anything unset or no longer in the catalog."""
    catalog: Mapping[str, Any] = _TYPES if field == "article_type" else _PARTS[field]
    return value if isinstance(value, str) and value in catalog else AUTO


def clean(parts: Mapping[str, Any] | None) -> dict[str, str]:
    """Stored formula values with unknown keys, unknown ids and blanks dropped (an explicit ``auto`` is kept)."""
    out: dict[str, str] = {}
    for field in PART_FIELDS:
        value = (parts or {}).get(field)
        if isinstance(value, str) and (value == AUTO or known(field, value) != AUTO):
            out[field] = value
    for field in NOTE_FIELDS:
        note = str((parts or {}).get(field) or "").strip()[:NOTE_MAX]
        if note:
            out[field] = note
    return out


def resolve_formula(chosen: Mapping[str, Any], default: Mapping[str, Any] | None = None) -> ResolvedFormula:
    """The post's own choice for each part, else the persona's default formula, else ``auto``.

    An explicit ``auto`` (or an empty note) on the post overrides the persona's default.
    """
    default = default or {}
    values: dict[str, str] = {}
    for field in PART_FIELDS:
        value = chosen.get(field)
        values[field] = known(field, value if value is not None else default.get(field))
    for field in NOTE_FIELDS:
        note = chosen.get(field)
        values[field] = str(note if note is not None else default.get(field) or "").strip()[:NOTE_MAX]
    return ResolvedFormula(**values)


def formula_label(formula: ResolvedFormula) -> str:
    """A short name for the post page, e.g. "Tutorial · Show the result first · Start simple, build up · A challenge"."""
    names = [_TYPES[formula.article_type].label] if formula.article_type != AUTO else []
    for field in ("opener", "body", "closer"):
        value = getattr(formula, field)
        if value != AUTO:
            names.append(_PARTS[field][value].label)
        elif getattr(formula, f"{field}_note"):
            names.append(f"Custom {field}")
    return " · ".join(names)


def formula_guide(formula: ResolvedFormula) -> str:
    """The formula as instructions for the plan, draft and critique prompts."""
    if not formula.is_set:
        return (
            "Formula: none chosen. Give the post the shape the author's own writing would give this brief "
            "(opening, structure and ending as the voice profile describes them)."
        )
    lines = [
        "Formula (the shape of this post. It decides structure only; the voice profile still decides how every sentence sounds. "
        "Where the formula and the platform notes disagree about how to open or close, the formula wins):"
    ]
    if formula.article_type != AUTO:
        kind = _TYPES[formula.article_type]
        lines.append(f"- Article type: {kind.label}. {kind.guide}")
    else:
        lines.append(f"- Article type: {_AUTO_TEXT['article_type']}")
    for field in ("opener", "body", "closer"):
        value, note = getattr(formula, field), getattr(formula, f"{field}_note")
        if value != AUTO:
            option = _PARTS[field][value]
            lines.append(f"- {_PART_LABEL[field]}: {option.label}. {option.guide}")
            if note:
                lines.append(f"  The author adds: {note}")
        elif note:
            lines.append(f"- {_PART_LABEL[field]} (the author's own instructions): {note}")
        else:
            lines.append(f"- {_PART_LABEL[field]}: {_AUTO_TEXT[field]}")
    lines.append(
        "The closer is the last lines of text. The closing meme image always comes after it and is not the closer, "
        "and a list of further reading, if one is added later, is not the closer either."
    )
    return "\n".join(lines)


def catalog() -> dict[str, Any]:
    return {"article_types": ARTICLE_TYPES, "openers": OPENERS, "bodies": BODIES, "closers": CLOSERS}
