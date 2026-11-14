import { errorText } from '../../api/client'
import { useProjectMutations } from '../../api/hooks'
import type { ProjectOut } from '../../api/types.gen'
import { Notice } from '../../components/ui'
import { cx } from '../../lib/cx'
import { OUTCOMES, STAGES, type Outcome, type Stage } from '../../lib/stages'

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  disabled,
}: {
  label: string
  options: { id: T; label: string; tone: string; hint?: string }[]
  value: string | null | undefined
  onChange: (id: T) => void
  disabled?: boolean
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap rounded-lg border border-line bg-surface p-0.5">
      {options.map((option) => {
        const selected = option.id === value
        return (
          <button
            key={option.id}
            type="button"
            title={option.hint}
            aria-pressed={selected}
            disabled={disabled}
            onClick={() => !selected && onChange(option.id)}
            className={cx(
              'rounded-md px-2.5 py-1 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-55',
              selected
                ? option.tone === 'flame'
                  ? 'flame-button text-white'
                  : option.tone === 'success'
                    ? 'bg-success-soft text-success'
                    : 'bg-accent-soft text-fg'
                : 'text-muted hover:bg-surface-2 hover:text-fg',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

/** Where the post is (Draft, Ready, Published) and, once published, how it did. */
export function StageControl({ project, disabled }: { project: ProjectOut; disabled?: boolean }) {
  const { update } = useProjectMutations(project.id)
  const published = project.stage === 'published'
  return (
    <div className="flex flex-col items-end gap-2">
      <Segmented<Stage>
        label="Post stage"
        options={STAGES}
        value={project.stage}
        disabled={disabled || update.isPending}
        onChange={(stage) => update.mutate({ stage })}
      />
      {published && (
        <Segmented<Outcome>
          label="How it did"
          options={OUTCOMES}
          value={project.outcome}
          disabled={disabled || update.isPending}
          onChange={(outcome) => update.mutate({ outcome })}
        />
      )}
      {update.error && <Notice tone="error">{errorText(update.error)}</Notice>}
    </div>
  )
}
