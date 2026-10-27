import { ChevronDown, Flame, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { errorText } from '../api/client'
import { useActivePersona, useProjectMutations } from '../api/hooks'
import {
  PLATFORMS,
  STYLE_DIALS,
  TOPICS,
  autoImageCount,
  buildDials,
  emptyDials,
  personaStyle,
  styleLabel,
  type DialsState,
  type Education,
  type IncludeCode,
  type Platform,
} from './dials'
import { Button, Card, Field, Notice, PageHeader, Select, Slider, Textarea } from '../components/ui'

const EXAMPLE = `Why most A/B tests at big companies are underpowered
- story: the test that "won" and then quietly lost
- explain power and minimum detectable effect simply
- quick Python snippet to size a test
- what to do when you can't get more traffic`

export function NewProjectPage() {
  const navigate = useNavigate()
  const { data: persona, isLoading } = useActivePersona()
  const { create } = useProjectMutations()
  const [prompt, setPrompt] = useState('')
  const [custom, setCustom] = useState(false)
  const [dials, setDials] = useState<DialsState>(emptyDials)
  const set = (patch: Partial<DialsState>) => setDials((d) => ({ ...d, ...patch }))

  // What each control shows: the user's choice, else the persona's default.
  const targetWords = dials.targetWords ?? persona?.default_target_words ?? 1500
  const imageCount = dials.imageCount ?? persona?.default_image_count ?? null
  const humor = dials.humor ?? persona?.default_humor ?? 5
  const education = dials.education ?? (persona?.default_education as Education | undefined) ?? 'intermediate'
  const platform = dials.platform ?? (persona?.default_platform as Platform | undefined) ?? 'medium'
  const includeCode = dials.includeCode ?? (persona?.default_include_code as IncludeCode | undefined) ?? 'auto'
  const changed = Object.keys(buildDials(dials)).length > 0

  const ready = !!persona?.voice_soul_version
  const submit = () =>
    create.mutate(
      { prompt, dials: buildDials(dials), persona_id: persona?.id },
      { onSuccess: (data) => navigate(`/projects/${data.project.id}${data.job_id ? `?job=${data.job_id}` : ''}`) },
    )

  return (
    <>
      <PageHeader
        title="New post"
        subtitle={
          persona
            ? `Writing as ${persona.name}${persona.voice_soul_version ? ` · voice soul v${persona.voice_soul_version}${persona.voice_soul_label ? ` (${persona.voice_soul_label})` : ''}` : ''}`
            : undefined
        }
      />
      {!isLoading && !ready && (
        <div className="mb-6">
          <Notice tone="warn" title={persona ? `${persona.name} has no voice soul yet` : 'No persona is turned on'}>
            {persona ? (
              <Link className="font-semibold underline" to={`/personas/${persona.id}`}>
                Add your writing and generate the voice soul first.
              </Link>
            ) : (
              <Link className="font-semibold underline" to="/welcome">
                Run the setup guide.
              </Link>
            )}
          </Notice>
        </div>
      )}
      <form
        className="grid gap-6 lg:grid-cols-[1fr_22rem]"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <Card className="space-y-4">
          <Field label="What should this post be about?" hint="A sentence is enough. A bullet-point outline gives you more control." htmlFor="prompt">
            <Textarea id="prompt" rows={12} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={EXAMPLE} required minLength={3} />
          </Field>
          {create.error && <Notice tone="error">{errorText(create.error)}</Notice>}
          <Button
            type="submit"
            variant="flame"
            size="lg"
            icon={<Flame className="size-5" />}
            disabled={!ready || prompt.trim().length < 3}
            loading={create.isPending}
          >
            Write my post
          </Button>
        </Card>

        <Card className="h-fit space-y-5">
          <Field label="Publishing on" htmlFor="platform">
            <Select id="platform" value={platform} onChange={(e) => set({ platform: e.target.value as Platform })}>
              {PLATFORMS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <button type="button" className="flex w-full items-center justify-between font-bold" aria-expanded={custom} onClick={() => setCustom((v) => !v)}>
            Customize
            <ChevronDown className={`size-5 transition ${custom ? 'rotate-180' : ''}`} aria-hidden />
          </button>
          {!custom ? (
            <p className="text-sm text-muted">
              Using {persona ? `${persona.name}'s` : 'your'} defaults: about {targetWords.toLocaleString()} words,{' '}
              {imageCount ? `${imageCount} images` : 'an image every ~350 words'} (hero first, meme last), humor {humor}/10, style dials as you write, topic
              detected automatically.
              {changed && ' Some settings are customized for this post.'}
            </p>
          ) : (
            <div className="space-y-5">
              <Slider
                label="Target length"
                min={500}
                max={5000}
                step={100}
                value={targetWords}
                onChange={(v) => set({ targetWords: v })}
                format={(v) => `${v.toLocaleString()} words`}
              />
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={imageCount === null}
                    onChange={(e) => set({ imageCount: e.target.checked ? null : autoImageCount(targetWords) })}
                    className="accent-[var(--app-accent)]"
                  />
                  Choose the number of images automatically
                </label>
                {imageCount !== null && <Slider label="Images" min={2} max={12} value={imageCount} onChange={(v) => set({ imageCount: v })} />}
              </div>
              <Slider label="Humor" min={0} max={10} value={humor} onChange={(v) => set({ humor: v })} format={(v) => `${v}/10`} />
              {STYLE_DIALS.map(({ key, label, low, high }) => (
                <Slider
                  key={key}
                  label={label}
                  min={0}
                  max={10}
                  value={dials.style[key] ?? personaStyle(persona, key)}
                  onChange={(v) => set({ style: { ...dials.style, [key]: v } })}
                  format={(v) => styleLabel(v, low, high)}
                />
              ))}
              <Field label="Education level" htmlFor="education">
                <Select id="education" value={education} onChange={(e) => set({ education: e.target.value as Education })}>
                  <option value="beginner">Beginner: explain everything</option>
                  <option value="intermediate">Intermediate: practical how and why</option>
                  <option value="expert">Expert: trade-offs and depth</option>
                </Select>
              </Field>
              <Field label="Topic" htmlFor="topic">
                <Select id="topic" value={dials.topic} onChange={(e) => set({ topic: e.target.value })}>
                  <option value="">Detect automatically</option>
                  {TOPICS.map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Code snippets and prompts" htmlFor="code">
                <Select id="code" value={includeCode} onChange={(e) => set({ includeCode: e.target.value as IncludeCode })}>
                  <option value="auto">Where they help</option>
                  <option value="yes">Yes, include them</option>
                  <option value="no">No code</option>
                </Select>
              </Field>
              <Button variant="ghost" size="sm" icon={<RotateCcw className="size-4" />} disabled={!changed} onClick={() => setDials(emptyDials)}>
                Reset to persona defaults
              </Button>
            </div>
          )}
        </Card>
      </form>
    </>
  )
}
