# Your Dashboard Has Too Many Donuts

*A short, opinionated tour of the chart types that quietly waste your reader's time.*

![A dashboard with six donut charts](donuts.png)

Last quarter I counted the charts in our team's main dashboard. There were twenty-three. Six of them were donuts. Nobody could tell me what any of the donuts meant, including the person who built them. That person was me.

## The Problem With Pretty

Donut charts look friendly. They are round, they come in nice colors, and they make a dashboard feel finished. But they ask the reader to compare angles and arc lengths, which humans are famously bad at. If two slices are within a few percent of each other, your reader is guessing.

So you're telling me the green slice is bigger than the blue one? I'll take your word for it.

## What I Use Instead

Most of the time, a sorted bar chart does the same job in half the time:

- Sort the bars so the ranking is obvious.
- Label the values directly and drop the legend.
- Use one highlight color for the thing you want people to notice.

If the point is change over time, use a line. If the point is part-to-whole and there are only two parts, write the number in a big font and move on with your life.

```python
import matplotlib.pyplot as plt

shares = {"Search": 41, "Email": 27, "Social": 19, "Direct": 13}
labels, values = zip(*sorted(shares.items(), key=lambda kv: kv[1]))
plt.barh(labels, values, color="#781c6d")
plt.title("Traffic share by channel (%)")
plt.show()
```

## The Rule I Follow Now

Before a chart goes on a dashboard, I ask one question: what decision does this help someone make? If I can't answer in a sentence, the chart doesn't ship. That rule deleted eleven charts, five of the donuts, and roughly a third of our dashboard's load time.

The sixth donut is still there. It's a reminder.
