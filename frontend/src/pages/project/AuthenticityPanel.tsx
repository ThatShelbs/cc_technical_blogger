import { RefreshCw, ScanSearch, Wand2 } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { useProjectMutations } from '../../api/hooks'
import type { ProjectOut } from '../../api/types.gen'
import { Button, Card, Dialog, Notice } from '../../components/ui'
import { cx } from '../../lib/cx'

export interface Signal {
  id: string
  label: string
  penalty: number
  detail: string
}

export interface FlaggedPassage {
  quote: string
  reason: string
  suggestion: string
  source: 'scan' | 'judge'
}

export interface AuthenticityReport {
  score: number
  band: 'human' | 'mostly_human' | 'mixed' | 'likely_ai'
  label: string
  scan_score: number
  judge_score: number | null
  verdict: string
  human_signals: string[]
  ai_signals: string[]
  signals: Signal[]
  flagged: FlaggedPassage[]
  judge_error: string | null
  checked_at: string
}

const BAND_TONE: Record<AuthenticityReport['band'], string> = {
  human: 'text-success',
  mostly_human: 'text-success',
  mixed: 'text-accent',
  likely_ai: 'text-danger',
}

/** AI-generation detection: 100 = reads as authentic human prose, 0 = almost certainly flagged as AI. */
export function AuthenticityPanel({ project, onEdited }: { project: ProjectOut; onEdited?: () => void }) {
  const report = project.authenticity as AuthenticityReport | null
  const { checkAuthenticity, rewrite } = useProjectMutations(project.id)
  const [open, setOpen] = useState(false)
  const [rewriting, setRewriting] = useState<string | null>(null)

  const humanize = (passage: FlaggedPassage) => {
    setRewriting(passage.quote)
    rewrite.mutate(
      {
        selection: passage.quote,
        instruction:
          `Rewrite this so it reads as genuinely human and unmistakably mine, removing the AI tell (${passage.reason}). ${passage.suggestion}`.trim(),
      },
      { onSettled: () => setRewriting(null), onSuccess: () => onEdited?.() },
    )
  }

  return (
    <Card className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-bold">Reads as human</h2>
        <Button
          size="sm"
          variant="ghost"
          icon={<RefreshCw className="size-4" />}
          loading={checkAuthenticity.isPending}
          onClick={() => checkAuthenticity.mutate()}
          title="Re-check the current text"
        >
          Re-check
        </Button>
      </div>
      {report ? (
        <>
          <div>
            <p className={cx('text-3xl font-extrabold tabular-nums', BAND_TONE[report.band])}>
              {report.score}
              <span className="text-base font-semibold text-muted">/100</span>
            </p>
            <p className="text-sm font-semibold">{report.label}</p>
            <div
              className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2"
              role="meter"
              aria-valuenow={report.score}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Human score"
            >
              <div className="flame-bar h-full" style={{ width: `${report.score}%` }} />
            </div>
            <p className="mt-1 text-xs text-muted">
              AI-generation detection. 100 = authentic human prose, 0 = almost certainly flagged. Scan {report.scan_score}
              {report.judge_score !== null ? ` · Claude judge ${report.judge_score}` : ''}.
            </p>
          </div>
          {report.verdict && <p className="text-sm">{report.verdict}</p>}
          {report.judge_error && <Notice tone="warn">The Claude judge was unavailable, so this is the scan alone.</Notice>}
          <Button size="sm" variant="secondary" icon={<ScanSearch className="size-4" />} onClick={() => setOpen(true)}>
            Full report{report.flagged.length ? ` · ${report.flagged.length} flagged` : ''}
          </Button>
        </>
      ) : (
        <p className="text-sm text-muted">Check how likely AI detectors are to flag this post, and fix the passages they would catch.</p>
      )}
      {checkAuthenticity.error && <Notice tone="error">{errorText(checkAuthenticity.error)}</Notice>}

      {report && (
        <Dialog open={open} onClose={() => setOpen(false)} title={`AI-detection report: ${report.score}/100`} wide>
          <div className="space-y-5 text-sm">
            <p>
              <span className={cx('font-bold', BAND_TONE[report.band])}>{report.label}.</span> {report.verdict}
            </p>
            {(report.human_signals.length > 0 || report.ai_signals.length > 0) && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="mb-1 font-semibold">Reads human</p>
                  <ul className="list-disc space-y-0.5 pl-5">
                    {report.human_signals.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 font-semibold">Reads machine-made</p>
                  <ul className="list-disc space-y-0.5 pl-5">
                    {report.ai_signals.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            <div>
              <p className="mb-2 font-semibold">Scan signals (calibrated to your own posts)</p>
              <ul className="space-y-1.5">
                {report.signals.map((s) => (
                  <li key={s.id} className="flex items-start gap-3">
                    <span className={cx('w-12 shrink-0 text-right font-semibold tabular-nums', s.penalty > 0 ? 'text-danger' : 'text-success')}>
                      {s.penalty > 0 ? `-${Math.round(s.penalty)}` : 'OK'}
                    </span>
                    <span>
                      <span className="font-semibold">{s.label}.</span> <span className="text-muted">{s.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            {report.flagged.length > 0 && (
              <div>
                <p className="mb-2 font-semibold">Passages a detector would catch</p>
                <ul className="space-y-3">
                  {report.flagged.map((f) => {
                    const present = project.markdown.includes(f.quote)
                    return (
                      <li key={f.quote} className="rounded-xl border border-line p-3">
                        <blockquote className="border-l-4 border-accent pl-3 italic">{f.quote}</blockquote>
                        <p className="mt-2">
                          <span className="font-semibold">{f.reason}.</span> {f.suggestion}
                        </p>
                        <div className="mt-2 flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            icon={<Wand2 className="size-4" />}
                            disabled={!present || (rewrite.isPending && rewriting !== f.quote)}
                            loading={rewriting === f.quote}
                            onClick={() => humanize(f)}
                            title={present ? 'Rewrite this passage in your voice' : 'This passage has already changed'}
                          >
                            {present ? 'Humanize' : 'Already changed'}
                          </Button>
                          <span className="text-xs text-muted">Found by {f.source === 'judge' ? 'the Claude judge' : 'the scan'}</span>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}
            {rewrite.error && <Notice tone="error">{errorText(rewrite.error)}</Notice>}
            <p className="text-xs text-muted">
              Checked {new Date(report.checked_at).toLocaleString()}. After edits, choose Re-check. No detector is perfect: treat this as an editor&apos;s
              second opinion.
            </p>
          </div>
        </Dialog>
      )}
    </Card>
  )
}
