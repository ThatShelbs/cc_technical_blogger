interface PlannedSection {
  heading?: string
  key_points?: string[]
}

/** Claude's plan for a post as an editable bullet outline (title, hook, sections, closing). */
export function planOutline(plan: Record<string, unknown> | null | undefined): string {
  if (!plan) return ''
  const lines: string[] = []
  const title = String(plan.chosen_title ?? '').trim()
  if (title) lines.push(title)
  const hook = String(plan.hook ?? '').trim()
  if (hook) lines.push(`- opening: ${hook}`)
  for (const section of (plan.sections as PlannedSection[] | undefined) ?? []) {
    if (!section.heading) continue
    lines.push(`- ${section.heading}`)
    for (const point of section.key_points ?? []) lines.push(`  - ${point}`)
  }
  const closing = String(plan.closing ?? '').trim()
  if (closing) lines.push(`- close: ${closing}`)
  return lines.join('\n')
}
