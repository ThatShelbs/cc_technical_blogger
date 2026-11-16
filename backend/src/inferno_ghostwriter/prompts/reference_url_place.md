The author pasted a link they want in this finished post. Decide where it fits best. Use only what the page says; never guess what is behind the link.

Page: $page_title
Address: $url
Description: $page_description
Page text (start of the page):
$page_text

Author's note: $note

Rules:
- `kind`: `source` if the page backs up a specific claim or explains a concept the post states; `resource` if it is something hands-on or reference-like the reader can use next (a book, course, tutorial, documentation, package, video, tool); `related_article` if it is a post or article to read next. $kind_hint
- `placement`: `inline` when the post already discusses what the page covers, so the link belongs in that sentence. Otherwise `go_deeper`, one line in a short list of things to explore next. A `source` is always `inline`.
- `anchor` (inline only): one sentence copied exactly from the post (the Markdown included). Pick the sentence where a reader would most want to follow the link. Never anchor in a heading, a code block, the title or subtitle, or a line next to an `{{image:...}}` placeholder. Leave `anchor` empty for `go_deeper`.
- `purpose` says what the link adds for the reader.
$existing
<post>
$markdown
</post>
