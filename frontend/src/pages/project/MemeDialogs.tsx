import { Lightbulb, Type } from 'lucide-react'
import { useState } from 'react'

import type { MemeFormatOut, MemeInfoOut, MemeSlotOut } from '../../api/types.gen'
import { Badge, Button, Dialog, Field, Input, Notice, Select, Textarea } from '../../components/ui'
import { cx } from '../../lib/cx'

/** Every joke the writers' room pitched for this meme: pick one, ask for the next, or re-pitch in a chosen format. */
export function MemeIdeasDialog({
  open,
  onClose,
  meme,
  formats,
  onPick,
  onNext,
  onFormat,
}: {
  open: boolean
  onClose: () => void
  meme: MemeInfoOut
  formats: MemeFormatOut[]
  onPick: (index: number) => void
  onNext: () => void
  onFormat: (id: string) => void
}) {
  return (
    <Dialog open={open} onClose={onClose} title="Meme ideas" wide>
      <p className="mb-4 text-sm text-muted">
        Claude pitched these jokes for this post. Pick one to draw it. Ideas without art (chats, terminals, labels, charts) appear at once.
      </p>
      <ul className="space-y-3">
        {meme.pitches.map((pitch) => (
          <li
            key={pitch.index}
            aria-label={`${pitch.format_name}: ${pitch.premise}`}
            className={cx('rounded-xl border p-3', pitch.current ? 'border-accent bg-sunken' : 'border-line')}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">{pitch.format_name}</Badge>
              {pitch.current ? <Badge>Showing now</Badge> : pitch.tried ? <Badge>Tried</Badge> : null}
            </div>
            <p className="mt-2 text-sm">{pitch.premise}</p>
            {pitch.words.length > 0 && <p className="mt-1 line-clamp-3 text-xs text-muted">{pitch.words.join(' / ')}</p>}
            {!pitch.current && (
              <Button size="sm" variant="secondary" className="mt-3" onClick={() => onPick(pitch.index)}>
                Use this idea
              </Button>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <Button size="sm" variant="secondary" icon={<Lightbulb className="size-4" />} onClick={onNext}>
          {meme.ideas_left ? 'Next best idea' : 'Pitch five new ideas'}
        </Button>
        <MemeFormatPicker formats={formats} value={meme.format} onPick={onFormat} />
      </div>
    </Dialog>
  )
}

/** Retype the meme's words. Saving redraws it at once with the same art; Claude is not asked. */
export function MemeWordsDialog({
  open,
  onClose,
  slots,
  saving,
  error,
  onSave,
  title = "Edit the meme's words",
  intro = 'The art stays as it is and the text is refitted. Nothing is sent to Claude.',
  labelOf = (slot: MemeSlotOut) => slot.name.replaceAll('_', ' '),
}: {
  open: boolean
  onClose: () => void
  slots: MemeSlotOut[]
  saving: boolean
  error?: string | null
  onSave: (words: Record<string, string>) => void
  title?: string
  intro?: string
  labelOf?: (slot: MemeSlotOut) => string
}) {
  const [words, setWords] = useState<Record<string, string>>({})
  const value = (slot: MemeSlotOut) => words[slot.name] ?? slot.text
  const missing = slots.some((slot) => !slot.optional && !value(slot).trim())
  const changed = slots.some((slot) => value(slot) !== slot.text)

  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          onSave(Object.fromEntries(slots.map((slot) => [slot.name, value(slot)])))
        }}
      >
        <p className="text-sm text-muted">{intro}</p>
        {slots.map((slot) => {
          const id = `meme-word-${slot.name.replaceAll('.', '-')}`
          const text = value(slot)
          const long = text.length > slot.max_chars
          const hint = `${slot.hint}${slot.optional ? ' Optional.' : ''} ${text.length}/${slot.max_chars}${long ? ': long text is drawn smaller.' : ''}`
          const props = { id, value: text, onChange: (e: { target: { value: string } }) => setWords({ ...words, [slot.name]: e.target.value }) }
          return (
            <Field key={slot.name} label={labelOf(slot)} hint={hint} htmlFor={id}>
              {slot.max_chars > 60 ? <Textarea rows={2} {...props} /> : <Input {...props} />}
            </Field>
          )
        })}
        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit" icon={<Type className="size-4" />} loading={saving} disabled={missing || !changed}>
          Save words
        </Button>
      </form>
    </Dialog>
  )
}

/** Remake the meme in a chosen format: Claude pitches jokes for that format and draws the best one. */
export function MemeFormatPicker({
  formats,
  value,
  disabled,
  onPick,
}: {
  formats: MemeFormatOut[]
  value: string
  disabled?: boolean
  onPick: (id: string) => void
}) {
  const families = [...new Set(formats.map((f) => f.family_label))]
  return (
    <Select
      aria-label="Meme format"
      title="Pitch five new ideas in another format"
      className="h-8 w-56 max-w-full text-sm"
      value={value}
      disabled={disabled}
      onChange={(e) => e.target.value && e.target.value !== value && onPick(e.target.value)}
    >
      {!value && <option value="">Meme format…</option>}
      {families.map((family) => (
        <optgroup key={family} label={family}>
          {formats
            .filter((f) => f.family_label === family)
            .map((f) => (
              <option key={f.id} value={f.id} title={f.when_to_use}>
                {f.name}
              </option>
            ))}
        </optgroup>
      ))}
    </Select>
  )
}
