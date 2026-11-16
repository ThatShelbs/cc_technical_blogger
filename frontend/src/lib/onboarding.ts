import type { ArchetypeOut, PersonaOut } from '../api/types.gen'

/** The setup steps, shared by the welcome guide and the checklist on the Posts page. */
export const SETUP_STEPS = [
  { id: 'connect', label: 'Connect Claude' },
  { id: 'images', label: 'Images' },
  { id: 'persona', label: 'Persona' },
  { id: 'voice', label: 'Your voice' },
  { id: 'profile', label: 'Voice profile' },
] as const

export type SetupStepId = (typeof SETUP_STEPS)[number]['id']

/** A persona has something to learn a voice from: its own posts, or a voice the author chose to start from. */
export function hasVoiceStart(persona: Pick<PersonaOut, 'own_samples' | 'source'> | undefined): boolean {
  return !!persona && (persona.own_samples > 0 || persona.source !== 'samples')
}

export function setupDone(opts: { signedIn: boolean; demo: boolean; persona: PersonaOut | undefined }): Record<SetupStepId, boolean> {
  const { signedIn, demo, persona } = opts
  return {
    connect: signedIn || demo,
    images: true,
    persona: !!persona,
    voice: hasVoiceStart(persona),
    profile: !!persona?.voice_profile_version,
  }
}

/** One line saying where a persona's voice comes from, or '' when it learns from its own posts only. */
export function sourceSummary(persona: Pick<PersonaOut, 'source' | 'source_spec'>, archetypes: ArchetypeOut[] = []): string {
  const spec = persona.source_spec as { archetype?: string; writers?: { name: string }[]; answers?: unknown[] }
  const name = (id?: string) => archetypes.find((a) => a.id === id)?.name
  switch (persona.source) {
    case 'archetype':
      return `Starts from ${name(spec.archetype) ?? 'a chosen voice'}`
    case 'random':
      return `A surprise voice: ${name(spec.archetype) ?? 'random pick'}`
    case 'blend':
      return `Inspired by ${(spec.writers ?? []).map((w) => w.name).join(', ') || 'writers you named'}`
    case 'interview':
      return 'Built from your interview answers'
    default:
      return ''
  }
}
