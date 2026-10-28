# Exporting

Open a post and click **Export**. Each platform gives you a zip bundle; Medium, Substack, LinkedIn and X also offer **Copy**, which puts the post on your clipboard as rich HTML with the images embedded, ready to paste into the platform's editor.

| Platform | Bundle contents | Notes |
| --- | --- | --- |
| **Medium** | `post.html`, `post.md`, `images/`, `thumbnail.png` (1400×788), `README.txt` | Title → title, subtitle → subtitle, sections → Medium's large heading, subsections → small heading. The hero becomes the story preview. |
| **Substack** | `post.html`, `post.md`, `images/`, `thumbnail.png` (1200×630), `README.txt` | The copied body excludes the title and subtitle; paste those into Substack's fields (they are listed in the README). Use the thumbnail as the social preview. |
| **LinkedIn** | `post.html`, `post.md`, `images/`, `thumbnail.png` (1920×1080 cover), `feed-post.txt`, `carousel.pdf`, `carousel.pptx`, `README.txt` | See below. |
| **X** | `post.html`, `post.md`, `images/`, `thumbnail.png` (1500×600 header), `teaser-post.txt`, `README.txt` | See below. |
| **Gumroad** | `post.pdf`, `post.html`, `post.md`, `images/`, `thumbnail.png` | Print-ready PDF for a product or post attachment. |
| **Markdown** | `post.md` with front matter (`title`, `description`, `tags`, `cover_image`, `published: false`), `post.docx`, `images/` | For dev.to, Hashnode, Ghost, static sites, or editors who prefer Word / Google Docs. |

Captions follow the "caption; credit" style under every image in all formats.

If a pasted image does not come through (editors differ in what they accept from the clipboard), drag it in from the bundle's `images/` folder.

## LinkedIn

Choose **LinkedIn** as the platform when you create the post (or make it the persona's default) and the writer follows LinkedIn's conventions: a two-line hook that survives the feed preview, one-to-three-sentence paragraphs, `##` headings only (LinkedIn articles have two heading levels and drop tables), a bolded takeaway per section, and a closing question that invites comments.

The export gives you three ways to publish:

- **Article.** *Copy article for LinkedIn* and paste into **Write article**; upload `thumbnail.png` (1920×1080) as the cover and paste the title into the title field.
- **Feed post.** The export dialog shows a feed post with a live character count (LinkedIn's limit is 3,000; only the first ~210 characters show before "…see more"). It starts as a template built from the article; **Write with Claude** replaces it with one written in the persona's voice, which is saved with the post and included as `feed-post.txt`. Markdown is stripped because LinkedIn shows it literally.
- **Document carousel.** `carousel.pdf` is a swipeable 4:5 (1080×1350) deck for a document post: a cover with the hero, one slide per section with its key sentences, the section's diagram or chart, and a closing slide. `carousel.pptx` is the same deck, editable in PowerPoint, Keynote or Google Slides.

## X

Choose **X (Article)** as the platform and the writer follows X Article conventions: a first line that hooks (it is all the timeline shows), one-to-three-sentence paragraphs, `##` headings, bold used sparingly, lists instead of tables, short code snippets only (X Articles have no code blocks), and a close that invites replies.

- **Article.** Start an X Article, upload `thumbnail.png` (1500×600, the 5:2 header), paste the title into the title field, then *Copy for X* and paste the body. Check any code: paste long snippets as images or links.
- **Teaser post.** `teaser-post.txt` announces the article in 280 characters or fewer: the post's opening sentences that fit, then the title. Publish the article first, then share it with this text.
