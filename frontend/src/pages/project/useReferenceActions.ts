import { useState } from 'react'

import { errorText } from '../../api/client'
import { useReferenceMutations } from '../../api/hooks'
import type { JobOut, ReferenceOut } from '../../api/types.gen'
import type { ReferenceKind } from '../../lib/references'

export interface ReferenceActions {
  /** A text job is running, so references cannot change right now. */
  disabled: boolean
  /** The reference being redrawn, while its job runs. */
  redrawingId: number | null
  redraw: (ref: ReferenceOut, kind?: ReferenceKind) => void
  remove: (ref: ReferenceOut) => void
  revert: (ref: ReferenceOut, index: number) => void
  enrich: (count?: number) => void
  enriching: boolean
  error: string | null
}

/** Reference actions shared by the sidebar card and the chips next to links in the preview; jobs are followed by the page. */
export function useReferenceActions(projectId: number, { busy, onJobStarted }: { busy: boolean; onJobStarted: (job: JobOut) => void }): ReferenceActions {
  const mutations = useReferenceMutations(projectId)
  const [pendingId, setPendingId] = useState<number | null>(null)
  const failed = mutations.redraw.error ?? mutations.remove.error ?? mutations.revert.error ?? mutations.enrich.error
  return {
    disabled: busy || mutations.redraw.isPending || mutations.enrich.isPending,
    redrawingId: busy || mutations.redraw.isPending ? pendingId : null,
    enriching: mutations.enrich.isPending || (busy && pendingId === -1),
    redraw: (ref, kind) => {
      setPendingId(ref.id)
      mutations.redraw.mutate({ id: ref.id, kind }, { onSuccess: onJobStarted })
    },
    remove: (ref) => mutations.remove.mutate(ref.id),
    revert: (ref, index) => mutations.revert.mutate({ id: ref.id, index }),
    enrich: (count) => {
      setPendingId(-1)
      mutations.enrich.mutate(count ? { count } : {}, { onSuccess: onJobStarted })
    },
    error: failed ? errorText(failed) : null,
  }
}
