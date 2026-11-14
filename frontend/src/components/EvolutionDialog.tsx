import { useState } from 'react'

import { errorText } from '../api/client'
import { useEvolutionMutations } from '../api/hooks'
import type { EvolutionOut } from '../api/types.gen'
import { useJob } from '../api/useJob'
import { KIND_LABEL, TARGET_LABEL } from '../lib/stages'
import { Badge, Button, Dialog, Notice, ProgressBar } from './ui'

/** Review a proposal learned from a post: tick the changes to keep, then apply them to the persona. */
export function EvolutionDialog({
  evolution,
  personaId,
  projectId,
  open,
  onClose,
}: {
  evolution: EvolutionOut
  personaId: number
  projectId?: number
  open: boolean
  onClose: () => void
}) {
  const { apply, dismiss, refresh } = useEvolutionMutations(personaId, projectId)
  const [selected, setSelected] = useState<Set<string>>(() => new Set(evolution.items.map((i) => i.id)))
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob(jobId, (state) => {
    refresh()
    if (state.status === 'succeeded') onClose()
  })
  const running = !!jobId && job.status !== 'succeeded' && job.status !== 'failed'
  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const profileCount = evolution.items.filter((i) => selected.has(i.id) && i.target === 'profile').length

  return (
    <Dialog open={open} onClose={onClose} title={`${KIND_LABEL[evolution.kind] ?? 'Suggestions'}: ${evolution.project_title}`} wide>
      <div className="space-y-4">
        {evolution.summary && <p className="text-sm">{evolution.summary}</p>}
        <ul className="space-y-2">
          {evolution.items.map((item) => (
            <li key={item.id}>
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3 text-sm hover:bg-surface-2">
                <input
                  type="checkbox"
                  className="mt-1 size-4 accent-[var(--app-accent)]"
                  checked={selected.has(item.id)}
                  onChange={() => toggle(item.id)}
                  disabled={running}
                />
                <span className="min-w-0 flex-1 space-y-1">
                  <span className="flex flex-wrap items-center gap-1.5">
                    <Badge tone={item.target === 'profile' ? 'accent' : 'success'}>{TARGET_LABEL[item.target] ?? item.target}</Badge>
                    {item.area && <span className="text-xs text-muted">{item.area}</span>}
                  </span>
                  <span className="block font-semibold">{item.change}</span>
                  {item.evidence && <span className="block text-muted">{item.evidence}</span>}
                </span>
              </label>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">
          Voice profile changes are written into a new voice profile version, so you can go back to the old one any time. Playbook entries are moves that
          worked; the writer uses them where they fit.
        </p>
        {running && (
          <div className="space-y-1">
            <ProgressBar value={job.progress} label="Applying changes" />
            <p className="text-xs text-muted">{job.message || 'Starting'}</p>
          </div>
        )}
        {job.status === 'failed' && <Notice tone="error">{job.error || 'Could not apply the changes.'}</Notice>}
        {(apply.error || dismiss.error) && <Notice tone="error">{errorText(apply.error ?? dismiss.error)}</Notice>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" disabled={running} loading={dismiss.isPending} onClick={() => dismiss.mutate(evolution.id, { onSuccess: onClose })}>
            Dismiss all
          </Button>
          <Button
            variant="flame"
            disabled={selected.size === 0 || running}
            loading={apply.isPending || running}
            onClick={() => apply.mutate({ id: evolution.id, itemIds: [...selected] }, { onSuccess: (j) => setJobId(j.id) })}
          >
            {profileCount > 0 ? `Apply ${selected.size} (new voice profile version)` : `Apply ${selected.size}`}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
