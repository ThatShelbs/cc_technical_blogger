import { Plus, Users } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { errorText } from '../api/client'
import { usePersonaMutations, usePersonas } from '../api/hooks'
import { Badge, Button, Card, Dialog, EmptyState, Field, Input, Notice, PageHeader, Spinner, Switch } from '../components/ui'

export function CreatePersonaForm({ onCreated, submitLabel = 'Create persona' }: { onCreated?: (id: number) => void; submitLabel?: string }) {
  const { create } = usePersonaMutations()
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        create.mutate({ name: name.trim(), display_name: displayName.trim() || name.trim() }, { onSuccess: (p) => onCreated?.(p.id) })
      }}
    >
      <Field label="Persona name" hint="Something you'll recognize, like your name or “Shelby: playful explainer”." htmlFor="persona-name">
        <Input id="persona-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} autoFocus />
      </Field>
      <Field label="Byline for image credits" hint="Defaults to the persona name." htmlFor="persona-byline">
        <Input id="persona-byline" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder={name || 'Your Name'} />
      </Field>
      {create.error && <Notice tone="error">{errorText(create.error)}</Notice>}
      <Button type="submit" disabled={!name.trim()} loading={create.isPending}>
        {submitLabel}
      </Button>
    </form>
  )
}

export function PersonasPage() {
  const { data: personas, isLoading } = usePersonas()
  const { activate } = usePersonaMutations()
  const [creating, setCreating] = useState(false)

  return (
    <>
      <PageHeader
        title="Personas"
        subtitle="Each persona has its own writing samples and voice profile. Exactly one is on at a time."
        actions={
          <Button icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
            New persona
          </Button>
        }
      />
      {isLoading && <Spinner />}
      {personas && personas.length === 0 && (
        <EmptyState
          icon={<Users className="size-8" />}
          title="No personas yet"
          action={<Button onClick={() => setCreating(true)}>Create your first persona</Button>}
        >
          A persona learns a voice from writing samples.
        </EmptyState>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {personas?.map((persona) => (
          <Card key={persona.id} className={persona.is_active ? 'border-accent ring-2 ring-accent/25' : ''}>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <Link to={`/personas/${persona.id}`} className="text-lg font-bold hover:underline">
                  {persona.name}
                </Link>
                <p className="text-sm text-muted">Byline: {persona.display_name}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">{persona.is_active ? 'On' : 'Off'}</span>
                <Switch
                  checked={persona.is_active}
                  label={`Turn ${persona.name} ${persona.is_active ? 'off' : 'on'}`}
                  disabled={persona.is_active || activate.isPending}
                  onChange={() => activate.mutate(persona.id)}
                />
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge>{persona.own_samples} of my posts</Badge>
              <Badge>{persona.influence_samples} influences</Badge>
              {persona.voice_profile_version ? (
                <Badge tone="success">Voice profile v{persona.voice_profile_version}</Badge>
              ) : (
                <Badge tone="danger">No voice profile</Badge>
              )}
            </div>
            <div className="mt-4">
              <Link to={`/personas/${persona.id}`} className="text-sm font-semibold text-primary hover:underline">
                Manage samples and voice →
              </Link>
            </div>
          </Card>
        ))}
      </div>
      <Dialog open={creating} onClose={() => setCreating(false)} title="New persona">
        <CreatePersonaForm onCreated={() => setCreating(false)} />
      </Dialog>
    </>
  )
}
