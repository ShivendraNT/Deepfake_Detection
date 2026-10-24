/**
 * WAV encoding for the capture pipeline (F10).
 *
 * The backend's live endpoints expect a complete, self-describing file per chunk: 16 kHz,
 * mono, 16-bit PCM. This helper is pure and has no Electron/DOM-network dependency, so it is
 * easy to test and can run inside the hidden capture renderer.
 */

const WAV_HEADER_BYTES = 44
const PCM_FORMAT = 1
const CHANNELS = 1
const BITS_PER_SAMPLE = 16

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let index = 0; index < text.length; index += 1) {
    view.setUint8(offset + index, text.charCodeAt(index))
  }
}

/**
 * Encode mono Int16 PCM samples as a standard 44-byte RIFF/WAVE file.
 *
 * @param pcm16 signed 16-bit samples at `sampleRate`
 * @param sampleRate samples per second (the capture graph uses 16000)
 */
export function encodeWav(pcm16: Int16Array, sampleRate = 16000): Blob {
  const blockAlign = CHANNELS * (BITS_PER_SAMPLE / 8)
  const byteRate = sampleRate * blockAlign
  const dataBytes = pcm16.length * 2
  const buffer = new ArrayBuffer(WAV_HEADER_BYTES + dataBytes)
  const view = new DataView(buffer)

  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataBytes, true) // RIFF chunk size = file size - 8
  writeAscii(view, 8, 'WAVE')

  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true) // PCM fmt chunk size
  view.setUint16(20, PCM_FORMAT, true)
  view.setUint16(22, CHANNELS, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, byteRate, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, BITS_PER_SAMPLE, true)

  writeAscii(view, 36, 'data')
  view.setUint32(40, dataBytes, true)

  for (let index = 0; index < pcm16.length; index += 1) {
    view.setInt16(WAV_HEADER_BYTES + index * 2, pcm16[index], true)
  }

  return new Blob([buffer], { type: 'audio/wav' })
}
