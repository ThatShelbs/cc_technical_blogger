import { ChevronDown, Flame, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { errorText } from '../api/client'
import { useActivePersona, useProjectMutations } from '../api/hooks'
import { PLATFORMS, buildDials, emptyDials, shownDials, type DialsState, type Platform } from './dials'
import { DialsFields } from '../components/DialsFields'
import { Button, Card, Field, Notice, PageHeader, Select, Textarea } from '../components/ui'

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
  const { targetWords, imageCount, humor } = shownDials(dials, persona)
  const platform = dials.platform ?? (persona?.default_platform as Platform | undefined) ?? 'medium'
  const changed = Object.keys(buildDials(dials)).length > 0

  const ready = !!persona?.voice_profile_version
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
            ? `Writing as ${persona.name}${persona.voice_profile_version ? ` · voice profile v${persona.voice_profile_version}${persona.voice_profile_label ? ` (${persona.voice_profile_label})` : ''}` : ''}`
            : undefined
        }
      />
      {!isLoading && !ready && (
        <div className="mb-6">
          <Notice tone="warn" title={persona ? `${persona.name} has no voice profile yet` : 'No persona is turned on'}>
            {persona ? (
              <Link className="font-semibold underline" to={`/personas/${persona.id}`}>
                Add your writing and generate the voice profile first.
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
              <DialsFields dials={dials} onChange={set} persona={persona} />
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
