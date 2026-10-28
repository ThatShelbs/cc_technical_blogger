import type { PersonaOut } from '../api/types.gen'
import { STYLE_DIALS, TOPICS, autoImageCount, personaStyle, shownDials, styleLabel, type DialsState, type Education, type IncludeCode } from '../pages/dials'
import { Field, Input, Select, Slider } from './ui'

/** The post customization controls shared by the new-post page and the post settings dialog (everything but platform). */
export function DialsFields({
  dials,
  onChange,
  persona,
  idPrefix = '',
}: {
  dials: DialsState
  onChange: (patch: Partial<DialsState>) => void
  persona: PersonaOut | undefined
  idPrefix?: string
}) {
  const { targetWords, imageCount, humor, education, includeCode } = shownDials(dials, persona)
  const id = (name: string) => `${idPrefix}${name}`
  return (
    <div className="space-y-5">
      <Slider
        label="Target length"
        min={500}
        max={5000}
        step={100}
        value={targetWords}
        onChange={(v) => onChange({ targetWords: v })}
        format={(v) => `${v.toLocaleString()} words`}
      />
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={imageCount === null}
            onChange={(e) => onChange({ imageCount: e.target.checked ? null : autoImageCount(targetWords) })}
            className="accent-[var(--app-accent)]"
          />
          Choose the number of images automatically
        </label>
        {imageCount !== null && <Slider label="Images" min={2} max={12} value={imageCount} onChange={(v) => onChange({ imageCount: v })} />}
      </div>
      <Slider label="Humor" min={0} max={10} value={humor} onChange={(v) => onChange({ humor: v })} format={(v) => `${v}/10`} />
      {STYLE_DIALS.map(({ key, label, low, high }) => (
        <Slider
          key={key}
          label={label}
          min={0}
          max={10}
          value={dials.style[key] ?? personaStyle(persona, key)}
          onChange={(v) => onChange({ style: { ...dials.style, [key]: v } })}
          format={(v) => styleLabel(v, low, high)}
        />
      ))}
      <Field label="Education level" htmlFor={id('education')}>
        <Select id={id('education')} value={education} onChange={(e) => onChange({ education: e.target.value as Education })}>
          <option value="beginner">Beginner: explain everything</option>
          <option value="intermediate">Intermediate: practical how and why</option>
          <option value="expert">Expert: trade-offs and depth</option>
        </Select>
      </Field>
      <Field label="Audience" hint="Leave empty for your usual readers." htmlFor={id('audience')}>
        <Input
          id={id('audience')}
          value={dials.audience}
          maxLength={200}
          onChange={(e) => onChange({ audience: e.target.value })}
          placeholder="Data science managers at big companies"
        />
      </Field>
      <Field label="Topic" htmlFor={id('topic')}>
        <Select id={id('topic')} value={dials.topic} onChange={(e) => onChange({ topic: e.target.value })}>
          <option value="">Detect automatically</option>
          {TOPICS.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </Select>
      </Field>
      <Field label="Code snippets and prompts" htmlFor={id('code')}>
        <Select id={id('code')} value={includeCode} onChange={(e) => onChange({ includeCode: e.target.value as IncludeCode })}>
          <option value="auto">Where they help</option>
          <option value="yes">Yes, include them</option>
          <option value="no">No code</option>
        </Select>
      </Field>
    </div>
  )
}
