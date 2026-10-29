import { useQueryClient } from '@tanstack/react-query'
import { Palette, RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { keys, useImageMutations, usePersonas, useProjectMutations } from '../../api/hooks'
import type { ProjectOut } from '../../api/types.gen'
import { useJob } from '../../api/useJob'
import { BrandKitFields } from '../../components/BrandKitFields'
import { brandKitOf, isEmptyBrandKit } from '../../lib/brandKit'
import { Button, Card, Dialog, Notice, ProgressBar } from '../../components/ui'

/** This post's image look, and a one-click redraw of every image in it. */
export function BrandKitCard({ project, disabled }: { project: ProjectOut; disabled?: boolean }) {
  const qc = useQueryClient()
  const { update } = useProjectMutations(project.id)
  const { redrawAll } = useImageMutations(project.id)
  const { data: personas = [] } = usePersonas()
  const persona = personas.find((p) => p.id === project.persona_id)
  const [open, setOpen] = useState(false)
  const [kit, setKit] = useState(() => brandKitOf(project.brand_kit))
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob(jobId, () => {
    setJobId(null)
    void qc.invalidateQueries({ queryKey: keys.project(project.id) })
  })
  const saved = brandKitOf(project.brand_kit)
  const redraw = () => redrawAll.mutate(undefined, { onSuccess: (j) => setJobId(j.id) })
  const save = (thenRedraw: boolean) =>
    update.mutate(
      { brand_kit: kit },
      {
        onSuccess: () => {
          setOpen(false)
          if (thenRedraw) redraw()
        },
      },
    )

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-bold">Image brand kit</h2>
        <Button
          size="sm"
          variant="ghost"
          icon={<Palette className="size-4" />}
          disabled={disabled}
          onClick={() => {
            setKit(brandKitOf(project.brand_kit))
            setOpen(true)
          }}
        >
          Edit
        </Button>
      </div>
      {isEmptyBrandKit(saved) ? (
        <p className="text-sm text-muted">Using {persona ? `${persona.name}'s` : 'the persona’s'} visual style.</p>
      ) : (
        <div className="space-y-2 text-sm">
          {saved.style && <p>{saved.style}</p>}
          {saved.palette.length > 0 && (
            <div className="flex gap-1" aria-label="Palette">
              {saved.palette.map((color) => (
                // Swatches show the author's chosen colors, so they are data, not theme tokens.
                <span key={color} className="size-5 rounded border border-line" style={{ background: color }} title={color} />
              ))}
            </div>
          )}
          {(saved.font || saved.motif) && (
            <p className="text-muted">{[saved.font && `Font: ${saved.font}`, saved.motif && `Motif: ${saved.motif}`].filter(Boolean).join(' · ')}</p>
          )}
        </div>
      )}
      {jobId ? (
        <div className="space-y-1">
          <ProgressBar value={job.progress} label="Redrawing images" />
          <p className="text-xs text-muted">{job.message || 'Starting'}</p>
        </div>
      ) : (
        <Button size="sm" variant="secondary" icon={<RefreshCw className="size-4" />} disabled={disabled} loading={redrawAll.isPending} onClick={redraw}>
          Redraw all images
        </Button>
      )}
      {job.status === 'failed' && <Notice tone="error">{job.error}</Notice>}
      {redrawAll.error && <Notice tone="error">{errorText(redrawAll.error)}</Notice>}

      <Dialog open={open} onClose={() => setOpen(false)} title="Image brand kit">
        <div className="space-y-5">
          <BrandKitFields kit={kit} onChange={setKit} idPrefix="post-" personaStyle={persona?.visual_style} />
          {update.error && <Notice tone="error">{errorText(update.error)}</Notice>}
          <div className="flex flex-wrap gap-2">
            <Button variant="flame" icon={<RefreshCw className="size-4" />} loading={update.isPending} onClick={() => save(true)}>
              Save and redraw images
            </Button>
            <Button variant="secondary" loading={update.isPending} onClick={() => save(false)}>
              Save only
            </Button>
          </div>
          <p className="text-xs text-muted">Redrawing keeps each image&rsquo;s idea and gives it the new look. Earlier versions stay under Versions.</p>
        </div>
      </Dialog>
    </Card>
  )
}
