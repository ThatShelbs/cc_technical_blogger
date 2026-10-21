import { CheckCircle2, ExternalLink, ImageIcon, KeyRound, LogIn, Sparkles } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../api/client'
import { useAuthActions, useAuthStatus, useDeleteCloudflareToken, useHealth, useSettings, useUpdateSettings } from '../api/hooks'
import type { AuthStatusOut } from '../api/types.gen'
import { Badge, Button, Card, Field, Input, Notice } from './ui'

const SOURCE_LABEL: Record<string, string> = {
  app_api_key: 'API key saved in Proseferno',
  env_api_key: 'ANTHROPIC_API_KEY environment variable',
  env_auth_token: 'ANTHROPIC_AUTH_TOKEN environment variable',
  claude_sign_in: 'Signed in with Claude',
  none: 'Not connected',
}

export function ClaudeConnect() {
  const { data: status, isLoading } = useAuthStatus()
  const health = useHealth()
  const actions = useAuthActions()
  const [key, setKey] = useState('')
  const [showKey, setShowKey] = useState(false)

  if (isLoading || !status) return <Card>Checking your Claude connection…</Card>

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <Sparkles className="size-6 text-accent" aria-hidden />
          <div>
            <h2 className="text-lg font-bold">Claude</h2>
            <p className="text-sm text-muted">Writes your voice soul and every post.</p>
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

      {health.data?.demo ? (
        <Notice>Demo mode is on: Claude is simulated, so there is nothing to connect.</Notice>
      ) : (
        <ConnectionDetails status={status} actions={actions} showKey={showKey} setShowKey={setShowKey} />
      )}

      {showKey && !health.data?.demo && (
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
      <p className="text-xs text-muted">&ldquo;Sign in with Claude&rdquo; uses your Claude Console account (API billing), not a Claude.ai chat subscription.</p>
    </Card>
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

export function CloudflareConnect() {
  const { data: settings } = useSettings()
  const update = useUpdateSettings()
  const removeToken = useDeleteCloudflareToken()
  const [accountId, setAccountId] = useState<string | null>(null)
  const [token, setToken] = useState('')
  if (!settings) return null
  const account = accountId ?? settings.cloudflare_account_id ?? ''

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <ImageIcon className="size-6 text-accent" aria-hidden />
          <div>
            <h2 className="text-lg font-bold">Images (optional)</h2>
            <p className="text-sm text-muted">Hero, illustration and meme images use FLUX.2 [klein] on Cloudflare Workers AI.</p>
          </div>
        </div>
        {settings.cloudflare_configured ? <Badge tone="success">Configured</Badge> : <Badge>Not configured</Badge>}
      </div>
      <p className="text-sm text-muted">
        Without it, Proseferno still makes diagrams, charts and SVG illustrations with Claude. Create a token with the <strong>Workers AI</strong> permission in
        the{' '}
        <a className="font-semibold text-primary underline" href="https://dash.cloudflare.com/profile/api-tokens" target="_blank" rel="noreferrer">
          Cloudflare dashboard
        </a>
        ; your account ID is on the Workers AI overview page. Cloudflare includes a daily free allocation.
      </p>
      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault()
          update.mutate({ cloudflare_account_id: account, cloudflare_api_token: token || null }, { onSuccess: () => setToken('') })
        }}
      >
        <Field label="Account ID" htmlFor="cf-account">
          <Input id="cf-account" value={account} onChange={(e) => setAccountId(e.target.value)} placeholder="e.g. 1a2b3c…" />
        </Field>
        <Field
          label="API token"
          htmlFor="cf-token"
          hint={settings.cloudflare_configured ? 'A token is saved. Enter a new one to replace it.' : 'Stored in your OS keychain.'}
        >
          <Input id="cf-token" type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder="••••••••" />
        </Field>
        <div className="flex flex-wrap gap-2 sm:col-span-2">
          <Button type="submit" loading={update.isPending} disabled={!account.trim()}>
            Save image settings
          </Button>
          {settings.cloudflare_configured && (
            <Button variant="ghost" onClick={() => removeToken.mutate()}>
              Remove token
            </Button>
          )}
        </div>
      </form>
      {update.error && <Notice tone="error">{errorText(update.error)}</Notice>}
    </Card>
  )
}
