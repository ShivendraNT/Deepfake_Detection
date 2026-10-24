/**
 * CaptureApp — the hidden 1×1 capture window (`?view=capture`).
 *
 * Main tells it exactly when to start and stop (`capture:command`), only after the user said
 * yes to listening to *this* call. Two sources:
 *
 *   loopback — system audio (the other person's voice from Meet/Zoom/Teams/WhatsApp) through
 *              `getDisplayMedia`; main answers with `audio: 'loopback'`. The video track is
 *              stopped immediately and never read, unless the user agreed to the video check
 *              (`video: true`): then ~15 downscaled frames/s go to the local engine only
 *              (videoFrames.ts). The microphone is never opened.
 *   replay   — a labelled demo recording played through the very same pipeline
 *              ("DEMO REPLAY — NOT LIVE CAPTURE"), audible so the room hears the "caller".
 *
 * Telemetry back to main: status, a 20 Hz loudness level (local only, makes Satya nod),
 * speech start/stop and "an utterance was sent". Any error fails closed: capture stops and
 * main puts Satya to sleep with a note saying why (also when the local engine stops answering).
 */

import { useEffect } from 'react'

import { ENGINE_LOST_REASON as ENGINE_LOST } from '../../../shared/contracts'

import { startPipeline, stopPipeline } from './pipeline'
import { startReplay, stopReplay } from './replay'
import { startVideo, stopVideo } from './videoFrames'

const NO_AUDIO_TIMEOUT_MS = 4000

type CaptureCommand =
  | {
      action: 'start'
      call_id: string
      source: 'loopback' | 'replay'
      replay_url?: string
      video?: boolean
    }
  | { action: 'stop' }

interface CaptureBridge {
  sendCapture?: (channel: string, payload?: unknown) => void
  onCaptureCommand?: (callback: (command: CaptureCommand) => void) => () => void
}

function bridge(): CaptureBridge {
  return (window as unknown as { satyapan?: CaptureBridge }).satyapan ?? {}
}

function send(channel: string, payload?: unknown): void {
  bridge().sendCapture?.(channel, payload)
}

function errorOf(error: unknown): string {
  if (error instanceof DOMException && error.name === 'NotAllowedError') {
    return 'screen & system audio permission was not granted'
  }
  return error instanceof Error ? error.message : String(error)
}

export default function CaptureApp(): JSX.Element {
  useEffect(() => {
    let disposed = false
    let token = 0
    let activeCall: string | null = null
    let activeSource: 'loopback' | 'replay' | null = null
    let stream: MediaStream | null = null
    let watchdog: ReturnType<typeof setInterval> | null = null
    let lastFrameAt = 0

    const release = (): void => {
      if (watchdog) clearInterval(watchdog)
      watchdog = null
      for (const track of stream?.getTracks() ?? []) track.stop()
      stream = null
    }

    const stop = async (notify: boolean, reason?: string): Promise<void> => {
      token += 1
      const had = activeCall !== null
      const source = activeSource
      activeCall = null
      activeSource = null
      await stopVideo()
      if (source === 'replay') await stopReplay(false)
      else await stopPipeline()
      release()
      if (notify && had) send('capture:status', { state: 'stopped', reason })
    }

    const fail = async (reason: string): Promise<void> => {
      await stop(false)
      send('capture:status', { state: 'error', reason })
    }

    const hooks = (myToken: number, callId: string) => ({
      onLevel: (rms: number) => {
        if (myToken === token) send('capture:level', Math.min(1, rms * 6))
      },
      onFrame: () => {
        lastFrameAt = Date.now()
      },
      onSpeech: (active: boolean) => {
        if (myToken === token) send('capture:speech', active)
      },
      onUtterance: (info: { index: number }) => {
        if (myToken === token) send('capture:utterance', { call_id: callId, index: info.index })
      },
      onCallGone: () => {
        if (myToken === token) void stop(true, 'the call was stopped')
      },
      onEngineLost: () => {
        if (myToken === token) void fail(ENGINE_LOST)
      },
    })

    const startLoopback = async (callId: string, wantVideo: boolean): Promise<void> => {
      await stop(false)
      if (disposed) return
      const myToken = ++token
      activeCall = callId
      activeSource = 'loopback'
      send('capture:status', { state: 'starting', source: 'loopback', call_id: callId })
      try {
        if (!navigator.mediaDevices?.getDisplayMedia) throw new Error('system audio capture is unavailable')
        const media = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
        if (myToken !== token || disposed) {
          for (const track of media.getTracks()) track.stop()
          return
        }
        // Without the video scope, never use the video: stop it before anything else.
        const [videoTrack] = media.getVideoTracks()
        const keepVideo = wantVideo && videoTrack !== undefined
        for (const track of media.getVideoTracks()) if (!keepVideo || track !== videoTrack) track.stop()
        const audio = media.getAudioTracks()
        // With the face check on, a laptop without system-audio loopback (some Linux desktops)
        // still gets the video check; without it there is nothing to do, so fail closed.
        if (audio.length === 0 && !keepVideo) {
          throw new Error('no system audio track (check the Screen & System Audio Recording permission)')
        }
        stream = new MediaStream(keepVideo ? [...audio, videoTrack] : audio)
        for (const track of audio) {
          track.onended = () => {
            if (myToken === token) void fail('system audio stopped')
          }
        }
        lastFrameAt = Date.now()
        if (audio.length > 0) await startPipeline(new MediaStream(audio), callId, hooks(myToken, callId))
        if (keepVideo) {
          await startVideo(videoTrack, callId, {
            onCallGone: () => {
              if (myToken === token) void stop(true, 'the call was stopped')
            },
            onVideoLost: (reason) => {
              if (myToken === token) void fail(reason)
            },
          })
        }
        if (myToken !== token || disposed) return
        send('capture:status', { state: 'capturing', source: 'loopback', call_id: callId })
        if (audio.length > 0) {
          watchdog = setInterval(() => {
            if (myToken !== token || activeCall === null) return
            if (Date.now() - lastFrameAt > NO_AUDIO_TIMEOUT_MS) void fail('no audio samples arrived')
          }, 500)
        }
      } catch (error) {
        if (myToken !== token || disposed) return
        await fail(errorOf(error))
      }
    }

    const startDemoReplay = async (callId: string, url: string): Promise<void> => {
      await stop(false)
      if (disposed) return
      const myToken = ++token
      activeCall = callId
      activeSource = 'replay'
      send('capture:status', { state: 'starting', source: 'replay', call_id: callId })
      await startReplay(url, callId, {
        audible: true,
        ...hooks(myToken, callId),
        onStatus: (status) => {
          if (myToken !== token) return
          if (status.state === 'capturing') {
            send('capture:status', { state: 'capturing', source: 'replay', call_id: callId })
          } else if (status.state === 'stopped') {
            activeCall = null
            activeSource = null
            send('capture:status', { state: 'stopped', reason: 'the replay finished' })
          } else {
            void fail(status.reason ?? 'replay failed')
          }
        },
      })
    }

    const off = bridge().onCaptureCommand?.((command) => {
      if (command.action === 'stop') {
        void stop(true)
      } else if (command.source === 'replay') {
        void startDemoReplay(command.call_id, command.replay_url ?? '')
      } else {
        void startLoopback(command.call_id, command.video === true)
      }
    })

    return () => {
      disposed = true
      off?.()
      void stop(false)
    }
  }, [])

  return <div data-view="capture" aria-hidden className="h-full w-full bg-transparent" />
}
