/**
 * Meeting notice (finale): "You're in a Google Meet call — want me to listen?"
 *
 * While Watching (and only if the user kept the "notice meetings" scope on), main reads the
 * *names* of open windows every few seconds. No pixels, no audio: a window name like
 * "Meet - abc-defg-hij - Google Chrome" is enough to know a call started. Listening still
 * needs a separate yes for that call.
 */

import { desktopCapturer } from 'electron'

import type { MeetingInfo } from '../shared/contracts'
import { detectMeeting } from './meetingRules'

export { detectMeeting, sameMeeting } from './meetingRules'

/**
 * Polls window names while active. Emits on change; a meeting only "ends" after two empty polls
 * in a row (window titles flicker while tabs switch).
 */
export class MeetingWatcher {
  private timer: ReturnType<typeof setInterval> | null = null
  private current: MeetingInfo | null = null
  private misses = 0
  private busy = false

  constructor(
    private readonly onChange: (meeting: MeetingInfo | null) => void,
    private readonly intervalMs = 3000,
  ) {}

  get meeting(): MeetingInfo | null {
    return this.current
  }

  start(): void {
    if (this.timer) return
    void this.poll()
    this.timer = setInterval(() => void this.poll(), this.intervalMs)
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
    if (this.current) {
      this.current = null
      this.onChange(null)
    }
    this.misses = 0
  }

  private async poll(): Promise<void> {
    if (this.busy) return
    this.busy = true
    try {
      const sources = await desktopCapturer.getSources({
        types: ['window'],
        thumbnailSize: { width: 0, height: 0 },
        fetchWindowIcons: false,
      })
      const found = detectMeeting(sources.map((source) => source.name))
      if (found) {
        this.misses = 0
        // Same app, title changed (e.g. participant name): keep the original notice.
        if (!this.current || this.current.app !== found.app) {
          this.current = found
          this.onChange(found)
        }
      } else if (this.current) {
        this.misses += 1
        if (this.misses >= 2) {
          this.current = null
          this.misses = 0
          this.onChange(null)
        }
      }
    } catch {
      // No permission yet, or the window list is unavailable: stay quiet, try again next tick.
    } finally {
      this.busy = false
    }
  }
}
