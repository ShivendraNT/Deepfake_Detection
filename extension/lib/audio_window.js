export function createWindower({ sampleRate = 16000, windowSeconds = 5 }) {
    const windowSamples = sampleRate * windowSeconds;
    let buffer = new Float32Array(windowSamples);
    let offset = 0;
    let windowIndex = 0;

    return {
        push(frames) {
            const result = [];
            let frameOffset = 0;

            while (frameOffset < frames.length) {
                const space = windowSamples - offset;
                const toCopy = Math.min(space, frames.length - frameOffset);
                buffer.set(frames.subarray(frameOffset, frameOffset + toCopy), offset);
                offset += toCopy;
                frameOffset += toCopy;

                if (offset === windowSamples) {
                    result.push({
                        windowIndex: windowIndex,
                        t_start_s: windowIndex * windowSeconds,
                        t_end_s: (windowIndex + 1) * windowSeconds,
                        data: new Float32Array(buffer)
                    });
                    windowIndex++;
                    offset = 0;
                }
            }
            return result;
        }
    };
}

export function speechSeconds(windowData, sampleRate = 16000, rmsThreshold = 0.01) {
    const frameSamples = Math.floor(sampleRate * 0.03);
    let speechFrames = 0;
    let totalFrames = 0;
    
    for (let i = 0; i < windowData.length; i += frameSamples) {
        const end = Math.min(i + frameSamples, windowData.length);
        let sumSq = 0;
        for (let j = i; j < end; j++) {
            sumSq += windowData[j] * windowData[j];
        }
        const rms = Math.sqrt(sumSq / (end - i));
        if (rms >= rmsThreshold) {
            speechFrames++;
        }
    }
    return speechFrames * 0.03;
}
