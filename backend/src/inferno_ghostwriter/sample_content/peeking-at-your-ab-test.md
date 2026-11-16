# Stop Peeking at Your A/B Test (I Know You Did)

*Checking results early feels harmless. It quietly doubles your false positives.*

Here is a confession. In my second year as an analyst I shipped a feature because the test was "clearly winning" on day three. It had been planned to run two weeks. By day fourteen the lift had vanished, like a magician's rabbit, and I had a very awkward Slack message to write.

I had peeked. Everyone peeks. The problem is what peeking does to the math.

## Why Peeking Breaks the Test

A standard A/B test promises a 5 percent false positive rate *if you look once*, at the end. Look every day for two weeks and you are no longer running one test. You are running fourteen, and stopping the first time any of them looks good.

Imagine flipping a fair coin and announcing a "biased coin" the moment heads pulls ahead. It will pull ahead at some point. Random walks love to wander.

Here is a quick simulation. No real effect, a check every day, stop at the first p-value below 0.05:

```python
import numpy as np
from scipy import stats

rng = np.random.default_rng(7)
false_wins = 0
for _ in range(2000):
    a = rng.normal(size=(14, 200))
    b = rng.normal(size=(14, 200))
    for day in range(1, 15):
        p = stats.ttest_ind(a[:day].ravel(), b[:day].ravel()).pvalue
        if p < 0.05:
            false_wins += 1
            break
print(false_wins / 2000)
```

I get about 0.25. A test that should be wrong one time in twenty is wrong one time in four.

## What To Do Instead

- **Fix the sample size up front.** Compute it from the smallest effect you would act on, then wait.
- **Use a sequential method if you must look.** Always-valid p-values or alpha spending let you peek honestly.
- **Write the stop rule down before launch.** A sentence in the ticket is enough.

## The Takeaway

You are allowed to be curious. You are not allowed to be curious *and* decisive. Pick one before the test starts, and the data will stop gaslighting you.
