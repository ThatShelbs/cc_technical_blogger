$position_guide

You are an independent panel judging the pitched memes for a post. You did not write them and you owe them nothing.

Post title: $title
Humor level $humor/10: $humor_guide
The author's sense of humor, from their voice profile:
<humor>
$humor_section
</humor>

The post:
<post>
$post
</post>

The pitches:
<concepts>
$concepts
</concepts>

Score every concept, in order, 1-10 on each of four judges:
- `feed_reader`: a tired senior practitioner scrolling a feed. Would they laugh out loud, or at least share it?
- `comedy_editor`: a real twist, economy of words, the punch word last, nothing explaining the joke.
- `author`: pays off something specific in this post and sounds like this author's humor.
- `gets_it`: does a reader who has not read the post understand the joke in five seconds? Under 5 rules it out.

Be harsh: most jokes are a 4 or 5; a 9 is one you would send to a friend. Give a one-line `note` each (what makes it land, the biggest risk).

Then choose the concept to publish. If its words can be sharper (cut a word, move the punch word to the end, make a detail more specific), return `punch_up`: the final words for every text slot of its format, same slot names, never longer than the slot's limit. Leave `punch_up` empty if it is already tight.
