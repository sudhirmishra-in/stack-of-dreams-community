// Fails the build if the MapLibre worker was not emitted. MapLibre loads it by URL at runtime, so a missing file
// only shows up as a map that hangs in production. This turns that silent failure into a build error.
import { readdirSync, readFileSync } from 'node:fs';

const assets = readdirSync('dist/assets');
const worker = assets.find((f) => /^maplibre-gl-worker.*\.mjs$/.test(f));
if (!worker) {
  console.error(
    'verify-dist: MapLibre worker asset is missing from dist/assets (map would never load).',
  );
  process.exit(1);
}
const mapChunk = assets.find((f) => /^ResourceMap-.*\.js$/.test(f));
if (!mapChunk || !readFileSync(`dist/assets/${mapChunk}`, 'utf8').includes(worker)) {
  console.error(
    `verify-dist: the map chunk does not reference ${worker}; setWorkerUrl() is not wired.`,
  );
  process.exit(1);
}
console.log(`verify-dist: ok (${worker} emitted and referenced by ${mapChunk})`);
