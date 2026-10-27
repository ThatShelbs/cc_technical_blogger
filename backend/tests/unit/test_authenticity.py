from __future__ import annotations

from proseferno.authenticity import AuthorProfile, band, profile_author, report, scan
from proseferno.authenticity.detector import AIDetectionJudgement

HUMAN = """# Pie Charts Are Lame

*A friendly roast.*

I made my first pie chart in 2014, for a quarterly review at a bank. Nobody could tell which slice was bigger.
My manager squinted, sighed, and asked for a table.

So I switched to bars. Sorted ones. It took six minutes.

Why do bars win? Length is easy to compare. Angles aren't, and that's not my opinion; Cleveland and McGill
measured it in 1984 with real people and a stopwatch.

Here is the dumb trick I still use: sort the bars, label them directly, delete the legend. Done.
If your stakeholder misses the pie, bake them an actual pie.

Last week a VP asked me for a donut chart. I said no. I still have my job, for now.
"""

AI = """# Unlocking the Power of Data Visualization

*Navigating the ever-evolving landscape of charts.*

In today's fast-paced world, data visualization plays a crucial role in decision-making.
It's not just about charts, it's about telling stories.
Moreover, effective visuals foster understanding, drive engagement, and empower teams.

Let's dive into the realm of bar charts.
Furthermore, bar charts offer a seamless way to compare values, highlight trends, and surface insights.
Additionally, they provide a robust foundation for analysis, reporting, and communication.

- **Clarity:** Bar charts make comparisons easy to see.
- **Accuracy:** Bar charts reduce perceptual errors in judgment.
- **Flexibility:** Bar charts adapt to many different use cases.

It's important to note that pie charts can still be useful in certain situations.
However, bar charts remain a game-changer for most analysts and teams.

In conclusion, embracing bar charts will unlock new possibilities and elevate your data storytelling journey.
"""


def test_scan_separates_human_from_ai() -> None:
    human, ai = scan(HUMAN), scan(AI)
    assert human.score >= 80, [s.as_dict() for s in human.signals if s.penalty]
    assert ai.score <= 40, ai.score
    assert human.score - ai.score >= 40
    labels = {s.id: s for s in ai.signals}
    assert labels["ai_vocabulary"].penalty > 0 and labels["formulas"].penalty > 0 and labels["ending"].penalty > 0
    assert any("game-changer" in f.reason for f in ai.flags)
    assert "Stock AI vocabulary" in ai.tells_text()


def test_scan_does_not_punish_the_authors_own_habits() -> None:
    em_dash_post = HUMAN.replace(", and asked for a table", "— and asked for a table").replace("; Cleveland", " — Cleveland")
    em_dash_post += "\nRobust results matter — robust ones, not lucky ones — and I check them twice — always.\n"
    generic = scan(em_dash_post)
    author = profile_author([em_dash_post, em_dash_post], baseline={"em_dash_per_1k": 20.0})
    assert "robust" in author.vocabulary
    calibrated = scan(em_dash_post, author)
    assert calibrated.score > generic.score


def test_report_combines_scan_and_judge() -> None:
    result = scan(HUMAN, AuthorProfile())
    judgement = AIDetectionJudgement(human_score=40, verdict="Meh.", human_signals=[], ai_signals=["Uniform"], flagged_passages=[])
    combined = report(result, judgement)
    assert combined["judge_score"] == 40
    assert combined["score"] == round(0.6 * 40 + 0.4 * result.score)
    assert report(result, None, judge_error="offline")["score"] == result.score
    assert band(95) == ("human", "Reads as authentic human writing")
    assert band(10)[0] == "likely_ai"
