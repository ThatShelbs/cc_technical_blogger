import { useState } from 'react'

import { errorText } from '../api/client'
import { useDetector, useSettings, useSetupDetector, useUpdateSettings } from '../api/hooks'
import { ClaudeConnect, ImagesCard } from '../components/Connections'
import { Button, Card, Dialog, Field, Input, Notice, PageHeader, Select, Switch } from '../components/ui'
import { cx } from '../lib/cx'
import { useTheme, type ThemeMode } from '../theme/useTheme'

const MODELS = [
  ['claude-opus-5-5', 'Claude Opus 5.5 (default: best writing)'],
  ['claude-fable-5-1', 'Claude Fable 5.1 (most capable, higher cost)'],
  ['claude-sonnet-5-5', 'Claude Sonnet 5.5 (faster, lower cost)'],
] as const

function AppearanceCard() {
  const { mode, setMode } = useTheme()
  const options: [ThemeMode, string][] = [
    ['light', 'Day'],
    ['dark', 'Night'],
    ['system', 'Match system'],
  ]
  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-bold">Appearance</h2>
      <div className="inline-flex rounded-lg border border-line p-1" role="radiogroup" aria-label="Theme">
        {options.map(([value, label]) => (
          <button
            key={value}
            role="radio"
            aria-checked={mode === value}
            onClick={() => setMode(value)}
            className={cx('rounded-md px-4 py-1.5 text-sm font-semibold', mode === value ? 'bg-accent-soft' : 'text-muted hover:text-fg')}
          >
            {label}
          </button>
        ))}
      </div>
    </Card>
  )
}

