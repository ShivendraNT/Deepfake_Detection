import test from 'node:test';
import assert from 'node:assert';
import { createWindower, speechSeconds } from '../lib/audio_window.js';

test('createWindower buffers frames into exact windows', (t) => {
    const windower = createWindower({ sampleRate: 1000, windowSeconds: 2 });
    // Window is 2000 samples.
    
    const frames1 = new Float32Array(1500);
    const result1 = windower.push(frames1);
    assert.strictEqual(result1.length, 0);

    const frames2 = new Float32Array(1000);
    const result2 = windower.push(frames2);
    assert.strictEqual(result2.length, 1);
    assert.strictEqual(result2[0].data.length, 2000);
    assert.strictEqual(result2[0].t_start_s, 0);
    assert.strictEqual(result2[0].t_end_s, 2);
    assert.strictEqual(result2[0].windowIndex, 0);

    const result3 = windower.push(new Float32Array(3500));
    assert.strictEqual(result3.length, 2);
    assert.strictEqual(result3[0].windowIndex, 1);
    assert.strictEqual(result3[1].windowIndex, 2);
    assert.strictEqual(result3[1].t_end_s, 6);
});

test('speechSeconds calculates correct speech duration', (t) => {
    const sampleRate = 1000; // 30ms = 30 samples
    const windowData = new Float32Array(1000); // 1 sec
    
    // Fill first 300 samples (10 frames) with loud signal
    for (let i = 0; i < 300; i++) {
        windowData[i] = 0.5; // rms = 0.5 > 0.01
    }
    
    // Rest is silence (0)
    const duration = speechSeconds(windowData, sampleRate, 0.01);
    
    // Expecting 10 frames * 0.03 = 0.3 seconds
    assert.ok(Math.abs(duration - 0.3) < 0.001);
});
