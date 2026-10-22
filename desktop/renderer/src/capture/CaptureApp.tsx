/**
 * CaptureApp — the hidden 1×1 capture window (`?view=capture`). F10 (Kartikey) fills this in
 * with the loopback/VAD pipeline. Until then it renders nothing and captures nothing: the app
 * never opens the microphone.
 */

export default function CaptureApp(): JSX.Element {
  return <div data-view="capture" aria-hidden className="h-full w-full bg-transparent" />
}
