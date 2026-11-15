import { MessageCircleQuestion, RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { useProjectMutations } from '../../api/hooks'
import type { InterviewAnswer, JobOut, ProjectOut } from '../../api/types.gen'
import { Button, Card, Notice, Textarea } from '../../components/ui'

/** The interview questions with a box for each answer; every answer is optional. */
export function InterviewFields({
  answers,
  onChange,
  idPrefix = '',
}: {
  answers: InterviewAnswer[]
  onChange: (answers: InterviewAnswer[]) => void
  idPrefix?: string
}) {
  return (
    <ol className="space-y-4">
      {answers.map((item, index) => (
        <li key={item.question} className="space-y-1.5">
          <label htmlFor={`${idPrefix}interview-${index}`} className="block font-semibold">
            {index + 1}. {item.question}
          </label>
          <Textarea
            id={`${idPrefix}interview-${index}`}
            rows={3}
            value={item.answer ?? ''}
            placeholder="A few lines in your own words, or leave it blank to skip"
            onChange={(e) => onChange(answers.map((a, i) => (i === index ? { ...a, answer: e.target.value } : a)))}
          />
        </li>
      ))}
    </ol>
  )
}

/** Before the first draft: answer (or skip) the questions, then write the post with the answers worked in. */
export function InterviewCard({ project, onStarted }: { project: ProjectOut; onStarted: (job: JobOut) => void }) {
  const { generate, interview } = useProjectMutations(project.id)
  const [answers, setAnswers] = useState<InterviewAnswer[]>(project.interview ?? [])
  const answered = answers.filter((a) => (a.answer ?? '').trim()).length
  const write = (list: InterviewAnswer[]) => generate.mutate({ interview: list }, { onSuccess: onStarted })

  return (
    <Card className="space-y-5">
      <div className="flex items-start gap-3">
        <MessageCircleQuestion className="mt-0.5 size-6 shrink-0 text-accent" aria-hidden />
        <div>
          <h2 className="text-lg font-bold">A few questions before I write</h2>
          <p className="text-sm text-muted">
            Your answers go into the post close to your own words. Skip any you like: I fill the rest in your voice, as always.
          </p>
        </div>
      </div>
      <p className="whitespace-pre-wrap rounded-xl bg-surface-2 p-3 text-sm text-muted">{project.prompt}</p>
      <InterviewFields answers={answers} onChange={setAnswers} />
      {(generate.error || interview.error) && <Notice tone="error">{errorText(generate.error ?? interview.error)}</Notice>}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="flame" onClick={() => write(answers)} loading={generate.isPending}>
          {answered ? `Write the post with ${answered} answer${answered === 1 ? '' : 's'}` : 'Write the post'}
        </Button>
        <Button
          variant="secondary"
          disabled={generate.isPending}
          onClick={() => write(answers.map((a) => ({ ...a, answer: '' })))}
          title="Write the post without the interview"
        >
          Skip the questions
        </Button>
        <Button
          variant="ghost"
          icon={<RefreshCw className="size-4" />}
          loading={interview.isPending}
          onClick={() => interview.mutate(undefined, { onSuccess: onStarted })}
        >
          Different questions
        </Button>
      </div>
    </Card>
  )
}
