import { CheckCircle2, Circle, Eye, FileText, PenLine, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { errorText } from '../api/client'
import { useActivePersona, useAuthStatus, usePersonaMutations, usePersonas, useProjectMutations, useProjects } from '../api/hooks'
import { Badge, Button, Card, EmptyState, Notice, PageHeader, Spinner } from '../components/ui'
import { cx } from '../lib/cx'
import { outcomeInfo, STAGES, stageInfo, type Stage } from '../lib/stages'

function SetupChecklist() {
  const auth = useAuthStatus()
  const { data: persona, isLoading } = useActivePersona()
  if (auth.isLoading || isLoading) return null
  const steps = [
    { done: !!auth.data?.signed_in, label: 'Connect Claude', to: '/settings' },
    { done: !!persona, label: 'Create a persona', to: '/personas' },
    { done: (persona?.own_samples ?? 0) > 0, label: 'Add posts you wrote', to: persona ? `/personas/${persona.id}` : '/personas' },
    { done: !!persona?.voice_profile_version, label: 'Generate your voice profile', to: persona ? `/personas/${persona.id}` : '/personas' },
  ]
  if (steps.every((s) => s.done)) return null
  return (
    <Card className="mb-8 border-accent/60">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Finish setting up</h2>
          <p className="text-sm text-muted">A few minutes of setup, then every post sounds like you.</p>
        </div>
        <Link to="/welcome">
          <Button variant="flame">Open the setup guide</Button>
        </Link>
      </div>
      <ol className="mt-4 grid gap-2 sm:grid-cols-2">
        {steps.map((step) => (
          <li key={step.label}>
            <Link to={step.to} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-2">
              {step.done ? <CheckCircle2 className="size-5 text-success" aria-hidden /> : <Circle className="size-5 text-muted" aria-hidden />}
              <span className={step.done ? 'text-muted line-through' : 'font-semibold'}>{step.label}</span>
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  )
}

// Generation states that take over the card's badge; otherwise it shows the post's stage.
const WORKING: Record<string, { label: string; tone: 'accent' | 'danger' }> = {
  generating: { label: 'Writing…', tone: 'accent' },
  error: { label: 'Needs attention', tone: 'danger' },
}

export function ProjectsPage() {
  const { data: projects, isLoading } = useProjects()
  const { remove } = useProjectMutations()
  const { data: personas } = usePersonas()
  const { createExample } = usePersonaMutations()
  const [filter, setFilter] = useState<Stage | 'all'>('all')
  const shown = projects?.filter((p) => filter === 'all' || p.stage === filter)
  const examplePersonas = new Set(personas?.filter((p) => p.is_example).map((p) => p.id))
  const hasVoice = !!personas?.some((p) => p.is_active && !p.is_example && p.voice_profile_version)
  const newPost = (
    <Link to="/projects/new">
      <Button variant="flame" icon={<PenLine className="size-4" />}>
        New post
      </Button>
    </Link>
  )
  return (
    <>
      <PageHeader
        title="Posts"
        subtitle="One project per article. Give Proseferno a prompt or outline and it writes the post in your voice."
        actions={newPost}
      />
      <SetupChecklist />
      {isLoading && <Spinner />}
      {createExample.error && (
        <div className="mb-6">
          <Notice tone="error">{errorText(createExample.error)}</Notice>
        </div>
      )}
      {projects?.length === 0 && (
        <EmptyState
          icon={<FileText className="size-8" />}
          title="No posts yet"
          action={
            <div className="flex flex-wrap items-center justify-center gap-3">
              {hasVoice ? (
                newPost
              ) : (
                <Link to="/welcome">
                  <Button variant="flame">Set up my voice</Button>
                </Link>
              )}
              <Button variant="secondary" icon={<Eye className="size-4" />} loading={createExample.isPending} onClick={() => createExample.mutate()}>
                See an example post
              </Button>
            </div>
          }
        >
          {hasVoice
            ? 'Start with a sentence or a bullet-point outline. Everything else has smart defaults.'
            : 'Set up your voice from your own writing, or look at a finished example first. The example needs no Claude connection.'}
        </EmptyState>
      )}
      {!!projects?.length && (
        <div role="group" aria-label="Show posts" className="mb-5 inline-flex flex-wrap rounded-lg border border-line bg-surface p-0.5">
          {[{ id: 'all' as const, label: 'All' }, ...STAGES].map((option) => (
            <button
              key={option.id}
              type="button"
              aria-pressed={filter === option.id}
              onClick={() => setFilter(option.id)}
              className={cx(
                'rounded-md px-3 py-1 text-sm font-semibold',
                filter === option.id ? 'bg-accent-soft text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg',
              )}
            >
              {option.label} ({option.id === 'all' ? projects.length : projects.filter((p) => p.stage === option.id).length})
            </button>
          ))}
        </div>
      )}
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {shown?.map((project) => {
          const status = WORKING[project.status] ?? stageInfo(project.stage)
          const outcome = project.stage === 'published' ? outcomeInfo(project.outcome) : undefined
          return (
            <Card key={project.id} padded={false} className="group flex flex-col overflow-hidden">
              <Link to={`/projects/${project.id}`} className="block aspect-[16/9] bg-sunken">
                {project.thumbnail_url ? (
                  <img src={project.thumbnail_url} alt="" className="size-full object-cover" />
                ) : (
                  <div className="flex size-full items-center justify-center">
                    <img src="/logo-mark.svg" alt="" className="size-16 opacity-60" />
                  </div>
                )}
              </Link>
              <div className="flex flex-1 flex-col gap-2 p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5">
                    <Badge tone={status.tone}>{status.label}</Badge>
                    {outcome && outcome.id !== 'too_early' && <Badge tone={outcome.tone}>{outcome.label}</Badge>}
                    {examplePersonas.has(project.persona_id) && <Badge tone="accent">Example</Badge>}
                    {project.ab_status === 'voting' && <Badge tone="flame">A/B: pick a winner</Badge>}
                    {project.ab_status === 'decided' && <Badge tone="accent">A/B result</Badge>}
                  </span>
                  <span className="text-xs text-muted">{new Date(project.updated_at).toLocaleDateString()}</span>
                </div>
                <Link to={`/projects/${project.id}`} className="line-clamp-2 font-bold hover:underline">
                  {project.title || project.prompt}
                </Link>
                <div className="mt-auto flex items-center justify-between pt-2 text-xs text-muted">
                  <span>as {project.persona_name}</span>
                  <button
                    type="button"
                    className="rounded-md p-1.5 opacity-70 hover:bg-danger-soft hover:text-danger hover:opacity-100"
                    aria-label={`Delete ${project.title || 'post'}`}
                    onClick={() => {
                      if (confirm('Delete this post and its images?')) remove.mutate(project.id)
                    }}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </>
  )
}
