import { Check, Copy, FileText, Pencil, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'

import { errorText } from '../api/client'
import { usePersona, usePersonaMutations, useSampleMutations, useSamples } from '../api/hooks'
import type { PersonaOut, PersonaUpdate } from '../api/types.gen'
import { SampleUploader } from '../components/SampleUploader'
import { VoiceSoulPanel } from '../components/VoiceSoulPanel'
import { Badge, Button, Card, Dialog, Field, Input, Notice, PageHeader, Select, Slider, Spinner, Switch } from '../components/ui'
import { cx } from '../lib/cx'
import { PLATFORMS, STYLE_DIALS, autoImageCount, styleLabel, type Education, type IncludeCode, type Platform } from './dials'

type Tab = 'samples' | 'voice' | 'settings'

function SamplesTab({ personaId }: { personaId: number }) {
  const { data: samples, isLoading } = useSamples(personaId)
  const mutations = useSampleMutations(personaId)
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <Card>
        <h2 className="mb-4 text-lg font-bold">Add writing samples</h2>
        <SampleUploader personaId={personaId} />
      </Card>
      <div className="min-w-0 space-y-3">
        <h2 className="text-lg font-bold">Samples ({samples?.length ?? 0})</h2>
        {isLoading && <Spinner />}
        {samples?.length === 0 && <p className="text-muted">No samples yet.</p>}
        <ul className="space-y-2">
          {samples?.map((sample) => (
            <li key={sample.id} className="flex items-start gap-3 rounded-xl border border-line bg-surface p-3">
              <FileText className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold" title={sample.title}>
                  {sample.title}
                </p>
                <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                  <p className="flex flex-wrap gap-x-1.5 text-xs text-muted">
                    <span>{sample.word_count.toLocaleString()} words</span>
                    <span aria-hidden>·</span>
                    <span>
                      {sample.image_count} image{sample.image_count === 1 ? '' : 's'}
                    </span>
                    <span aria-hidden>·</span>
                    <span className="uppercase">{sample.source_type}</span>
                    {sample.analyzed && (
                      <>
                        <span aria-hidden>·</span>
                        <span className="text-success">analyzed</span>
                      </>
                    )}
                  </p>
                  <div className="flex shrink-0 items-center gap-1">
                    <Select
                      aria-label={`Sample type for ${sample.title}`}
                      className="h-8 w-32 text-xs"
                      value={sample.kind}
                      onChange={(e) => mutations.setKind.mutate({ id: sample.id, kind: e.target.value as 'own' | 'influence' })}
                    >
                      <option value="own">My writing</option>
                      <option value="influence">Influence</option>
                    </Select>
                    <button
                      type="button"
                      className="rounded-md p-1.5 text-muted hover:bg-danger-soft hover:text-danger"
                      aria-label={`Delete ${sample.title}`}
                      onClick={() => mutations.remove.mutate(sample.id)}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function defaultsFrom(persona: PersonaOut) {
  return {
    name: persona.name,
    display_name: persona.display_name,
    visual_style: persona.visual_style,
    credit_template: persona.credit_template,
    default_humor: persona.default_humor,
    default_education: persona.default_education as Education,
    default_target_words: persona.default_target_words,
    default_image_count: persona.default_image_count ?? 0,
    default_storytelling: persona.default_storytelling,
    default_opinion: persona.default_opinion,
    default_formality: persona.default_formality,
    default_technical_depth: persona.default_technical_depth,
    default_skimmability: persona.default_skimmability,
    default_include_code: persona.default_include_code as IncludeCode,
    default_platform: persona.default_platform as Platform,
  } satisfies PersonaUpdate
}

function SettingsTab({ persona }: { persona: PersonaOut }) {
  const { update, remove } = usePersonaMutations()
  const navigate = useNavigate()
  const [draft, setDraft] = useState(() => defaultsFrom(persona))
  const set = (patch: Partial<typeof draft>) => setDraft((d) => ({ ...d, ...patch }))
  const dirty = JSON.stringify(draft) !== JSON.stringify(defaultsFrom(persona))

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card className="h-fit space-y-5">
        <h2 className="text-lg font-bold">Identity and images</h2>
        <Field label="Persona name" htmlFor="p-name">
          <Input id="p-name" value={draft.name} maxLength={80} onChange={(e) => set({ name: e.target.value })} />
        </Field>
        <Field label="Byline for image credits" htmlFor="p-byline">
          <Input id="p-byline" value={draft.display_name} onChange={(e) => set({ display_name: e.target.value })} />
        </Field>
        <Field
          label="Image credit format"
          hint="{name} is the byline, {tool} is the Claude model that drew the image. Example: Author: {name}; Made with {tool}"
          htmlFor="p-credit"
        >
          <Input id="p-credit" value={draft.credit_template} onChange={(e) => set({ credit_template: e.target.value })} />
        </Field>
        <Field label="Visual style for generated images" hint="Filled in from your voice soul. Keeps a post's images looking like a set." htmlFor="p-visual">
          <Input id="p-visual" value={draft.visual_style} onChange={(e) => set({ visual_style: e.target.value })} />
        </Field>
        <div className="flex items-center justify-between gap-4 rounded-xl border border-line p-4">
          <div>
            <p className="font-semibold">Web research on best practices</p>
            <p className="text-sm text-muted">
              When generating the voice soul, research current advice on titles, storytelling, skimmable structure, humor and credibility.
            </p>
          </div>
          <Switch
            checked={persona.research_enabled}
            label="Web research"
            onChange={(value) => update.mutate({ id: persona.id, body: { research_enabled: value } })}
          />
        </div>
      </Card>

      <Card className="h-fit space-y-5">
        <div>
          <h2 className="text-lg font-bold">Defaults for new posts</h2>
          <p className="text-sm text-muted">
            Every post starts here; you can still change any of them per post. Style dials at 5 mean &ldquo;as I write&rdquo;.
          </p>
        </div>
        <Slider
          label="Target length"
          min={500}
          max={5000}
          step={100}
          value={draft.default_target_words}
          onChange={(v) => set({ default_target_words: v })}
          format={(v) => `${v.toLocaleString()} words`}
        />
        <Slider
          label="Images per post"
          min={0}
          max={12}
          value={draft.default_image_count}
          onChange={(v) => set({ default_image_count: v === 1 ? 2 : v })}
          format={(v) => (v === 0 ? `Automatic (~${autoImageCount(draft.default_target_words)})` : `${v} images`)}
        />
        <Slider label="Humor" min={0} max={10} value={draft.default_humor} onChange={(v) => set({ default_humor: v })} format={(v) => `${v}/10`} />
        {STYLE_DIALS.map(({ key, label, low, high }) => (
          <Slider
            key={key}
            label={label}
            min={0}
            max={10}
            value={draft[`default_${key}`]}
            onChange={(v) => set({ [`default_${key}`]: v })}
            format={(v) => styleLabel(v, low, high)}
          />
        ))}
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Education level" htmlFor="p-edu">
            <Select id="p-edu" value={draft.default_education} onChange={(e) => set({ default_education: e.target.value as Education })}>
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="expert">Expert</option>
            </Select>
          </Field>
          <Field label="Code snippets" htmlFor="p-code">
            <Select id="p-code" value={draft.default_include_code} onChange={(e) => set({ default_include_code: e.target.value as IncludeCode })}>
              <option value="auto">Where they help</option>
              <option value="yes">Include them</option>
              <option value="no">No code</option>
            </Select>
          </Field>
          <Field label="Platform" htmlFor="p-platform">
            <Select id="p-platform" value={draft.default_platform} onChange={(e) => set({ default_platform: e.target.value as Platform })}>
              {PLATFORMS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label.split(' (')[0]}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      <div className="space-y-3 xl:col-span-2">
        {update.error && <Notice tone="error">{errorText(update.error)}</Notice>}
        <div className="flex flex-wrap justify-between gap-2">
          <div className="flex gap-2">
            <Button loading={update.isPending} disabled={!dirty || !draft.name.trim()} onClick={() => update.mutate({ id: persona.id, body: draft })}>
              Save changes
            </Button>
            {dirty && (
              <Button variant="ghost" onClick={() => setDraft(defaultsFrom(persona))}>
                Discard
              </Button>
            )}
          </div>
          <Button
            variant="danger"
            icon={<Trash2 className="size-4" />}
            onClick={() => {
              if (confirm(`Delete persona “${persona.name}” with all its samples, voice souls and posts? This cannot be undone.`)) {
                remove.mutate(persona.id, { onSuccess: () => navigate('/personas') })
              }
            }}
          >
            Delete persona
          </Button>
        </div>
      </div>
    </div>
  )
}

function EditableName({ persona }: { persona: PersonaOut }) {
  const { update } = usePersonaMutations()
  const [value, setValue] = useState<string | null>(null)
  if (value === null) {
    return (
      <span className="inline-flex items-center gap-2">
        {persona.name}
        <button
          type="button"
          className="rounded-md p-1 text-muted hover:bg-surface-2 hover:text-fg"
          aria-label="Rename persona"
          onClick={() => setValue(persona.name)}
        >
          <Pencil className="size-4" />
        </button>
      </span>
    )
  }
  const save = () => {
    if (!value.trim() || value.trim() === persona.name) return setValue(null)
    update.mutate({ id: persona.id, body: { name: value.trim() } }, { onSuccess: () => setValue(null) })
  }
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        save()
      }}
    >
      <Input
        aria-label="Persona name"
        value={value}
        maxLength={80}
        autoFocus
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && setValue(null)}
        className="h-10 max-w-md text-xl font-bold"
      />
      <Button type="submit" size="sm" icon={<Check className="size-4" />} loading={update.isPending} aria-label="Save name" />
      <Button size="sm" variant="ghost" icon={<X className="size-4" />} onClick={() => setValue(null)} aria-label="Cancel rename" />
    </form>
  )
}

