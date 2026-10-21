import { ChevronDown, Flame } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { errorText } from '../api/client'
import { useActivePersona, useProjectMutations } from '../api/hooks'
import { TOPICS, buildDials, type DialsState, type Education } from './dials'
import { Button, Card, Field, Notice, PageHeader, Select, Slider, Textarea } from '../components/ui'

const PLATFORMS = [
  ['medium', 'Medium'],
  ['substack', 'Substack'],
  ['gumroad', 'Gumroad'],
  ['markdown', 'Markdown (dev.to, Hashnode, Ghost)'],
] as const

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
  const [dials, setDials] = useState<DialsState>({
    targetWords: 1500,
    autoImages: true,
    imageCount: 4,
    humor: null,
    education: null,
    topic: '',
    platform: 'medium',
    includeCode: 'auto',
  })
  const set = (patch: Partial<DialsState>) => setDials((d) => ({ ...d, ...patch }))
  const humor = dials.humor ?? persona?.default_humor ?? 5
  const education = dials.education ?? (persona?.default_education as Education | undefined) ?? 'intermediate'

  const ready = !!persona?.voice_soul_version
  const submit = () =>
    create.mutate(
      { prompt, dials: buildDials(custom, dials), persona_id: persona?.id },
      { onSuccess: (data) => navigate(`/projects/${data.project.id}${data.job_id ? `?job=${data.job_id}` : ''}`) },
    )

  return (
    <>
      <PageHeader title="New post" subtitle={persona ? `Writing as ${persona.name}` : undefined} />
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
          <button type="button" className="flex w-full items-center justify-between font-bold" aria-expanded={custom} onClick={() => setCustom((v) => !v)}>
            Customize
            <ChevronDown className={`size-5 transition ${custom ? 'rotate-180' : ''}`} aria-hidden />
          </button>
          {!custom ? (
            <p className="text-sm text-muted">
              Smart defaults: about 1,500 words, an image every ~350 words (hero first, meme last), your persona&apos;s usual humor and level, topic detected
              automatically.
            </p>
          ) : (
            <div className="space-y-5">
              <Slider
                label="Target length"
                min={500}
                max={5000}
                step={100}
                value={dials.targetWords}
                onChange={(v) => set({ targetWords: v })}
                format={(v) => `${v.toLocaleString()} words`}
              />
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={dials.autoImages}
                    onChange={(e) => set({ autoImages: e.target.checked })}
                    className="accent-[var(--app-accent)]"
                  />
                  Choose the number of images automatically
                </label>
                {!dials.autoImages && <Slider label="Images" min={2} max={12} value={dials.imageCount} onChange={(v) => set({ imageCount: v })} />}
              </div>
              <Slider label="Humor" min={0} max={10} value={humor} onChange={(v) => set({ humor: v })} format={(v) => `${v}/10`} />
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
                <Select id="code" value={dials.includeCode} onChange={(e) => set({ includeCode: e.target.value as DialsState['includeCode'] })}>
                  <option value="auto">Where they help</option>
                  <option value="yes">Yes, include them</option>
                  <option value="no">No code</option>
                </Select>
              </Field>
            </div>
          )}
          <Field label="Publishing on" htmlFor="platform">
            <Select id="platform" value={dials.platform} onChange={(e) => set({ platform: e.target.value as DialsState['platform'] })}>
              {PLATFORMS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
        </Card>
      </form>
    </>
  )
}
