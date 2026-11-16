import { useSearchParams } from 'react-router'

import { Tabs } from '../../components/tabs'
import { panelDomId, tabDomId } from '../../lib/tabs'
import { PageHeader } from '../../components/ui'
import { BankTab } from './BankTab'
import { IdeasTab } from './IdeasTab'
import { ResearchTab } from './ResearchTab'
import { SourcesTab } from './SourcesTab'

const TABS = [
  { id: 'ideas', label: 'Ideas' },
  { id: 'bank', label: 'Saved bank' },
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
      <Tabs tabs={TABS} value={tab} onChange={open} label="Idea Lab" idPrefix="idea" className="mb-6" />
      <div role="tabpanel" id={panelDomId('idea', tab)} aria-labelledby={tabDomId('idea', tab)}>
        {tab === 'ideas' && <IdeasTab openResearch={() => open('research')} />}
        {tab === 'bank' && <BankTab />}
        {tab === 'research' && <ResearchTab openSources={() => open('sources')} />}
        {tab === 'sources' && <SourcesTab />}
      </div>
    </>
  )
}
