import type { ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { ImageOut } from '../api/types.gen'
import { fullCaption, splitArticle, splitHeader } from '../lib/article'

export function Figure({ image }: { image: ImageOut }) {
  if (!image.url) return null
  return (
    <figure className="my-8">
      <img src={image.url} alt={image.alt} className="w-full rounded-xl border border-line" loading="lazy" />
      {fullCaption(image) && <figcaption className="mt-2 text-center font-sans text-sm text-muted">{fullCaption(image)}</figcaption>}
    </figure>
  )
}

/** Render a link yourself (e.g. to add a reference's actions next to it); return undefined for a plain link. */
export type RenderLink = (href: string | undefined, children: ReactNode) => ReactNode | undefined

export function Markdown({ children, renderLink }: { children: string; renderLink?: RenderLink }) {
  const components: Components | undefined = renderLink
    ? {
        a: ({ href, children: label, node: _node, ...rest }) =>
          renderLink(href, label) ?? (
            <a href={href} {...rest}>
              {label}
            </a>
          ),
      }
    : undefined
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  )
}

export function Article({
  markdown,
  images = [],
  renderImage,
  renderLink,
}: {
  markdown: string
  images?: ImageOut[]
  renderImage?: (slot: string, image: ImageOut | undefined) => ReactNode
  renderLink?: RenderLink
}) {
  const { title, subtitle, body } = splitHeader(markdown)
  const bySlot = new Map(images.map((img) => [img.slot_id, img]))
  return (
    <article className="article">
      {title && <h1>{title}</h1>}
      {subtitle && <p className="subtitle">{subtitle}</p>}
      {splitArticle(body).map((part, index) =>
        part.type === 'text' ? (
          <Markdown key={index} renderLink={renderLink}>
            {part.text}
          </Markdown>
        ) : (
          <div key={`${part.slot}-${index}`}>
            {renderImage ? renderImage(part.slot, bySlot.get(part.slot)) : bySlot.get(part.slot) && <Figure image={bySlot.get(part.slot)!} />}
          </div>
        ),
      )}
    </article>
  )
}