function AdvancedCard() {
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const [model, setModel] = useState<string | null>(null)
  if (!settings) return null
  const currentModel = model ?? settings.model
  const known = MODELS.some(([id]) => id === currentModel)
  return (
    <Card className="space-y-5">
      <div>
        <h2 className="text-lg font-bold">Advanced</h2>
        <p className="text-sm text-muted">The defaults are tuned for the best writing quality.</p>
      </div>
      <Field label="Claude model" htmlFor="model">
        <Select id="model" value={known ? currentModel : 'custom'} onChange={(e) => setModel(e.target.value === 'custom' ? '' : e.target.value)}>
          {MODELS.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
          <option value="custom">Other model ID…</option>
        </Select>
      </Field>
      {!known && (
        <Field label="Model ID" htmlFor="model-id">
          <Input id="model-id" value={currentModel} onChange={(e) => setModel(e.target.value)} placeholder="claude-…" />
        </Field>
      )}
      <Field
        label="Voice editing passes"
        hint="After the draft, an editor pass critiques it against your voice and a revision follows. 0 is faster; 2 is most faithful."
        htmlFor="passes"
      >
        <Select id="passes" value={settings.revision_passes} onChange={(e) => update.mutate({ revision_passes: Number(e.target.value) })}>
          <option value={0}>0 passes</option>
          <option value={1}>1 pass (default)</option>
          <option value={2}>2 passes</option>
        </Select>
      </Field>
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold">Refusal fallback</p>
          <p className="text-sm text-muted">
            If Claude&apos;s safety filters wrongly decline a request, retry it on Anthropic&apos;s recommended fallback model.
          </p>
        </div>
        <Switch checked={settings.use_fallbacks} label="Refusal fallback" onChange={(value) => update.mutate({ use_fallbacks: value })} />
      </div>
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold">AI-detection judge</p>
          <p className="text-sm text-muted">
            Every post gets a 0-100 &ldquo;reads as human&rdquo; score. The free scan always runs; this adds a Claude judge for a sharper read (a few cents per
            post).
          </p>
        </div>
        <Switch checked={settings.ai_detection} label="AI-detection judge" onChange={(value) => update.mutate({ ai_detection: value })} />
      </div>
      <Button
        disabled={!currentModel.trim() || currentModel === settings.model}
        loading={update.isPending}
        onClick={() => update.mutate({ model: currentModel.trim() })}
      >
        Save model
      </Button>
      {update.error && <Notice tone="error">{errorText(update.error)}</Notice>}
      <div className="rounded-xl bg-surface-2 p-4 text-sm">
        <p>
          <span className="font-semibold">Your data folder:</span> <code className="break-all">{settings.data_dir}</code>
        </p>
        <p className="mt-1 text-muted">Samples, voice profiles, posts and images stay on this computer. Version {settings.version}.</p>
      </div>
    </Card>
  )
}

/** The AI-text detectors (the built-in light check and the trained models, any mix), run on this computer, and the humanize pass they drive. */
function HumanizeCard() {
  const { data: settings } = useSettings()
  const { data: detector } = useDetector()
  const update = useUpdateSettings()
  const setup = useSetupDetector()
  const [confirming, setConfirming] = useState(false)
  if (!settings || !detector) return null
  const installing = detector.job?.status === 'queued' || detector.job?.status === 'running'
  return (
    <Card className="space-y-5">
      <div>
        <h2 className="text-lg font-bold">Humanizing</h2>
        <p className="text-sm text-muted">
          After the editor&apos;s pass, Inferno Ghostwriter checks each post against your own writing and rewrites only the passages that read as machine-made.
        </p>
      </div>
      <Field
        label="Humanize rounds"
        hint="Each round rewrites the flagged passages and keeps the new version only if it reads more like you. 0 turns it off."
        htmlFor="humanize-rounds"
      >
        <Select id="humanize-rounds" value={settings.humanize_rounds} onChange={(e) => update.mutate({ humanize_rounds: Number(e.target.value) })}>
          <option value={0}>Off</option>
          <option value={1}>1 round (default)</option>
          <option value={2}>2 rounds</option>
        </Select>
      </Field>
      <fieldset className="space-y-2">
        <legend className="font-semibold">AI detectors</legend>
        <p className="text-sm text-muted">
          Pick one or several. Each scores every post against your own posts, on this computer; nothing is sent anywhere. The light check is built in and
          instant; the trained models are more thorough and need a one-time download.
        </p>
        <ul className="space-y-2">
          {detector.models.map((m) => (
            <li key={m.id}>
              <label className="flex cursor-pointer items-start gap-3 rounded-xl bg-surface-2 p-3">
                <input
                  type="checkbox"
                  className="mt-1 size-4 accent-[var(--app-accent)]"
                  checked={m.selected}
                  disabled={update.isPending}
                  onChange={(e) =>
                    update.mutate({
                      detector_models: e.target.checked ? [...settings.detector_models, m.id] : settings.detector_models.filter((id) => id !== m.id),
                    })
                  }
                />
                <span className="text-sm">
                  <span className="font-semibold">{m.label}</span>
                  {m.id === detector.models[0]?.id && <span className="ml-2 rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold">Default</span>}
                  <span className="ml-2 text-muted">{m.heavy ? (m.installed ? 'Downloaded' : `Download: ${m.size}`) : 'No download'}</span>
                  <span className="mt-0.5 block text-muted">{m.summary}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        <p className="text-sm">{detector.detail}</p>
        {installing && (
          <Notice tone="info">{detector.job?.message || 'Setting up'}… This can take a while on the first run; you can keep using the app.</Notice>
        )}
        {detector.available && !detector.ready && !installing && (
          <Button size="sm" variant="secondary" onClick={() => setConfirming(true)}>
            Set up the trained models
          </Button>
        )}
        {detector.job?.status === 'failed' && <Notice tone="error">{detector.job.error}</Notice>}
        {setup.error && <Notice tone="error">{errorText(setup.error)}</Notice>}
      </fieldset>
      <Dialog open={confirming} onClose={() => setConfirming(false)} title="Download the trained detector models?">
        <div className="space-y-3 text-sm">
          <p>
            This installs PyTorch and downloads the trained models you selected from Hugging Face: about 1.3 GB for both, once. They are stored in your data
            folder and run on your CPU.
          </p>
          <p className="text-muted">A detector on your computer is not the one a platform uses, but it reads the same machine texture.</p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Not now
            </Button>
            <Button loading={setup.isPending} onClick={() => setup.mutate(undefined, { onSettled: () => setConfirming(false) })}>
              Download
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  )
}

export function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="space-y-6">
          <ClaudeConnect />
          <ImagesCard />
          <HumanizeCard />
        </div>
        <div className="space-y-6">
          <AppearanceCard />
          <AdvancedCard />
        </div>
      </div>
    </>
  )
}
