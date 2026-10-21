import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
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

export function Markdown({ children }: { children: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
}

export function Article({
  markdown,
  images = [],
  renderImage,
}: {
  markdown: string
  images?: ImageOut[]
  renderImage?: (slot: string, image: ImageOut | undefined) => ReactNode
}) {
  const { title, subtitle, body } = splitHeader(markdown)
  const bySlot = new Map(images.map((img) => [img.slot_id, img]))
  return (
    <article className="article">
      {title && <h1>{title}</h1>}
      {subtitle && <p className="subtitle">{subtitle}</p>}
      {splitArticle(body).map((part, index) =>
        part.type === 'text' ? (
          <Markdown key={index}>{part.text}</Markdown>
        ) : (
          <div key={`${part.slot}-${index}`}>
            {renderImage ? renderImage(part.slot, bySlot.get(part.slot)) : bySlot.get(part.slot) && <Figure image={bySlot.get(part.slot)!} />}
          </div>
        ),
      )}
    </article>
  )
}
