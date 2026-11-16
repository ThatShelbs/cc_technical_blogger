import { RefreshCw, ScanSearch, Wand2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

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

export type FlagSource = 'scan' | 'judge' | 'detector' | 'twin' | 'texture'

export interface FlaggedPassage {
  quote: string
  reason: string
  suggestion: string
  source: FlagSource
}

export interface DetectorModel {
  id: string
  label: string
  model: string
  value: number
  author_low: number
  author_high: number
  calibrated: boolean
  score: number
  verdict: string
}

export interface TwinPair {
  quote: string
  role_label: string
  score: number
  caught: boolean
  ai_certainty: number
  giveaway: string
}

export interface AuthenticityReport {
  score: number
  band: 'human' | 'mostly_human' | 'mixed' | 'likely_ai'
  label: string
  scan_score: number
  judge_score: number | null
  judge_kind?: 'twin' | 'judge' | null
  texture_score?: number | null
  detector_score?: number | null
  verdict: string
  human_signals: string[]
  ai_signals: string[]
  signals: Signal[]
  texture?: { gaps: Signal[] } | null
  twin?: { score: number | null; caught: number; total: number; pairs: TwinPair[] } | null
  detectors?: { score: number | null; models: DetectorModel[] } | null
  flagged: FlaggedPassage[]
  judge_error: string | null
  detector_error?: string | null
  checked_at: string
}

const BAND_TONE: Record<AuthenticityReport['band'], string> = {
  human: 'text-success',
  mostly_human: 'text-success',
  mixed: 'text-accent',
  likely_ai: 'text-danger',
}

const SOURCE_LABEL: Record<FlagSource, string> = {
  detector: 'the detector models',
  twin: 'the twin test',
  judge: 'the Claude judge',
  texture: 'the texture check',
  scan: 'the scan',
}

function parts(report: AuthenticityReport): string {
  const out: string[] = []
  if (report.detector_score != null) out.push(`Detector models ${report.detector_score}`)
  if (report.judge_score != null) out.push(`${report.judge_kind === 'twin' ? 'Twin test' : 'Claude judge'} ${report.judge_score}`)
  out.push(`Scan ${report.scan_score}`)
  if (report.texture_score != null) out.push(`Texture ${report.texture_score}`)
  return out.join(' · ')
}

function ScoreChip({ score }: { score: number }) {
  const tone = score >= 85 ? 'text-success' : score >= 55 ? 'text-accent' : 'text-danger'
  return <span className={cx('w-12 shrink-0 text-right font-semibold tabular-nums', tone)}>{score}</span>
}

/** AI-generation detection: 100 = reads as authentic human prose, 0 = almost certainly flagged as AI. */
export function AuthenticityPanel({ project, onEdited }: { project: ProjectOut; onEdited?: () => void }) {
  const report = project.authenticity as AuthenticityReport | null
  const { checkAuthenticity, rewrite } = useProjectMutations(project.id)
  const [open, setOpen] = useState(false)
  const [rewriting, setRewriting] = useState<string | null>(null)

  const humanize = (quote: string, reason: string, suggestion = '') => {
    setRewriting(quote)
    rewrite.mutate(
      { selection: quote, action: 'humanize', instruction: `${reason}. ${suggestion}`.trim() },
      { onSettled: () => setRewriting(null), onSuccess: () => onEdited?.() },
    )
  }

  const humanizeButton = (quote: string, reason: string, suggestion = '') => {
    const present = project.markdown.includes(quote)
    return (
      <Button
        size="sm"
        variant="secondary"
        icon={<Wand2 className="size-4" />}
        disabled={!present || (rewrite.isPending && rewriting !== quote)}
        loading={rewriting === quote}
        onClick={() => humanize(quote, reason, suggestion)}
        title={present ? 'Rewrite this passage so it reads like you' : 'This passage has already changed'}
      >
        {present ? 'Humanize' : 'Already changed'}
      </Button>
    )
  }

  const models = report?.detectors?.models ?? []
  const twin = report?.twin
  const gaps = (report?.texture?.gaps ?? []).filter((g) => g.penalty > 0)

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
            <p className="mt-1 text-xs text-muted">Compared with your own posts. {parts(report)}.</p>
          </div>
          {report.verdict && <p className="text-sm">{report.verdict}</p>}
          {report.detector_score == null && !report.detector_error && (
            <p className="text-xs text-muted">
              No detector is selected. Pick one in{' '}
              <Link to="/settings" className="font-semibold underline">
                Settings
              </Link>
              .
            </p>
          )}
          {report.detector_error && <Notice tone="warn">The detector models could not run this time: {report.detector_error}</Notice>}
          {report.judge_error && <Notice tone="warn">Claude&apos;s check was unavailable, so this score leaves it out.</Notice>}
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

            {models.length > 0 && (
              <div>
                <p className="mb-2 font-semibold">Detectors (run on this computer)</p>
                <ul className="space-y-1.5">
                  {models.map((m) => (
                    <li key={m.id} className="flex items-start gap-3">
                      <ScoreChip score={m.score} />
                      <span>
                        <span className="font-semibold">{m.label}.</span> {m.verdict}.{' '}
                        <span className="text-muted">
                          {m.id === 'classifier' ? `AI probability ${Math.round(m.value * 100)}%` : `Score ${m.value.toFixed(2)}`}
                          {m.calibrated
                            ? `; your posts: ${m.id === 'classifier' ? `${Math.round(m.author_low * 100)}-${Math.round(m.author_high * 100)}%` : `${m.author_low.toFixed(2)} to ${m.author_high.toFixed(2)}`}`
                            : '; compared with typical human writing (add your own posts to compare with yours)'}
                          . <code className="text-xs">{m.model}</code>
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {twin && twin.total > 0 && (
              <div>
                <p className="mb-1 font-semibold">
                  Twin test: Claude told {twin.caught} of {twin.total} passages apart from your own writing
                </p>
                <p className="mb-2 text-xs text-muted">
                  Each passage was shown blind next to a real paragraph of yours that does the same job. Passed means Claude could not tell which one you wrote.
                </p>
                <ul className="space-y-3">
                  {twin.pairs.map((pair) => (
                    <li key={pair.quote} className="rounded-xl border border-line p-3">
                      <p className="mb-1 text-xs font-semibold">
                        <span className={pair.caught ? 'text-danger' : 'text-success'}>{pair.caught ? 'Caught' : 'Passed'}</span>{' '}
                        <span className="text-muted">· {pair.role_label}</span>
                      </p>
                      <blockquote className="line-clamp-3 border-l-4 border-accent pl-3 italic">{pair.quote}</blockquote>
                      {pair.caught && (
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          {pair.giveaway && <p className="grow">Giveaway: {pair.giveaway}</p>}
                          {humanizeButton(pair.quote, pair.giveaway || 'Claude could tell this from my writing')}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(report.human_signals.length > 0 || (report.judge_kind !== 'twin' && report.ai_signals.length > 0)) && (
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

            {gaps.length > 0 && (
              <div>
                <p className="mb-2 font-semibold">Texture compared with your posts</p>
                <ul className="space-y-1.5">
                  {gaps.map((g) => (
                    <li key={g.id} className="flex items-start gap-3">
                      <span className="w-12 shrink-0 text-right font-semibold tabular-nums text-danger">-{Math.round(g.penalty)}</span>
                      <span>
                        <span className="font-semibold">{g.label}.</span> <span className="text-muted">{g.detail}</span>
                      </span>
                    </li>
                  ))}
                </ul>
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
                <p className="mb-2 font-semibold">Passages that read as machine-made</p>
                <ul className="space-y-3">
                  {report.flagged
                    .filter((f) => f.source !== 'twin')
                    .map((f) => (
                      <li key={f.quote} className="rounded-xl border border-line p-3">
                        <blockquote className="border-l-4 border-accent pl-3 italic">{f.quote}</blockquote>
                        <p className="mt-2">
                          <span className="font-semibold">{f.reason}.</span> {f.suggestion}
                        </p>
                        <div className="mt-2 flex items-center gap-2">
                          {humanizeButton(f.quote, f.reason, f.suggestion)}
                          <span className="text-xs text-muted">Found by {SOURCE_LABEL[f.source] ?? 'the scan'}</span>
                        </div>
                      </li>
                    ))}
                </ul>
              </div>
            )}
            {rewrite.error && <Notice tone="error">{errorText(rewrite.error)}</Notice>}
            <p className="text-xs text-muted">
              Checked {new Date(report.checked_at).toLocaleString()}. After edits, choose Re-check. The models here are open-source detectors, not the one a
              platform uses: they read the same machine texture, but treat the score as a strong second opinion, not a guarantee.
            </p>
          </div>
        </Dialog>
      )}
    </Card>
  )
}
