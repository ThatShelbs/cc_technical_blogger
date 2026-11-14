import { ChevronDown, Flame, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { errorText } from '../api/client'
import { useActivePersona, useProjectMutations } from '../api/hooks'
import { PLATFORMS, buildDials, emptyDials, shownDials, type DialsState, type Platform } from './dials'
import { BrandKitFields } from '../components/BrandKitFields'
import { emptyBrandKit, isEmptyBrandKit } from '../lib/brandKit'
import { DialsFields } from '../components/DialsFields'
import { FormulaFields } from '../components/FormulaFields'
import { OpeningFields } from '../components/OpeningFields'
import { Button, Card, Field, Notice, PageHeader, Select, Textarea } from '../components/ui'
import { cx } from '../lib/cx'

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
  const set = (patch: Partial<DialsState>) => setDials((d) => ({ ...d, ...patch }))

  // What each control shows: the user's choice, else the persona's default.
  const { targetWords, imageCount, humor } = shownDials(dials, persona)
  const platform = dials.platform ?? (persona?.default_platform as Platform | undefined) ?? 'medium'
  const changed = Object.keys(buildDials(dials)).length > 0

  const ready = !!persona?.voice_profile_version
  const submit = () =>
    create.mutate(
      { prompt, dials: buildDials(dials), persona_id: persona?.id, mode, ...(isEmptyBrandKit(brandKit) ? {} : { brand_kit: brandKit }) },
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
          {!prompt.trim() && (
            <Button variant="ghost" size="sm" onClick={() => setPrompt(EXAMPLE)}>
              Use an example prompt
            </Button>
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
          <Button
            type="submit"
            variant="flame"
            size="lg"
            icon={<Flame className="size-5" />}
            disabled={!ready || prompt.trim().length < 3}
            loading={create.isPending}
          >
            {mode === 'ab' ? 'Write two versions' : 'Write my post'}
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
