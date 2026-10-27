import { useState } from 'react'

import { errorText } from '../api/client'
import { useSettings, useUpdateSettings } from '../api/hooks'
import { ClaudeConnect, ImagesCard } from '../components/Connections'
import { Button, Card, Field, Input, Notice, PageHeader, Select, Switch } from '../components/ui'
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
        <p className="mt-1 text-muted">Samples, voice souls, posts and images stay on this computer. Version {settings.version}.</p>
      </div>
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
        </div>
        <div className="space-y-6">
          <AppearanceCard />
          <AdvancedCard />
        </div>
      </div>
    </>
  )
}
