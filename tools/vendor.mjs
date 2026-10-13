import { mkdir, copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = path.join(root, 'node_modules', 'three');
const destination = path.join(root, 'web', 'vendor', 'three');
for (const relative of ['build/three.module.js', 'build/three.core.js', 'examples/jsm/controls/OrbitControls.js', 'examples/jsm/controls/TransformControls.js', 'LICENSE']) {
  const output = path.join(destination, relative);
  await mkdir(path.dirname(output), { recursive: true });
  await copyFile(path.join(source, relative), output);
}
console.log('Vendored Three.js 0.180.0. The visualizer now runs without an internet connection.');
