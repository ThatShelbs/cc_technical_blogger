import { FolderInput, Link2, Upload } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'

import { errorText } from '../api/client'
import { useSampleMutations, useSeedSamples } from '../api/hooks'
import { Button, Field, Input, Notice, Select } from './ui'
import { cx } from '../lib/cx'

const ACCEPT = '.docx,.pdf,.md,.markdown,.txt,.html,.htm'

export function SampleUploader({ personaId, defaultKind = 'own' }: { personaId: number; defaultKind?: 'own' | 'influence' }) {
  const mutations = useSampleMutations(personaId)
  const seed = useSeedSamples()
  const [kind, setKind] = useState<'own' | 'influence'>(defaultKind)
  const [url, setUrl] = useState('')
  const [dragging, setDragging] = useState(false)
  const [messages, setMessages] = useState<{ tone: 'success' | 'error'; text: string }[]>([])
  const input = useRef<HTMLInputElement>(null)

  const upload = (files: File[]) => {
    if (!files.length) return
    mutations.upload.mutate(
      { files, kind },
      {
        onSuccess: (result) =>
          setMessages([
            ...(result.added.length ? [{ tone: 'success' as const, text: `Added ${result.added.length} sample${result.added.length === 1 ? '' : 's'}.` }] : []),
            ...result.errors.map((text) => ({ tone: 'error' as const, text })),
          ]),
        onError: (error) => setMessages([{ tone: 'error', text: errorText(error) }]),
      },
    )
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    upload(Array.from(event.dataTransfer.files))
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="These samples are" htmlFor="sample-kind">
          <Select id="sample-kind" value={kind} onChange={(e) => setKind(e.target.value as 'own' | 'influence')} className="w-auto">
            <option value="own">My own writing (defines my voice)</option>
            <option value="influence">Writers I admire (borrow techniques)</option>
          </Select>
        </Field>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cx(
          'flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition',
          dragging ? 'border-accent bg-accent-soft' : 'border-line bg-sunken',
        )}
      >
        <Upload className="mb-2 size-7 text-accent" aria-hidden />
        <p className="font-semibold">Drop blog posts here</p>
        <p className="text-sm text-muted">Word (.docx), PDF, Markdown, text or saved HTML. Medium exports work great.</p>
        <Button className="mt-4" variant="secondary" onClick={() => input.current?.click()} loading={mutations.upload.isPending}>
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          aria-label="Choose sample files"
          onChange={(e) => {
            upload(Array.from(e.target.files ?? []))
            e.target.value = ''
          }}
        />
      </div>

      <form
        className="flex flex-col gap-2 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault()
          mutations.importUrl.mutate(
            { url, kind },
            {
              onSuccess: (sample) => {
                setUrl('')
                setMessages([{ tone: 'success', text: `Imported “${sample.title}”.` }])
              },
              onError: (error) => setMessages([{ tone: 'error', text: errorText(error) }]),
            },
          )
        }}
      >
        <div className="flex-1">
          <Field label="Or import a post from a URL" htmlFor="sample-url">
            <Input id="sample-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://medium.com/@you/your-post" />
          </Field>
        </div>
        <Button type="submit" variant="secondary" icon={<Link2 className="size-4" />} disabled={!url} loading={mutations.importUrl.isPending}>
          Import
        </Button>
      </form>

      {seed.data?.available && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface-2 px-4 py-3">
          <p className="text-sm">
            Found <strong>{seed.data.files.length}</strong> posts in <code className="text-xs break-all">{seed.data.directory}</code>
          </p>
          <Button
            size="sm"
            icon={<FolderInput className="size-4" />}
            loading={mutations.importSeed.isPending}
            onClick={() =>
              mutations.importSeed.mutate(undefined, {
                onSuccess: (result) =>
                  setMessages([
                    {
                      tone: 'success',
                      text: result.added.length ? `Imported ${result.added.length} posts as your own writing.` : 'All of those posts are already imported.',
                    },
                    ...result.errors.map((text) => ({ tone: 'error' as const, text })),
                  ]),
              })
            }
          >
            Import them
          </Button>
        </div>
      )}

      {messages.map((m, i) => (
        <Notice key={i} tone={m.tone}>
          {m.text}
        </Notice>
      ))}
    </div>
  )
}