export function DuplicatePersonaDialog({
  persona,
  open,
  onClose,
  initialVersion,
}: {
  persona: PersonaOut
  open: boolean
  onClose: () => void
  initialVersion?: number | null
}) {
  const { duplicate } = usePersonaMutations()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [version, setVersion] = useState<number | null>(initialVersion ?? persona.voice_soul_version)
  const [copySamples, setCopySamples] = useState(true)
  return (
    <Dialog open={open} onClose={onClose} title={`New persona from ${persona.name}`}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          duplicate.mutate(
            { id: persona.id, body: { name: name.trim(), voice_soul_version: version, copy_samples: copySamples } },
            {
              onSuccess: (created) => {
                onClose()
                navigate(`/personas/${created.id}`)
              },
            },
          )
        }}
      >
        <p className="text-sm text-muted">
          Branch off a separately named persona (say, a playful version for LinkedIn) instead of another version of this one. Its settings start as copies;
          change anything afterwards without touching {persona.name}.
        </p>
        <Field label="New persona name" htmlFor="dup-name">
          <Input
            id="dup-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={`${persona.name} (playful)`}
            required
            maxLength={80}
            autoFocus
          />
        </Field>
        <Field label="Start from voice soul" htmlFor="dup-version">
          <Select id="dup-version" value={version ?? ''} onChange={(e) => setVersion(e.target.value ? Number(e.target.value) : null)}>
            {persona.voice_soul_versions.map((v) => (
              <option key={v.id} value={v.version}>
                v{v.version}
                {v.label ? ` · ${v.label}` : ''}
                {v.version === persona.voice_soul_version ? ' (in use)' : ''}
              </option>
            ))}
            <option value="">None: I will generate a fresh one</option>
          </Select>
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={copySamples} onChange={(e) => setCopySamples(e.target.checked)} className="accent-[var(--app-accent)]" />
          Copy the writing samples ({persona.own_samples + persona.influence_samples})
        </label>
        {duplicate.error && <Notice tone="error">{errorText(duplicate.error)}</Notice>}
        <Button type="submit" icon={<Copy className="size-4" />} disabled={!name.trim()} loading={duplicate.isPending}>
          Create persona
        </Button>
      </form>
    </Dialog>
  )
}

