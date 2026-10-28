import { CheckCircle2, ExternalLink, ImageIcon, KeyRound, LogIn, Sparkles } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../api/client'
import { useAuthActions, useAuthStatus, useHealth, useSettings, useUpdateSettings } from '../api/hooks'
import type { AuthStatusOut, SettingsOut } from '../api/types.gen'
import { cx } from '../lib/cx'
import { Badge, Button, Card, Field, Input, Notice } from './ui'

type Connection = SettingsOut['claude_connection']

const CONNECTIONS: [Connection, string, string][] = [
  ['api', 'Anthropic API', 'Billed to Claude Console credits'],
  ['subscription', 'Claude subscription', 'Your Pro or Max plan, through Claude Code'],
]

const SOURCE_LABEL: Record<string, string> = {
  app_api_key: 'API key saved in Proseferno',
  env_api_key: 'ANTHROPIC_API_KEY environment variable',
  env_auth_token: 'ANTHROPIC_AUTH_TOKEN environment variable',
  claude_sign_in: 'Signed in with Claude',
  claude_subscription: 'Claude subscription',
  none: 'Not connected',
}

export function ClaudeConnect() {
  const { data: status, isLoading } = useAuthStatus()
  const health = useHealth()
  const actions = useAuthActions()
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()
  const [key, setKey] = useState('')
  const [showKey, setShowKey] = useState(false)

  if (isLoading || !status) return <Card>Checking your Claude connection…</Card>
  const connection = settings?.claude_connection ?? status.connection
  const onApi = connection === 'api'

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <Sparkles className="size-6 text-accent" aria-hidden />
          <div>
            <h2 className="text-lg font-bold">Claude</h2>
            <p className="text-sm text-muted">Writes your voice profile and every post.</p>
          </div>
        </div>
        {status.signed_in ? (
          <Badge tone="success">
            <CheckCircle2 className="size-3.5" aria-hidden /> Connected
          </Badge>
        ) : (
          <Badge tone="danger">Not connected</Badge>
        )}
      </div>

      <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="How Proseferno uses Claude">
        {CONNECTIONS.map(([value, label, hint]) => (
          <button
            key={value}
            role="radio"
            aria-checked={connection === value}
            disabled={updateSettings.isPending}
            onClick={() => connection !== value && updateSettings.mutate({ claude_connection: value })}
            className={cx('rounded-lg border p-3 text-left', connection === value ? 'border-accent bg-accent-soft' : 'border-line hover:bg-surface-2')}
          >
            <span className="block text-sm font-semibold">{label}</span>
            <span className="block text-xs text-muted">{hint}</span>
          </button>
        ))}
      </div>
      {updateSettings.error && <Notice tone="error">{errorText(updateSettings.error)}</Notice>}

      {health.data?.demo ? (
        <Notice>Demo mode is on: Claude is simulated, so there is nothing to connect.</Notice>
      ) : onApi ? (
        <ConnectionDetails status={status} actions={actions} showKey={showKey} setShowKey={setShowKey} />
      ) : (
        <SubscriptionDetails status={status} actions={actions} />
      )}

      {onApi && showKey && !health.data?.demo && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            actions.saveKey.mutate(key, { onSuccess: () => setKey('') })
          }}
        >
          <Field label="Anthropic API key" hint="Stored in your operating system's keychain, never in the project folder." htmlFor="api-key">
            <Input id="api-key" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-ant-…" />
          </Field>
          <Button type="submit" disabled={key.trim().length < 10} loading={actions.saveKey.isPending}>
            Save key
          </Button>
        </form>
      )}
      {onApi ? (
        <p className="text-xs text-muted">
          &ldquo;Sign in with Claude&rdquo; uses your Claude Console account (API billing). To use a Pro or Max plan instead, choose Claude subscription.
        </p>
      ) : (
        <p className="text-xs text-muted">
          Proseferno runs your own Claude Code, signed in through Anthropic&apos;s sign-in, and never sees your Claude credentials. Usage counts toward your
          plan&apos;s limits.{' '}
          <a className="underline" href="https://code.claude.com/docs/en/legal-and-compliance" target="_blank" rel="noreferrer">
            Anthropic&apos;s usage policy
          </a>
        </p>
      )}
    </Card>
  )
}

