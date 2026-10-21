import { ArrowRight, Check } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { useActivePersona, useAuthStatus, useHealth } from '../api/hooks'
import { ClaudeConnect, CloudflareConnect } from '../components/Connections'
import { SampleUploader } from '../components/SampleUploader'
import { VoiceSoulPanel } from '../components/VoiceSoulPanel'
import { Button, Card } from '../components/ui'
import { cx } from '../lib/cx'
import { CreatePersonaForm } from './PersonasPage'

const STEPS = ['Connect Claude', 'Images', 'Persona', 'Your writing', 'Voice soul'] as const

export function WelcomePage() {
  const auth = useAuthStatus()
  const health = useHealth()
  const { data: persona } = useActivePersona()
  const [step, setStep] = useState(0)

  const done = [!!auth.data?.signed_in || !!health.data?.demo, true, !!persona, (persona?.own_samples ?? 0) > 0, !!persona?.voice_soul_version]
  const canNext = step === 1 || done[step]

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 flex flex-col items-center text-center">
        <img src="/logo-mark.svg" alt="" className="mb-4 size-24" />
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Welcome to Prose<span className="flame-text">ferno</span>
        </h1>
        <p className="mt-2 max-w-xl text-muted">
          Five quick steps and every technical post you generate will sound like you wrote it, because it learned from what you wrote.
        </p>
      </div>

      <ol className="mb-8 flex flex-wrap justify-center gap-2" aria-label="Setup steps">
        {STEPS.map((label, i) => (
          <li key={label}>
            <button
              type="button"
              onClick={() => setStep(i)}
              aria-current={step === i ? 'step' : undefined}
              className={cx(
                'inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-semibold',
                step === i ? 'border-accent bg-accent-soft' : 'border-line text-muted hover:text-fg',
              )}
            >
              <span
                className={cx('flex size-5 items-center justify-center rounded-full text-xs', done[i] && i !== 1 ? 'bg-success text-white' : 'bg-surface-2')}
              >
                {done[i] && i !== 1 ? <Check className="size-3.5" aria-hidden /> : i + 1}
              </span>
              {label}
            </button>
          </li>
        ))}
      </ol>

      <div className="space-y-6">
        {step === 0 && <ClaudeConnect />}
        {step === 1 && <CloudflareConnect />}
        {step === 2 &&
          (persona ? (
            <Card>
              <p>
                <span className="font-semibold">{persona.name}</span> is your active persona. You can create more personas later and switch between them.
              </p>
            </Card>
          ) : (
            <Card>
              <h2 className="mb-4 text-lg font-bold">Create your persona</h2>
              <CreatePersonaForm onCreated={() => setStep(3)} submitLabel="Create and continue" />
            </Card>
          ))}
        {step === 3 && persona && (
          <Card>
            <h2 className="mb-1 text-lg font-bold">Add posts you wrote</h2>
            <p className="mb-4 text-sm text-muted">
              Three or more is ideal. You can also add posts by writers you admire as “influences”; Proseferno borrows their techniques, never their identity.
            </p>
            <SampleUploader personaId={persona.id} />
          </Card>
        )}
        {step === 4 && persona && <VoiceSoulPanel personaId={persona.id} />}

        <div className="flex items-center justify-between">
          <Button variant="ghost" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button onClick={() => setStep((s) => s + 1)} disabled={!canNext} icon={<ArrowRight className="size-4" />}>
              {step === 1 ? 'Continue (you can skip this)' : 'Continue'}
            </Button>
          ) : (
            <Link to="/projects/new">
              <Button variant="flame" disabled={!done[4]}>
                Write my first post
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
