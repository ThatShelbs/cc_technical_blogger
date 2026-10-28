Write the voice profile for **$persona_name** (byline: $display_name).

## Evidence

### Measured style baseline across the author's own posts (exact numbers)
```json
$baseline
```

### Analyses of the author's own posts ($own_count posts; this defines identity)
```json
$own_analyses
```

### Analyses of influence posts by other writers ($influence_count posts; borrow technique only)
```json
$influence_analyses
```

### Research on best practices (optional; adapt to the author, never override their voice)
$best_practices

## Output

Return only the Markdown document, starting with `# Voice Profile: $persona_name`. Use exactly these sections, in this order:

1. `## Soul`: who this writer is, what they care about, their worldview and promise to the reader (one tight paragraph plus 3-5 bullets).
2. `## Voice & Tone`: defining traits, each with a verbatim example. Include how tone shifts with humor level (0-10) and education level (beginner / intermediate / expert).
3. `## Signature Moves`: 6-12 recurring techniques, each with "when to use" and a verbatim example.
4. `## Structure Blueprint`: how a post is built: hook pattern(s), section rhythm, heading style, use of lists, how sections transition, how the post closes. Include the measured targets (sentence and paragraph lengths, short-paragraph ratio, words per heading, words per image).
5. `## Titles & Subtitles`: the author's title formulas with their real titles as examples, plus subtitle style.
6. `## Humor`: devices, frequency, placement, and examples; what kinds of jokes they never make.
7. `## Teaching Style`: how they explain concepts, analogies, examples, code, and data.
8. `## Credibility & Trust`: how they cite, show their work, and admit limits.
9. `## Images & Captions`: how images are used (types, frequency, placement), the exact caption and credit format they use (with real examples), and a one-line **Visual style** for generated images that fits the author's brand.
10. `## Lexicon`: words and phrases to use (verbatim from the author) and a "Never use" list (including generic AI-writing tells).
11. `## Do / Don't`: 8-12 crisp rules.
12. `## Voice Anchors`: 6-10 short verbatim passages from the author's own posts (each 1-4 sentences, quoted exactly, with the post title) chosen to show the voice at its most distinctive: an opening, a transition, a joke, an explanation, a closing.

Be specific, evidence-based, and concise (aim for 1,500-2,500 words). This document will be used as the system prompt for writing every future post for this persona.
