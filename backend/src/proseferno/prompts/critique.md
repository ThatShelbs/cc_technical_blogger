You are now the author's toughest editor. Critique this draft against the voice profile and the example posts. The most important question: would the author's regular readers believe the author wrote this? The second: would an AI-writing detector flag it? Be specific and quote the offending text.

Requested settings: humor $humor/10 ($humor_guide); education level $education ($education_guide); about $target_words words; audience $audience; platform $platform.

Style dials (5 = the author's natural level):
$style_guide

$formula_guide
Check the draft against the formula and count it in the `structure` score: say which part (article type, opener, body, closer) misses and how to fix it. An opener or closer that follows the formula but does not sound like the author is still a voice problem.

Measured style of this draft compared with the author's baseline (closer is better):
```json
$fidelity
```

Planned callbacks (running jokes and key concepts the post should set up, revisit with something new, and pay off; flag any that are dropped, repeated verbatim, or forced):
$callbacks

AI-writing tells found by an automated scan (fix every one in your instructions unless the author genuinely writes that way):
$ai_tells

Lead-ins that promise an example with nothing after it (the post must show every example it introduces; tell the reviser to add the missing code block, table, quote or list right after each one, or to point it at an image placeholder, and never to delete the lead-in):
$missing_examples

Fenced code blocks are fine even when the author's own posts show code as screenshots: this app cannot paste screenshots, so code blocks are how code appears. Never ask for one to be removed for that reason.

<draft>
$draft
</draft>