export function PersonaPage() {
  const id = Number(useParams().id)
  const { data: persona, isLoading, error } = usePersona(id)
  const { activate } = usePersonaMutations()
  const [tab, setTab] = useState<Tab>('samples')
  const [duplicating, setDuplicating] = useState(false)

  if (isLoading) return <Spinner />
  if (error || !persona) return <Notice tone="error">{error ? errorText(error) : 'Persona not found.'}</Notice>

  const tabs: [Tab, string][] = [
    ['samples', 'Writing samples'],
    ['voice', 'Voice soul'],
    ['settings', 'Settings & defaults'],
  ]
  return (
    <>
      <PageHeader
        title={<EditableName key={persona.id} persona={persona} />}
        subtitle={persona.is_active ? 'This persona is on: new posts are written in its voice.' : 'This persona is off.'}
        actions={
          <>
            <Button variant="ghost" icon={<Copy className="size-4" />} onClick={() => setDuplicating(true)}>
              Save as new persona
            </Button>
            {persona.is_active ? (
              <Badge tone="success">On</Badge>
            ) : (
              <Button variant="secondary" onClick={() => activate.mutate(persona.id)}>
                Turn on
              </Button>
            )}
          </>
        }
      />
      <div role="tablist" aria-label="Persona sections" className="mb-6 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={cx(
              '-mb-px border-b-2 px-4 py-2.5 text-sm font-semibold whitespace-nowrap',
              tab === key ? 'border-accent text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'samples' && <SamplesTab personaId={persona.id} />}
      {tab === 'voice' && <VoiceSoulPanel personaId={persona.id} />}
      {tab === 'settings' && <SettingsTab key={`${persona.id}-${persona.name}`} persona={persona} />}
      {duplicating && <DuplicatePersonaDialog persona={persona} open onClose={() => setDuplicating(false)} />}
    </>
  )
}
