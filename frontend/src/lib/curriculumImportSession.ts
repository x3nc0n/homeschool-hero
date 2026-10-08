import type { CurriculumAiImportSession, CurriculumDuplicateMatch } from '@/types/api'

export const CURRICULUM_POLL_MS = 2000

export function duplicatesAcknowledged(matches: CurriculumDuplicateMatch[], ids: number[]) {
  return matches.every((match) => ids.includes(match.id))
}

export class CurriculumSessionRunner {
  private generation = 0
  private id: string | null = null
  private timer: ReturnType<typeof setTimeout> | null = null
  private wake: (() => void) | null = null

  private remove: (id: string) => Promise<void>
  constructor(remove: (id: string) => Promise<void>) { this.remove = remove }

  async cancel() {
    const generation = ++this.generation
    if (this.timer) clearTimeout(this.timer)
    this.wake?.()
    this.timer = null
    this.wake = null
    const id = this.id
    this.id = null
    if (id) {
      try { await this.remove(id) }
      catch (error) {
        if (this.generation === generation && !this.id) this.id = id
        throw error
      }
    }
  }

  confirmed() {
    this.id = null
  }

  async run(
    create: () => Promise<CurriculumAiImportSession>,
    get: (id: string) => Promise<CurriculumAiImportSession>,
    update: (session: CurriculumAiImportSession) => void,
  ): Promise<CurriculumAiImportSession | null> {
    const cleanup = this.cancel()
    const generation = this.generation
    await cleanup
    if (generation !== this.generation) return null
    let session = await create()
    if (generation !== this.generation) {
      await this.remove(session.id)
      return null
    }
    this.id = session.id
    while (generation === this.generation) {
      if (Date.parse(session.expires_at) <= Date.now() && session.status !== 'confirmed') {
        session = { ...session, status: 'expired' }
      }
      update(session)
      if (session.status !== 'processing') return session
      await new Promise<void>((resolve) => {
        this.wake = resolve
        this.timer = setTimeout(resolve, CURRICULUM_POLL_MS)
      })
      this.timer = null
      this.wake = null
      if (generation !== this.generation) return null
      session = await get(session.id)
    }
    return null
  }
}
