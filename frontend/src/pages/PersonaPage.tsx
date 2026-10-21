import { FileText, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'

import { errorText } from '../api/client'
import { usePersona, usePersonaMutations, useSampleMutations, useSamples } from '../api/hooks'
import type { PersonaOut } from '../api/types.gen'
import { SampleUploader } from '../components/SampleUploader'
import { VoiceSoulPanel } from '../components/VoiceSoulPanel'
import { Badge, Button, Card, Field, Input, Notice, PageHeader, Select, Slider, Spinner, Switch } from '../components/ui'
import { cx } from '../lib/cx'

type Tab = 'samples' | 'voice' | 'settings'

function SamplesTab({ personaId }: { personaId: number }) {
  const { data: samples, isLoading } = useSamples(personaId)
  const mutations = useSampleMutations(personaId)
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
      <Card>
        <h2 className="mb-4 text-lg font-bold">Add writing samples</h2>
        <SampleUploader personaId={personaId} />
      </Card>
      <div className="space-y-3">
        <h2 className="text-lg font-bold">Samples ({samples?.length ?? 0})</h2>
        {isLoading && <Spinner />}
        {samples?.length === 0 && <p className="text-muted">No samples yet.</p>}
        {samples?.map((sample) => (
          <div key={sample.id} className="flex items-start gap-3 rounded-xl border border-line bg-surface p-3">
            <FileText className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold" title={sample.title}>
                {sample.title}
              </p>
              <p className="text-xs text-muted">
                {sample.word_count.toLocaleString()} words · {sample.image_count} images · {sample.source_type}
                {sample.analyzed ? ' · analyzed' : ''}
              </p>
            </div>
            <Select
              aria-label={`Sample type for ${sample.title}`}
              className="h-8 w-auto text-xs"
              value={sample.kind}
              onChange={(e) => mutations.setKind.mutate({ id: sample.id, kind: e.target.value as 'own' | 'influence' })}
            >
              <option value="own">Mine</option>
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
        ))}
      </div>
    </div>
  )
}

function SettingsTab({ persona }: { persona: PersonaOut }) {
  const { update, remove } = usePersonaMutations()
  const navigate = useNavigate()
  const [draft, setDraft] = useState({
    name: persona.name,
    display_name: persona.display_name,
    default_humor: persona.default_humor,
    default_education: persona.default_education,
    visual_style: persona.visual_style,
    credit_template: persona.credit_template,
  })
  return (
    <Card className="max-w-2xl space-y-5">
      <Field label="Persona name" htmlFor="p-name">
        <Input id="p-name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
      </Field>
      <Field label="Byline for image credits" htmlFor="p-byline">
        <Input id="p-byline" value={draft.display_name} onChange={(e) => setDraft({ ...draft, display_name: e.target.value })} />
      </Field>
      <Field
        label="Image credit format"
        hint="{name} is the byline, {tool} is what made the image. Example: Author: {name}; Made with {tool}"
        htmlFor="p-credit"
      >
        <Input id="p-credit" value={draft.credit_template} onChange={(e) => setDraft({ ...draft, credit_template: e.target.value })} />
      </Field>
      <Field label="Visual style for generated images" hint="Filled in from your voice soul. Keeps a post's images looking like a set." htmlFor="p-visual">
        <Input id="p-visual" value={draft.visual_style} onChange={(e) => setDraft({ ...draft, visual_style: e.target.value })} />
      </Field>
      <Slider label="Default humor" min={0} max={10} value={draft.default_humor} onChange={(v) => setDraft({ ...draft, default_humor: v })} />
      <Field label="Default education level" htmlFor="p-edu">
        <Select id="p-edu" value={draft.default_education} onChange={(e) => setDraft({ ...draft, default_education: e.target.value })}>
          <option value="beginner">Beginner</option>
          <option value="intermediate">Intermediate</option>
          <option value="expert">Expert</option>
        </Select>
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
      {update.error && <Notice tone="error">{errorText(update.error)}</Notice>}
      <div className="flex flex-wrap justify-between gap-2">
        <Button
          loading={update.isPending}
          onClick={() =>
            update.mutate({
              id: persona.id,
              body: { ...draft, default_education: draft.default_education as 'beginner' | 'intermediate' | 'expert' },
            })
          }
        >
          Save changes
        </Button>
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
    </Card>
  )
}

export function PersonaPage() {
  const id = Number(useParams().id)
  const { data: persona, isLoading, error } = usePersona(id)
  const { activate } = usePersonaMutations()
  const [tab, setTab] = useState<Tab>('samples')

  if (isLoading) return <Spinner />
  if (error || !persona) return <Notice tone="error">{error ? errorText(error) : 'Persona not found.'}</Notice>

  const tabs: [Tab, string][] = [
    ['samples', 'Writing samples'],
    ['voice', 'Voice soul'],
    ['settings', 'Settings'],
  ]
  return (
    <>
      <PageHeader
        title={persona.name}
        subtitle={persona.is_active ? 'This persona is on: new posts are written in its voice.' : 'This persona is off.'}
        actions={
          persona.is_active ? (
            <Badge tone="success">On</Badge>
          ) : (
            <Button variant="secondary" onClick={() => activate.mutate(persona.id)}>
              Turn on
            </Button>
          )
        }
      />
      <div role="tablist" aria-label="Persona sections" className="mb-6 flex gap-1 overflow-x-auto border-b border-line">
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
      {tab === 'settings' && <SettingsTab key={persona.id} persona={persona} />}
    </>
  )
}
