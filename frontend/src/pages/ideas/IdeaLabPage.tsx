import { useSearchParams } from 'react-router'

import { PageHeader } from '../../components/ui'
import { cx } from '../../lib/cx'
import { IdeasTab } from './IdeasTab'
import { ResearchTab } from './ResearchTab'
import { SourcesTab } from './SourcesTab'

const TABS = [
  { id: 'ideas', label: 'Ideas' },
  { id: 'research', label: 'Research' },
  { id: 'sources', label: 'Sources' },
] as const
type TabId = (typeof TABS)[number]['id']

export function IdeaLabPage() {
  const [params, setParams] = useSearchParams()
  const tab: TabId = TABS.some((t) => t.id === params.get('tab')) ? (params.get('tab') as TabId) : 'ideas'
  const open = (next: TabId) =>
    setParams(
      (current) => {
        const updated = new URLSearchParams(current)
        if (next === 'ideas') updated.delete('tab')
        else updated.set('tab', next)
        return updated
      },
      { replace: true },
    )
  return (
    <>
      <PageHeader
        title="Idea Lab"
        subtitle="What to write next: ideas from what is happening in the field and from your own portfolio, each with a title, brief and outline."
      />
      <div role="tablist" aria-label="Idea Lab" className="mb-6 flex gap-1 border-b border-line">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`idea-tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`idea-panel-${item.id}`}
            onClick={() => open(item.id)}
            className={cx(
              '-mb-px border-b-2 px-4 py-2 text-sm font-semibold',
              tab === item.id ? 'border-accent text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`idea-panel-${tab}`} aria-labelledby={`idea-tab-${tab}`}>
        {tab === 'ideas' && <IdeasTab openResearch={() => open('research')} />}
        {tab === 'research' && <ResearchTab openSources={() => open('sources')} />}
        {tab === 'sources' && <SourcesTab />}
      </div>
    </>
  )
}
