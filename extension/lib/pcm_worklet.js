class PcmWorkletProcessor extends AudioWorkletProcessor {
    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input && input.length > 0) {
            const channelData = input[0];
            // Copy data to avoid being overwritten, and post it
            this.port.postMessage(new Float32Array(channelData));
        }
        return true;
    }
}

registerProcessor('pcm-worklet', PcmWorkletProcessor);
