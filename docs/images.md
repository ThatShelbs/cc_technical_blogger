# Images

Every post gets images that add value for the reader. The plan decides how many (about one per 350 words by default, at least two) and what each is for.

| Kind | Purpose | Made by |
| --- | --- | --- |
| **hero** | Opening image and thumbnail | FLUX.2 [klein] (Cloudflare), or a Claude SVG illustration |
| **diagram** | Concepts, workflows, architectures | Claude writes SVG; sanitized and rendered locally with resvg |
| **chart** | Illustrative data visualization | Claude writes a Vega-Lite spec with inline data; rendered locally with vl-convert |
| **illustration** | A conceptual image for a section | FLUX.2 [klein], or Claude SVG |
| **screenshot** | A real UI/console screenshot would help | Placeholder card; replace it with your screenshot |
| **meme** | The closing joke | FLUX.2 [klein] image (no text) + captions overlaid with Pillow |

## Design step

For each slot Claude reads the text around the image, the author's *Images & Captions* guidance from the voice soul, and the persona's visual style, then returns a structured design: a text-to-image prompt, SVG, or chart spec, plus alt text and a caption in the author's caption style.

Text-to-image prompts never ask for text in the image (small distilled models render text poorly); meme captions are drawn on afterwards.

## Credits

Each image gets a credit from the persona's template (default `Author: {name}; Made with {tool}`), for example:

> The saddest pie; Author: Shelby Temple; Made with FLUX.2 [klein] on Cloudflare Workers AI

Charts with made-up numbers are labeled *(illustrative data)*. You can edit any caption, credit or alt text.

## Redraw, new idea, replace, versions

- **Redraw**: same design, new random seed (FLUX images) or a fresh take (diagrams and charts).
- **New idea**: Claude redesigns the image from scratch.
- **Replace**: upload your own image (PNG, JPEG, WebP, ...; converted to PNG).
- **Versions**: every version is kept; click one to restore it.

## Cloudflare setup

1. In the [Cloudflare dashboard](https://dash.cloudflare.com/profile/api-tokens), create an API token with the **Workers AI** permission.
2. Copy your account ID from the Workers AI page.
3. Paste both into **Settings → Images** (the token goes into your OS keychain).

The model is `@cf/black-forest-labs/flux-2-klein-4b`, called with multipart form data (`prompt`, `width`, `height`, `seed`); sizes are kept within 256-1920 px and rounded to multiples of 16.
