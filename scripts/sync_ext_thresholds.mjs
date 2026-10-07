import fs from 'fs';
import path from 'path';

const configPath = path.resolve('config/voice_thresholds.json');
const outPath = path.resolve('extension/lib/thresholds.js');

const data = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const outContent = `// GENERATED FILE - DO NOT EDIT MANUALLY
// Run node scripts/sync_ext_thresholds.mjs to update from config/voice_thresholds.json

export const THRESHOLDS = {
    tauHi: ${data.tau_hi},
    tauLo: ${data.tau_lo},
    modelVersion: "${data.model_version}",
    calibrated: ${data.calibrated}
};
`;

fs.writeFileSync(outPath, outContent);
console.log('Generated extension/lib/thresholds.js');
