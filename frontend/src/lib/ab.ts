/** A/B Test Mode helpers: names and the parts an author can take from the other post. */

export type ABSide = 'left' | 'right'
export type ABPart = 'title' | 'opener' | 'closer' | 'hero' | 'meme' | 'image_style'

/** Positions only: nothing on screen says which post is which until the author has chosen. */
export const SIDE_NAME: Record<ABSide, string> = { left: 'Post 1', right: 'Post 2' }

export const otherSide = (side: ABSide): ABSide => (side === 'left' ? 'right' : 'left')

export const PARTS: { id: ABPart; label: string; hint: string }[] = [
  { id: 'title', label: 'Title & subtitle', hint: 'Its headline and the line under it.' },
  { id: 'opener', label: 'Opener', hint: 'Everything before the first section heading.' },
  { id: 'closer', label: 'Closer', hint: 'The last section, before any reading list and the meme.' },
  { id: 'hero', label: 'Hero image', hint: 'The opening image and thumbnail.' },
  { id: 'meme', label: 'Closing meme', hint: 'The joke at the very end.' },
  { id: 'image_style', label: 'Image style', hint: 'Its look: the other images are redrawn in it.' },
]

/** Order of the tweak groups in the reveal, as the author thinks about a post. */
export const TWEAK_GROUPS = ['Settings', 'Formula', 'Voice', 'Principles', 'Examples', 'Title', 'Images']