function SubscriptionDetails({ status, actions }: { status: AuthStatusOut; actions: ReturnType<typeof useAuthActions> }) {
  const usable = status.claude_code_signed_in && status.claude_code_auth_method === 'claude.ai'
  return (
    <>
      <p className="text-sm">
        {status.detail}
        {status.claude_code_version && <span className="text-muted"> Claude Code {status.claude_code_version}.</span>}
      </p>
      {status.warnings.map((w) => (
        <Notice key={w} tone="warn">
          {w}
        </Notice>
      ))}

      <div className="flex flex-wrap gap-2">
        {!status.claude_code_installed ? (
          <a
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-line px-4 text-sm font-semibold hover:bg-surface-2"
            href="https://code.claude.com/docs/en/setup"
            target="_blank"
            rel="noreferrer"
          >
            Install Claude Code <ExternalLink className="size-4" aria-hidden />
          </a>
        ) : (
          !usable && (
            <Button
              icon={<LogIn className="size-4" />}
              onClick={() => actions.claudeCodeLogin.mutate()}
              loading={status.login_in_progress || actions.claudeCodeLogin.isPending}
            >
              {status.login_in_progress ? 'Finish signing in in your browser…' : 'Sign in with Claude'}
            </Button>
          )
        )}
        {status.claude_code_installed && (
          <Button variant="ghost" loading={actions.test.isPending} onClick={() => actions.test.mutate()}>
            Test connection
          </Button>
        )}
      </div>

      {actions.test.data && <Notice tone={actions.test.data.ok ? 'success' : 'error'}>{actions.test.data.message}</Notice>}
      {actions.claudeCodeLogin.error && <Notice tone="error">{errorText(actions.claudeCodeLogin.error)}</Notice>}
      {status.login_in_progress && (
        <Notice>
          A browser window opened for Claude sign-in. Choose your Claude account (Pro or Max). This page updates when you finish.
          {status.login_output && <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-xs">{status.login_output}</pre>}
        </Notice>
      )}
    </>
  )
}

function ConnectionDetails({
  status,
  actions,
  showKey,
  setShowKey,
}: {
  status: AuthStatusOut
  actions: ReturnType<typeof useAuthActions>
  showKey: boolean
  setShowKey: (value: boolean) => void
}) {
  return (
    <>
      <p className="text-sm">
        <span className="font-semibold">{SOURCE_LABEL[status.source] ?? status.source}.</span> {status.detail}
      </p>
      {status.warnings.map((w) => (
        <Notice key={w} tone="warn">
          {w}
        </Notice>
      ))}

      <div className="flex flex-wrap gap-2">
        {status.ant_installed ? (
          <Button icon={<LogIn className="size-4" />} onClick={() => actions.login.mutate()} loading={status.login_in_progress || actions.login.isPending}>
            {status.login_in_progress ? 'Finish signing in in your browser…' : status.source === 'claude_sign_in' ? 'Sign in again' : 'Sign in with Claude'}
          </Button>
        ) : (
          <a
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-line px-4 text-sm font-semibold hover:bg-surface-2"
            href="https://github.com/anthropics/anthropic-cli/releases"
            target="_blank"
            rel="noreferrer"
          >
            Install the Anthropic CLI to sign in <ExternalLink className="size-4" aria-hidden />
          </a>
        )}
        <Button variant="secondary" icon={<KeyRound className="size-4" />} onClick={() => setShowKey(!showKey)}>
          {status.source === 'app_api_key' ? 'Replace API key' : 'Use an API key'}
        </Button>
        {status.signed_in && (
          <Button variant="ghost" loading={actions.test.isPending} onClick={() => actions.test.mutate()}>
            Test connection
          </Button>
        )}
        {status.source === 'app_api_key' && (
          <Button variant="danger" onClick={() => actions.removeKey.mutate()}>
            Remove key
          </Button>
        )}
        {status.source === 'claude_sign_in' && (
          <Button variant="ghost" onClick={() => actions.logout.mutate()}>
            Sign out
          </Button>
        )}
      </div>

      {actions.test.data && <Notice tone={actions.test.data.ok ? 'success' : 'error'}>{actions.test.data.message}</Notice>}
      {actions.login.error && <Notice tone="error">{errorText(actions.login.error)}</Notice>}
      {status.login_in_progress && (
        <Notice>
          A browser window opened for Claude sign-in (works with your organization&apos;s SSO). This page updates when you finish.
          {status.login_output && <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-xs">{status.login_output}</pre>}
        </Notice>
      )}
    </>
  )
}

export function ImagesCard() {
  const { data: settings } = useSettings()
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <ImageIcon className="size-6 text-accent" aria-hidden />
          <div>
            <h2 className="text-lg font-bold">Images</h2>
            <p className="text-sm text-muted">Claude draws every image itself. Nothing to set up.</p>
          </div>
        </div>
        <Badge tone="success">
          <CheckCircle2 className="size-3.5" aria-hidden /> Ready
        </Badge>
      </div>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        <li>Hero and stock-style illustrations, concept icons and memes: hand-built SVG vector art.</li>
        <li>Diagrams (workflows, architectures, comparisons): clean SVG in your inferno palette.</li>
        <li>Data visualizations: Vega-Lite charts with inline data, labeled when the numbers are illustrative.</li>
      </ul>
      <p className="text-xs text-muted">
        Everything is rendered on your computer; model-written code is never run. Credits name you and the model
        {settings ? ` (${settings.image_tool_label.split(':')[0]})` : ''}.
      </p>
    </Card>
  )
}
