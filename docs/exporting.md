# Exporting

Open a post and click **Export**. Each platform gives you a zip bundle; Medium and Substack also offer **Copy**, which puts the post on your clipboard as rich HTML with the images embedded, ready to paste into the platform's editor.

| Platform | Bundle contents | Notes |
| --- | --- | --- |
| **Medium** | `post.html`, `post.md`, `images/`, `thumbnail.png` (1400×788), `README.txt` | Title → title, subtitle → subtitle, sections → Medium's large heading, subsections → small heading. The hero becomes the story preview. |
| **Substack** | `post.html`, `post.md`, `images/`, `thumbnail.png` (1200×630), `README.txt` | The copied body excludes the title and subtitle; paste those into Substack's fields (they are listed in the README). Use the thumbnail as the social preview. |
| **Gumroad** | `post.pdf`, `post.html`, `post.md`, `images/`, `thumbnail.png` | Print-ready PDF for a product or post attachment. |
| **Markdown** | `post.md` with front matter (`title`, `description`, `tags`, `cover_image`, `published: false`), `post.docx`, `images/` | For dev.to, Hashnode, Ghost, static sites, or editors who prefer Word / Google Docs. |

Captions follow the "caption; credit" style under every image in all formats.

If a pasted image does not come through (editors differ in what they accept from the clipboard), drag it in from the bundle's `images/` folder.
