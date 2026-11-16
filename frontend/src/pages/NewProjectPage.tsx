import { ChevronDown, Flame, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { errorText } from '../api/client'
import { useActivePersona, useIdea, useProjectMutations } from '../api/hooks'
import { PLATFORMS, buildDials, emptyDials, shownDials, type DialsState, type Platform } from './dials'
import { BrandKitFields } from '../components/BrandKitFields'
import { emptyBrandKit, isEmptyBrandKit } from '../lib/brandKit'
import { DialsFields } from '../components/DialsFields'
import { FormulaFields } from '../components/FormulaFields'
import { OpeningFields } from '../components/OpeningFields'
import { Button, Card, Field, Notice, PageHeader, Select, Switch, Textarea } from '../components/ui'
import { cx } from '../lib/cx'
import { useHotkey } from '../lib/hotkeys'

const EXAMPLE = `Why most A/B tests at big companies are underpowered
- story: the test that "won" and then quietly lost
- explain power and minimum detectable effect simply
- quick Python snippet to size a test
- what to do when you can't get more traffic`

const MODES = [
  ['standard', 'Generate & tweak', 'One post in your voice, then refine it with feedback.'],
  ['ab', 'A/B test', 'Two posts: one as your persona is, one with its settings nudged. Pick the better one blind. About twice the cost.'],
] as const

export function NewProjectPage() {
  const navigate = useNavigate()
  const { data: persona, isLoading } = useActivePersona()
  const { create } = useProjectMutations()
  const [prompt, setPrompt] = useState('')
  const [custom, setCustom] = useState(false)
  const [dials, setDials] = useState<DialsState>(emptyDials)
  const [brandKit, setBrandKit] = useState(emptyBrandKit)
  const [mode, setMode] = useState<'standard' | 'ab'>('standard')
  const [interviewChoice, setInterview] = useState<boolean | null>(null)
  const set = (patch: Partial<DialsState>) => setDials((d) => ({ ...d, ...patch }))

  // "Customize first" from Idea Lab: start from the idea's brief and article type, once, then it is the author's to change.
  const [params] = useSearchParams()
  const ideaId = Number(params.get('idea')) || null
  const { data: idea } = useIdea(ideaId)
  const [seeded, setSeeded] = useState<number | null>(null)
  if (idea && idea.state !== 'used' && seeded !== idea.id) {
    setSeeded(idea.id)
    setPrompt(idea.prompt)
    if (idea.article_type && idea.article_type !== 'auto') setDials((d) => ({ ...d, formula: { ...d.formula, article_type: idea.article_type } }))
  }

  // What each control shows: the user's choice, else the persona's default.
  const { targetWords, imageCount, humor } = shownDials(dials, persona)
  const platform = dials.platform ?? (persona?.default_platform as Platform | undefined) ?? 'medium'
  const changed = Object.keys(buildDials(dials)).length > 0

  const ready = !!persona?.voice_profile_version
  // Off unless the author turns it on (or makes it the persona's default); A/B tests write straight away.
  const interview = mode === 'standard' && (interviewChoice ?? persona?.default_interview ?? false)
  const submit = () =>
    create.mutate(
      {
        prompt,
        dials: buildDials(dials),
        persona_id: persona?.id,
        mode,
        interview,
        ...(isEmptyBrandKit(brandKit) ? {} : { brand_kit: brandKit }),
        ...(seeded ? { idea_id: seeded } : {}),
      },
      {
        onSuccess: (data) => navigate(`/projects/${data.project.id}${data.job_id ? `?job=${data.job_id}${interview ? '&kind=interview' : ''}` : ''}`),
      },
    )

  // Ctrl/Cmd+Enter writes the post from anywhere on the page, including the prompt box.
  const canSubmit = ready && prompt.trim().length >= 3 && !create.isPending
  useHotkey(
    'mod+enter',
    (event) => {
      event.preventDefault()
      if (canSubmit) submit()
    },
    true,
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
                Add your writing or start from a ready-made voice, then generate the voice profile first.
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
          {seeded && idea && <Notice>Started from your Idea Lab idea &ldquo;{idea.title}&rdquo;. Change anything you like before writing.</Notice>}
          {!prompt.trim() && (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => setPrompt(EXAMPLE)}>
                Use an example prompt
              </Button>
              <Link to="/ideas" className="text-sm font-semibold text-accent hover:underline">
                Not sure what to write? Open Idea Lab
              </Link>
            </div>
          )}
          <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="How to write it">
            {MODES.map(([value, title, hint]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mode === value}
                onClick={() => setMode(value)}
                className={cx('rounded-xl border px-4 py-3 text-left', mode === value ? 'border-accent bg-accent-soft' : 'border-line hover:bg-surface-2')}
              >
                <span className="block font-semibold">{title}</span>
                <span className="block text-sm text-muted">{hint}</span>
              </button>
            ))}
          </div>
          {mode === 'standard' && (
            <div className="flex items-center justify-between gap-4 rounded-xl border border-line px-4 py-3">
              <div>
                <p className="font-semibold">Interview me first</p>
                <p className="text-sm text-muted">
                  Optional. Claude asks 3-5 questions about this post (your stories, opinions, numbers) and works your answers in. Skip any of them.
                </p>
              </div>
              <Switch checked={interview} label="Interview me first" onChange={setInterview} />
            </div>
          )}
          <Button
            type="submit"
            variant="flame"
            size="lg"
            icon={<Flame className="size-5" />}
            disabled={!ready || prompt.trim().length < 3}
            loading={create.isPending}
            title="Ctrl/Cmd + Enter"
          >
            {mode === 'ab' ? 'Write two versions' : interview ? 'Ask me a few questions' : 'Write my post'}
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
          <div className="space-y-3 border-t border-line pt-4">
            <div>
              <h3 className="font-bold">Formula</h3>
              <p className="text-sm text-muted">The shape of the post. Your voice still writes every sentence.</p>
            </div>
            <FormulaFields
              value={dials.formula}
              onChange={(patch) => set({ formula: { ...dials.formula, ...patch } })}
              defaults={persona?.default_formula}
              brief={prompt}
              humor={humor}
            />
          </div>
          <div className="space-y-3 border-t border-line pt-4">
            <div>
              <h3 className="font-bold">Opening image</h3>
              <p className="text-sm text-muted">The first thing readers see, and the post&rsquo;s thumbnail.</p>
            </div>
            <OpeningFields
              style={dials.openingStyle}
              note={dials.openingNote}
              onChange={set}
              defaultStyle={persona?.default_opening_style}
              formula={dials.formula}
              formulaDefaults={persona?.default_formula}
              brief={prompt}
              humor={humor}
            />
          </div>
          <button
            type="button"
            className="flex w-full items-center justify-between border-t border-line pt-4 font-bold"
            aria-expanded={custom}
            onClick={() => setCustom((v) => !v)}
          >
            Customize
            <ChevronDown className={`size-5 transition ${custom ? 'rotate-180' : ''}`} aria-hidden />
          </button>
          {!custom ? (
            <p className="text-sm text-muted">
              Using {persona ? `${persona.name}'s` : 'your'} defaults: about {targetWords.toLocaleString()} words,{' '}
              {imageCount ? `${imageCount} images` : 'about as many images as you use'} (an opening image first, a meme last), humor {humor}/10, style dials as
              you write, topic and article type detected automatically.
              {changed && ' Some settings are customized for this post.'}
            </p>
          ) : (
            <div className="space-y-5">
              <DialsFields dials={dials} onChange={set} persona={persona} />
              <Button variant="ghost" size="sm" icon={<RotateCcw className="size-4" />} disabled={!changed} onClick={() => setDials(emptyDials)}>
                Reset to persona defaults
              </Button>
              <div className="space-y-3 border-t border-line pt-4">
                <div>
                  <h3 className="font-bold">Image brand kit</h3>
                  <p className="text-sm text-muted">The look of this post&rsquo;s images. You can change it later and redraw them.</p>
                </div>
                <BrandKitFields kit={brandKit} onChange={setBrandKit} personaStyle={persona?.visual_style} />
              </div>
            </div>
          )}
        </Card>
      </form>
    </>
  )
}
