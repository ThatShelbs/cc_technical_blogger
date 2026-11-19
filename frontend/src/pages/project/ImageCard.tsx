import { useQueryClient } from '@tanstack/react-query'
import { Dices, History, ImagePlus, Layers, Lightbulb, MonitorSmartphone, PencilLine, Sparkles, ThumbsDown, ThumbsUp, Type, Wand2 } from 'lucide-react'
import { useRef, useState } from 'react'

import { errorText } from '../../api/client'
import { keys, useImageMutations, useMemeFormats, useMemeLooks, useOpeningStyles, useRemixOptions, type RedrawPicks } from '../../api/hooks'
import type { ImageOut } from '../../api/types.gen'
import { useJob } from '../../api/useJob'
import { fullCaption } from '../../lib/article'
import { Badge, Button, Dialog, Field, Input, Notice, Select, Spinner, Textarea } from '../../components/ui'
import { cx } from '../../lib/cx'
import { buildOnChoices, dependentsOf, remixTwists } from '../../lib/remix'
import { textSyncNote, type TextSyncNote } from '../../lib/textSync'
import { MemeIdeasDialog, MemeWordsDialog } from './MemeDialogs'
import { OpeningIdeasDialog } from './OpeningDialogs'
import { RemixDialog } from './RemixDialog'

const PROVIDER_LABEL: Record<string, string> = {
  'claude-svg': 'Claude SVG',
  'vega-lite': 'Claude + Vega-Lite',
  'claude-meme': 'Claude meme',
  'claude-opening': 'Claude + Inferno Ghostwriter layout',
  'claude-scene': 'Claude + character kit',
  placeholder: 'Placeholder',
  upload: 'Your upload',
}

const KIND_LABEL: Record<string, string> = {
  hero: 'Opening · thumbnail',
  diagram: 'Diagram',
  chart: 'Chart',
  illustration: 'Illustration',
  icon: 'Icons',
  meme: 'Closing meme',
  screenshot: 'Screenshot',
}

