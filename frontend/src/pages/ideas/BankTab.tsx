import { Archive, Plus, Search } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { useIdeaBank, useIdeaLabMutations, usePersonas } from '../../api/hooks'
import type { PersonaOut } from '../../api/types.gen'
import { Button, Card, EmptyState, Field, Input, Notice, Select, Spinner, Textarea } from '../../components/ui'
import { BANK_FILTERS, filterBank, type BankFilter } from '../../lib/ideas'
import { IdeaCard } from './IdeaCard'
import { IdeaDialog } from './IdeaDialog'
import { Segmented } from './IdeasTab'

/** An idea of the author's own, straight into the bank. */
function AddIdea({ personaId, onDone }: { personaId: number | undefined; onDone: () => void }) {
  const { createIdea } = useIdeaLabMutations()
  const [title, setTitle] = useState('')
  const [brief, setBrief] = useState('')
  const [outline, setOutline] = useState('')
  const [note, setNote] = useState('')
  return (
    <Card>
      <form
        className="grid gap-3 lg:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault()
          createIdea.mutate({ persona_id: personaId, title, brief, note, outline: outline.split('\n').filter((l) => l.trim()) }, { onSuccess: onDone })
        }}
      >
        <Field label="Title" htmlFor="own-title">
          <Input id="own-title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={200} />
        </Field>
        <Field label="Your note" htmlFor="own-note" hint="Optional. Only for you: who to ask, what to check.">
          <Input id="own-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
        </Field>
        <Field label="Brief" htmlFor="own-brief" hint="Optional. What the post says, in a sentence or two.">
          <Textarea id="own-brief" rows={3} value={brief} onChange={(e) => setBrief(e.target.value)} maxLength={2000} />
        </Field>
        <Field label="Outline" htmlFor="own-outline" hint="Optional. One point per line.">
          <Textarea id="own-outline" rows={3} value={outline} onChange={(e) => setOutline(e.target.value)} />
        </Field>
        {createIdea.error && <Notice tone="error">{errorText(createIdea.error)}</Notice>}
        <div className="flex gap-2 lg:col-span-2">
          <Button type="submit" loading={createIdea.isPending}>
            Add to the bank
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  )
}

function BankBoard({ personas }: { personas: PersonaOut[] }) {
  const active = personas.find((p) => p.is_active) ?? personas[0]
  const [personaId, setPersonaId] = useState<number>(active?.id ?? 0)
  const [filter, setFilter] = useState<BankFilter>('serious')
  const [search, setSearch] = useState('')
  const [adding, setAdding] = useState(false)
  const [openId, setOpenId] = useState<number | null>(null)
  const bank = useIdeaBank(personaId || null)
  const { updateIdea } = useIdeaLabMutations()

  const ideas = bank.data ?? []
  const shown = filterBank(ideas, filter, search)
  const opened = ideas.find((i) => i.id === openId) ?? null

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted">
        Ideas you saved, from every brainstorm, follow you here as they become posts: Serious, then Generated, Ready and Published, and finally how the post
        did. New brainstorms never repeat an idea that is on file.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        {personas.length > 1 && (
          <Select aria-label="Persona" className="w-auto" value={personaId} onChange={(e) => setPersonaId(Number(e.target.value))}>
            <option value={0}>All personas</option>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        )}
        <Segmented
          label="Show saved ideas"
          options={BANK_FILTERS.map((f) => ({ ...f, count: filterBank(ideas, f.id).length }))}
          value={filter}
          onChange={setFilter}
        />
        <label className="relative">
          <span className="sr-only">Search the bank</span>
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input className="w-56 pl-8" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        <Button className="ml-auto" variant="secondary" icon={<Plus className="size-4" />} onClick={() => setAdding((v) => !v)} aria-expanded={adding}>
          Add your own idea
        </Button>
      </div>

      {adding && (
        <AddIdea
          personaId={personaId || undefined}
          onDone={() => {
            setAdding(false)
            setFilter('serious')
          }}
        />
      )}

      {bank.isLoading && <Spinner />}
      {bank.error && <Notice tone="error">{errorText(bank.error)}</Notice>}
      {bank.data && ideas.length === 0 && (
        <EmptyState icon={<Archive className="size-8" />} title="Nothing saved yet">
          Save ideas from a brainstorm with the bookmark, or add one of your own. They stay here even after the brainstorm is deleted.
        </EmptyState>
      )}
      {ideas.length > 0 && shown.length === 0 && <p className="text-sm text-muted">Nothing here.</p>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((idea) => (
          <IdeaCard
            key={idea.id}
            idea={idea}
            showRank={false}
            onOpen={() => setOpenId(idea.id)}
            onState={(state) => updateIdea.mutate({ id: idea.id, body: { state } })}
          />
        ))}
      </div>

      <IdeaDialog idea={opened} personas={personas} onClose={() => setOpenId(null)} />
    </div>
  )
}

export function BankTab() {
  const { data: personas, isLoading } = usePersonas()
  if (isLoading) return <Spinner />
  if (!personas?.length)
    return (
      <EmptyState icon={<Archive className="size-8" />} title="Create a persona first">
        Saved ideas belong to a persona.
      </EmptyState>
    )
  return <BankBoard personas={personas} />
}