export function ImageCard({ projectId, image, images = [], title = '' }: { projectId: number; image: ImageOut; images?: ImageOut[]; title?: string }) {
  const qc = useQueryClient()
  const mutations = useImageMutations(projectId)
  const [jobId, setJobId] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [caption, setCaption] = useState(image.caption)
  const [alt, setAlt] = useState(image.alt)
  const [credit, setCredit] = useState(image.credit)
  const fileInput = useRef<HTMLInputElement>(null)

  const [textNote, setTextNote] = useState<TextSyncNote | null>(null)
  // Set when a redraw of this image leaves the images that build on it drawn from its old version.
  const [unmatched, setUnmatched] = useState(false)
  const job = useJob(jobId, (state) => {
    setJobId(null)
    setTextNote(textSyncNote(state))
    setUnmatched(((state.result?.dependents as string[] | undefined) ?? []).length > 0)
    void qc.invalidateQueries({ queryKey: keys.project(projectId) })
  })
  const [instructOpen, setInstructOpen] = useState(false)
  const [instruction, setInstruction] = useState('')
  const busy = !!jobId || mutations.upload.isPending
  // Only images Claude drew have a design to edit; uploads and placeholders can be redrawn or replaced.
  const editable = ['claude-svg', 'vega-lite', 'claude-meme', 'claude-opening', 'claude-scene'].includes(image.provider)
  // The opening image is the thumbnail: preview it as a feed card (the crop platforms show, with the title under it).
  const [feedOpen, setFeedOpen] = useState(false)
  const rateable = (image.kind === 'hero' || image.kind === 'meme') && image.status !== 'pending' && !!image.url
  const rate = (value: number) => mutations.rate.mutate({ id: image.id, rating: image.rating === value ? 0 : value })
  // The opening image (also the thumbnail) carries the panel's pitches; an opening meme has the meme tools too.
  const opening = image.kind === 'hero' ? image.opening : null
  // Why the render panel picked this picture, and what strangers saw in it with no context.
  const why = opening?.review?.why || image.meme?.review_why || ''
  const readings = opening?.review?.readings?.length ? opening.review.readings : (image.meme?.review_readings ?? [])
  const isMeme = image.kind === 'meme' || !!(opening && image.meme)
  // The opening image can become a meme in any format, so it needs the bank even before it is one.
  const memeFormats = useMemeFormats(isMeme || !!opening)
  const memeLooks = useMemeLooks(isMeme)
  const { data: openingCatalog } = useOpeningStyles()
  const [ideasOpen, setIdeasOpen] = useState(false)
  const [memeIdeasOpen, setMemeIdeasOpen] = useState(false)
  const [wordsOpen, setWordsOpen] = useState(false)
  const [remixOpen, setRemixOpen] = useState(false)
  const [buildOpen, setBuildOpen] = useState(false)
  const remixOptions = useRemixOptions(remixOpen)
  const canRemix = editable && (image.remix_dimensions ?? []).length > 0
  // Images that build on each other share one source, so they look like the same data taken further.
  const bases = buildOnChoices(image, images)
  const base = images.find((other) => other.slot_id === image.builds_on)
  const dependents = dependentsOf(image, images)
  const nameOf = (slotId: string) => {
    const other = images.find((i) => i.slot_id === slotId)
    return other ? `${KIND_LABEL[other.kind] ?? other.kind} "${other.caption || other.purpose}"` : slotId
  }
  const redraw = (rethink: boolean, picks: RedrawPicks = {}) => {
    setIdeasOpen(false)
    setMemeIdeasOpen(false)
    setRemixOpen(false)
    mutations.redraw.mutate({ id: image.id, rethink, ...picks }, { onSuccess: (j) => setJobId(j.id) })
  }
  // A meme whose format has no art is drawn by the template alone, so there is nothing for Redraw to redraw.
  const hasArt = !image.meme || image.meme.has_art
  const hasIdeas = opening ? opening.pitches.length > 0 : !!image.meme?.pitches.length
  const openIdeas = () => (opening ? setIdeasOpen(true) : setMemeIdeasOpen(true))
  // Words the author can retype with no model call: a code-drawn opening's text, or a meme's.
  const openingWords = !!opening?.slots.length
  const wordSlots = opening?.slots.length ? opening.slots : (image.meme?.slots ?? [])
  const wordsMutation = openingWords ? mutations.openingWords : mutations.memeWords
  const edit = () =>
    mutations.edit.mutate(
      { id: image.id, instruction: instruction.trim() },
      {
        onSuccess: (j) => {
          setJobId(j.id)
          setInstructOpen(false)
          setInstruction('')
        },
      },
    )

  return (
    <figure className="group my-8 font-sans not-italic">
      {/* The opening image is the thumbnail and often carries a headline, so its label sits above it, not on it. */}
      {opening && (
        <div className="mb-2 flex justify-center">
          <Badge tone="accent">{opening.style_label ? `Opening image · ${opening.style_label}` : KIND_LABEL.hero}</Badge>
        </div>
      )}
      <div className="relative overflow-hidden rounded-xl border border-line bg-sunken">
        {image.url ? (
          <img src={image.url} alt={image.alt} className={cx('w-full', busy && 'opacity-40')} />
        ) : (
          <div className="flex aspect-video items-center justify-center p-6 text-center text-sm text-muted">
            {image.status === 'pending' ? <Spinner label="Creating image…" /> : image.purpose}
          </div>
        )}
        {busy && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="rounded-full bg-surface px-4 py-2 shadow">
              <Spinner label={job.message || 'Redrawing…'} />
            </span>
          </div>
        )}
        {!opening && (
          <div className="absolute top-2 left-2">
            <Badge tone="accent">{KIND_LABEL[image.kind] ?? image.kind}</Badge>
          </div>
        )}
      </div>

      {fullCaption(image) && <figcaption className="mt-2 text-center text-sm text-muted">{fullCaption(image)}</figcaption>}
      {(why || readings.length > 0) && !busy && (
        <p className="mt-1 text-center text-xs text-muted" aria-label="Why the panel picked this one">
          {why ? `Why this one: ${/[.!?]$/.test(why) ? why : `${why}.`} ` : ''}
          {readings.length > 0 ? `Strangers read it as: “${readings[0]}”` : ''}
        </p>
      )}
      {image.status === 'error' && (
        <div className="mt-2">
          <Notice tone="error">{image.error}</Notice>
        </div>
      )}
      {job.status === 'failed' && (
        <div className="mt-2">
          <Notice tone="error">{job.error}</Notice>
        </div>
      )}
      {mutations.upload.error && (
        <div className="mt-2">
          <Notice tone="error">{errorText(mutations.upload.error)}</Notice>
        </div>
      )}
      {textNote && !busy && (
        <div className="mt-2">
          <Notice tone={textNote.tone} title="Text updated to match">
            {textNote.text}
          </Notice>
        </div>
      )}
      {image.remix && !busy && (image.remix.brainstormed || image.remix.tweaks.length > 0) && (
        <p className="mt-1 text-center text-xs text-muted" aria-label="What the last redraw tried">
          {image.remix.brainstormed && image.remix.improvements[0] ? `Last redraw set out to: ${image.remix.improvements[0].replace(/\.$/, '')}. ` : ''}
          {remixTwists(image.remix) ? `Tried ${remixTwists(image.remix)}.` : ''}
        </p>
      )}
      {base && <p className="mt-1 text-center text-xs text-muted">Builds on the {nameOf(base.slot_id)}: same data and look, taken further.</p>}
      {unmatched && dependents.length > 0 && !busy && (
        <div className="mt-2">
          <Notice tone="warn" title="Other images build on this one">
            <p>
              {dependents.map(nameOf).join(', ')} {dependents.length === 1 ? 'was' : 'were'} drawn from the previous version.
            </p>
            <Button
              size="sm"
              variant="secondary"
              className="mt-2"
              icon={<Layers className="size-4" />}
              loading={mutations.matchDependents.isPending}
              onClick={() =>
                mutations.matchDependents.mutate(image.id, {
                  onSuccess: (j) => {
                    setUnmatched(false)
                    setJobId(j.id)
                  },
                })
              }
            >
              Redraw {dependents.length === 1 ? 'it' : 'them'} to match
            </Button>
          </Notice>
        </div>
      )}
      {isMeme && image.meme?.premise && (
        <p className="mt-1 text-center text-xs text-muted">
          {image.meme.format_name}: {image.meme.premise}
        </p>
      )}
      {opening?.fallback_from && (
        <p className="mt-1 text-center text-xs text-muted">
          The panel&rsquo;s first pick ({opening.fallback_from}) could not be built, so this is its next best idea. Open Ideas to see them all.
        </p>
      )}
      {opening && opening.sources.length > 0 && (
        <p className="mt-1 text-center text-xs text-muted">
          Sources:{' '}
          {opening.sources.map((source, i) => (
            <span key={source.title}>
              {i > 0 && '; '}
              {source.url ? (
                <a href={source.url} target="_blank" rel="noreferrer" className="underline">
                  {source.title}
                </a>
              ) : (
                source.title
              )}
            </span>
          ))}
        </p>
      )}
      {image.meme?.fallback_from && (
        <p className="mt-1 text-center text-xs text-muted">
          Claude could not draw the “{image.meme.fallback_from}” format, so this is a stand-in. Open Ideas to try another.
        </p>
      )}
      {image.kind === 'screenshot' && image.status === 'placeholder' && (
        <p className="mt-2 text-center text-xs text-muted">Replace this placeholder with a real screenshot: {image.purpose}</p>
      )}
      {image.kind === 'screenshot' && image.provider === 'claude-svg' && (
        <p className="mt-2 text-center text-xs text-muted">Claude drew this mock screen. Use Replace if you have the real screenshot.</p>
      )}

      {feedOpen && opening && image.url && (
        <div className="mx-auto mt-3 max-w-md overflow-hidden rounded-xl border border-line bg-surface shadow" aria-label="Feed card preview">
          <div className="aspect-[1200/630] overflow-hidden bg-sunken">
            <img src={image.url} alt="" className={cx('size-full', opening.thumbnail_fit === 'contain' ? 'object-contain' : 'object-cover')} />
          </div>
          <p className="px-4 py-3 text-base leading-snug font-bold">{title || 'Your post title'}</p>
        </div>
      )}
      <div className="mt-3 flex flex-wrap justify-center gap-2" aria-label={`Actions for ${KIND_LABEL[image.kind] ?? 'image'}`}>
        {rateable && (
          <>
            <Button
              size="sm"
              variant={image.rating === 1 ? 'primary' : 'ghost'}
              icon={<ThumbsUp className="size-4" />}
              aria-pressed={image.rating === 1}
              aria-label="I like this one"
              onClick={() => rate(1)}
              disabled={busy || mutations.rate.isPending}
            />
            <Button
              size="sm"
              variant={image.rating === -1 ? 'primary' : 'ghost'}
              icon={<ThumbsDown className="size-4" />}
              aria-pressed={image.rating === -1}
              aria-label="Not for me"
              onClick={() => rate(-1)}
              disabled={busy || mutations.rate.isPending}
            />
          </>
        )}
        {opening && image.url && (
          <Button
            size="sm"
            variant={feedOpen ? 'secondary' : 'ghost'}
            icon={<MonitorSmartphone className="size-4" />}
            aria-pressed={feedOpen}
            onClick={() => setFeedOpen((open) => !open)}
          >
            Feed preview
          </Button>
        )}
        {editable && (
          <Button
            size="sm"
            variant="secondary"
            icon={<Wand2 className="size-4" />}
            onClick={() => setInstructOpen(true)}
            disabled={busy}
            title="Tell Claude what to change; the rest of the image stays"
          >
            Edit
          </Button>
        )}
        {hasArt && (
          <Button
            size="sm"
            variant="secondary"
            icon={<Dices className="size-4" />}
            onClick={() => redraw(false)}
            disabled={busy}
            title="Claude critiques this image, then redraws the same idea to fix its weakest point, with a new twist (colors, cast or staging)"
          >
            Redraw
          </Button>
        )}
        {hasArt && canRemix && (
          <Button
            size="sm"
            variant="secondary"
            icon={<Sparkles className="size-4" />}
            onClick={() => setRemixOpen(true)}
            disabled={busy}
            title="Choose what the redraw experiments with: colors, who is in it, staging, medium"
          >
            Remix
          </Button>
        )}
        {hasIdeas ? (
          <Button
            size="sm"
            variant="secondary"
            icon={<Lightbulb className="size-4" />}
            onClick={openIdeas}
            disabled={busy}
            title={opening ? 'See every opening the panel judged, pick one, or try another style' : 'See every joke Claude pitched, pick one, or ask for more'}
          >
            Ideas
          </Button>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            icon={<Lightbulb className="size-4" />}
            onClick={() => redraw(true)}
            disabled={busy}
            title="Ask Claude for a different idea"
          >
            New idea
          </Button>
        )}
        {wordSlots.length > 0 && (
          <Button
            size="sm"
            variant="secondary"
            icon={<Type className="size-4" />}
            onClick={() => {
              wordsMutation.reset()
              setWordsOpen(true)
            }}
            disabled={busy}
            title="Retype the text; the layout or art stays and Claude is not asked"
          >
            Words
          </Button>
        )}
        <Button size="sm" variant="secondary" icon={<ImagePlus className="size-4" />} onClick={() => fileInput.current?.click()} disabled={busy}>
          Replace
        </Button>
        <Button
          size="sm"
          variant="ghost"
          icon={<PencilLine className="size-4" />}
          onClick={() => {
            setCaption(image.caption)
            setAlt(image.alt)
            setCredit(image.credit)
            setEditOpen(true)
          }}
        >
          Caption
        </Button>
        {(bases.length > 0 || base) && (
          <Button
            size="sm"
            variant="ghost"
            icon={<Layers className="size-4" />}
            onClick={() => {
              mutations.buildOn.reset()
              setBuildOpen(true)
            }}
            disabled={busy}
            title="Draw this image from an earlier one, so both share the same data, colors and shapes"
          >
            Builds on
          </Button>
        )}
        {image.history.length > 1 && (
          <Button size="sm" variant="ghost" icon={<History className="size-4" />} onClick={() => setHistoryOpen(true)}>
            Versions ({image.history.length})
          </Button>
        )}
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          className="hidden"
          aria-label="Upload replacement image"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) mutations.upload.mutate({ id: image.id, file })
            e.target.value = ''
          }}
        />
      </div>

      {opening && hasIdeas && (
        <OpeningIdeasDialog
          open={ideasOpen}
          onClose={() => setIdeasOpen(false)}
          opening={opening}
          styles={openingCatalog.styles}
          onPick={(index) => redraw(false, { openingConcept: index })}
          onNext={() => redraw(true)}
          onStyle={(id) => redraw(false, { openingStyle: id })}
          memeFormats={memeFormats.data ?? []}
          onMemeFormat={(id) => redraw(false, { memeFormat: id })}
          onMemeIdeas={
            image.meme?.pitches.length
              ? () => {
                  setIdeasOpen(false)
                  setMemeIdeasOpen(true)
                }
              : undefined
          }
        />
      )}
      {image.meme && !!image.meme.pitches.length && (
        <MemeIdeasDialog
          open={memeIdeasOpen}
          onClose={() => setMemeIdeasOpen(false)}
          meme={image.meme}
          formats={memeFormats.data ?? []}
          looks={memeLooks.data ?? []}
          onLook={(id) => redraw(false, { memeLook: id })}
          onPick={(index) => redraw(false, { memeConcept: index })}
          onNext={() => redraw(true)}
          onFormat={(id) => redraw(false, { memeFormat: id })}
        />
      )}
      {wordsOpen && wordSlots.length > 0 && (
        <MemeWordsDialog
          open
          onClose={() => setWordsOpen(false)}
          slots={wordSlots}
          saving={wordsMutation.isPending}
          error={wordsMutation.error ? errorText(wordsMutation.error) : null}
          onSave={(words) => wordsMutation.mutate({ id: image.id, words }, { onSuccess: () => setWordsOpen(false) })}
          {...(openingWords
            ? {
                title: "Edit the opening image's words",
                intro: 'The layout is redrawn with your words at once. Numbers and sources stay as researched. Nothing is sent to Claude.',
                labelOf: (slot: { hint: string }) => slot.hint,
              }
            : {})}
        />
      )}

      {remixOpen && (
        <RemixDialog
          open
          onClose={() => setRemixOpen(false)}
          image={image}
          dimensions={remixOptions.data ?? []}
          onRemix={(tweaks, improve) => redraw(false, { tweaks, improve })}
        />
      )}

      <Dialog open={buildOpen} onClose={() => setBuildOpen(false)} title="Build on an earlier image">
        <div className="space-y-4">
          <p className="text-sm text-muted">
            When two images tell one story (a chart, then the same chart split into groups), draw the second from the first: it reuses the same data, colors and
            shapes and adds only what is new.
          </p>
          <Field label="This image builds on" htmlFor={`builds-on-${image.id}`}>
            <Select
              id={`builds-on-${image.id}`}
              value={image.builds_on ?? ''}
              disabled={mutations.buildOn.isPending || mutations.clearBuildOn.isPending}
              onChange={(e) => {
                const slotId = e.target.value
                if (!slotId) return mutations.clearBuildOn.mutate(image.id, { onSuccess: () => setBuildOpen(false) })
                mutations.buildOn.mutate(
                  { id: image.id, slotId },
                  {
                    onSuccess: (j) => {
                      setJobId(j.id)
                      setBuildOpen(false)
                    },
                  },
                )
              }}
            >
              <option value="">Nothing (it stands alone)</option>
              {bases.map((other) => (
                <option key={other.id} value={other.slot_id}>
                  {KIND_LABEL[other.kind] ?? other.kind}: {other.caption || other.purpose}
                </option>
              ))}
            </Select>
          </Field>
          <p className="text-xs text-muted">Choosing an image redraws this one from it right away. The current version stays in Versions.</p>
          {mutations.buildOn.error && <Notice tone="error">{errorText(mutations.buildOn.error)}</Notice>}
        </div>
      </Dialog>

      <Dialog open={historyOpen} onClose={() => setHistoryOpen(false)} title="Image versions" wide>
        <div className="grid gap-4 sm:grid-cols-2">
          {image.history.map((entry) => (
            <button
              key={entry.index}
              type="button"
              className="rounded-xl border border-line p-2 text-left hover:border-accent"
              onClick={() => mutations.revert.mutate({ id: image.id, index: entry.index }, { onSuccess: () => setHistoryOpen(false) })}
            >
              <img src={entry.url} alt={`Version ${entry.index + 1}`} className="w-full rounded-lg" />
              <p className="mt-1 text-xs text-muted">
                v{entry.index + 1} · {PROVIDER_LABEL[entry.provider] ?? entry.provider}{' '}
                {entry.created_at ? `· ${new Date(entry.created_at).toLocaleString()}` : ''}
              </p>
            </button>
          ))}
        </div>
      </Dialog>

      <Dialog open={instructOpen} onClose={() => setInstructOpen(false)} title="Edit this image">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            edit()
          }}
        >
          <Field
            label="What should change?"
            hint="Claude keeps the concept and layout and changes only what you describe. The current version stays in Versions."
            htmlFor={`instruct-${image.id}`}
          >
            <Textarea
              id={`instruct-${image.id}`}
              rows={3}
              value={instruction}
              autoFocus
              placeholder="Make the arrows orange and label the y-axis in percent"
              onChange={(e) => setInstruction(e.target.value)}
            />
          </Field>
          {mutations.edit.error && <Notice tone="error">{errorText(mutations.edit.error)}</Notice>}
          <Button type="submit" icon={<Wand2 className="size-4" />} loading={mutations.edit.isPending} disabled={instruction.trim().length < 3}>
            Edit image
          </Button>
        </form>
      </Dialog>

      <Dialog open={editOpen} onClose={() => setEditOpen(false)} title="Caption and credit">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            mutations.update.mutate({ id: image.id, caption, alt, credit }, { onSuccess: () => setEditOpen(false) })
          }}
        >
          <Field label="Caption" htmlFor={`cap-${image.id}`}>
            <Input id={`cap-${image.id}`} value={caption} onChange={(e) => setCaption(e.target.value)} />
          </Field>
          <Field label="Credit" hint="Who made it and with what model or tool." htmlFor={`credit-${image.id}`}>
            <Input id={`credit-${image.id}`} value={credit} onChange={(e) => setCredit(e.target.value)} />
          </Field>
          <Field label="Alt text" hint="Describes the image for screen readers." htmlFor={`alt-${image.id}`}>
            <Input id={`alt-${image.id}`} value={alt} onChange={(e) => setAlt(e.target.value)} />
          </Field>
          <Button type="submit" loading={mutations.update.isPending}>
            Save
          </Button>
        </form>
      </Dialog>
    </figure>
  )
}
