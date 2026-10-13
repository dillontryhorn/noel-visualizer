import * as THREE from 'three';

export const clone = value => JSON.parse(JSON.stringify(value));
export const OBJECT_SIZES = { house: [8, 5.8, 4], pine: [1, 1, 1], box: [1, 1, 1], cone: [1, 1, 1], arch: [1, 1, .08], arches: [6.6, 1.2, .08] };
const radians = value => value * Math.PI / 180;
export function poseMatrix(item) {
  return new THREE.Matrix4().compose(new THREE.Vector3(...item.position), new THREE.Quaternion().setFromEuler(new THREE.Euler(...item.rotation.map(radians), 'XYZ')), new THREE.Vector3(...item.scale));
}
export function fixtureBounds(fixture) {
  const box = new THREE.Box3().setFromPoints(fixture.pixels.map(p => new THREE.Vector3(...p)));
  return { center: box.getCenter(new THREE.Vector3()).toArray(), size: box.getSize(new THREE.Vector3()).toArray() };
}
export function updateCounts(layout) {
  layout.pixelCount = layout.fixtures.reduce((sum, f) => { f.pixelCount = f.pixels.length; return sum + f.pixelCount; }, 0);
  const span = Math.max(...layout.fixtures.map(f => f.startChannel - 1 + f.pixels.length * 3));
  layout.channelCount = Math.max(layout.channelCount || 0, span);
  layout.universeCount = Math.ceil(layout.channelCount / (layout.universeSize || 510));
  return layout;
}
export function transformPoints(fixture, delta) {
  fixture.pixels = fixture.pixels.map(point => new THREE.Vector3(...point).applyMatrix4(delta).toArray().map(v => Math.round(v * 1e6) / 1e6));
}
export function applyTransform(layout, selection, next, linkFixtures = true) {
  const result = clone(layout);
  const previousMatrix = new THREE.Matrix4().fromArray(next.previousMatrix);
  const delta = new THREE.Matrix4().fromArray(next.matrix).multiply(previousMatrix.invert());
  if (selection.kind === 'object') {
    const object = result.scene.objects.find(o => o.id === selection.id);
    if (!object) throw new Error('The selected object no longer exists.');
    for (const key of ['position', 'rotation', 'scale']) object[key] = [...next[key]];
    if (linkFixtures) for (const fixture of result.fixtures) if (object.fixtureIds.includes(fixture.id)) transformPoints(fixture, delta);
  } else {
    const fixture = result.fixtures.find(f => f.id === selection.id);
    if (!fixture) throw new Error('The selected light fixture no longer exists.');
    transformPoints(fixture, delta);
  }
  return validateDraft(updateCounts(result));
}
export function editObjectPose(layout, id, changes, linkFixtures = true) {
  const object = layout.scene.objects.find(o => o.id === id);
  const next = { ...object, ...changes };
  return applyTransform(layout, { kind: 'object', id }, { ...next, previousMatrix: poseMatrix(object).toArray(), matrix: poseMatrix(next).toArray() }, linkFixtures);
}
export function editFixturePose(layout, id, field, values) {
  const fixture = layout.fixtures.find(f => f.id === id), bounds = fixtureBounds(fixture);
  const center = new THREE.Vector3(...bounds.center), delta = new THREE.Matrix4();
  if (field === 'position') delta.makeTranslation(...values.map((v, i) => v - bounds.center[i]));
  else {
    const scale = values.map((v, i) => bounds.size[i] < .001 ? 1 : v / bounds.size[i]);
    delta.makeTranslation(...center.toArray()).multiply(new THREE.Matrix4().makeScale(...scale)).multiply(new THREE.Matrix4().makeTranslation(...center.clone().negate().toArray()));
  }
  return applyTransform(layout, { kind: 'fixture', id }, { matrix: delta.toArray(), previousMatrix: new THREE.Matrix4().toArray() });
}
export function rotateFixture(layout, id, degrees) {
  const center = fixtureBounds(layout.fixtures.find(f => f.id === id)).center;
  const delta = new THREE.Matrix4().makeTranslation(...center).multiply(new THREE.Matrix4().makeRotationY(radians(degrees))).multiply(new THREE.Matrix4().makeTranslation(...center.map(v => -v)));
  return applyTransform(layout, { kind: 'fixture', id }, { matrix: delta.toArray(), previousMatrix: new THREE.Matrix4().toArray() });
}
export function uniqueId(items, prefix) { let i = 1; while (items.some(o => o.id === `${prefix}-${i}`)) i++; return `${prefix}-${i}`; }
export function addObject(layout, type) {
  const result = clone(layout), id = uniqueId(result.scene.objects, type);
  const names = { house: 'House', pine: 'Pine tree', box: 'Box', cone: 'Cone tree', arch: 'Arch', arches: 'Three arches' };
  if (!Object.hasOwn(names, type)) throw new Error('Unknown scenery type.');
  const scales = { house: [.6, .6, .6], pine: [2, 3, 2], box: [2, 1, 2], cone: [2, 3, 2], arch: [2, 1.2, 1] };
  result.scene.objects.push({ id, name: `${names[type]} ${id.split('-').pop()}`, type, position: [0, 0, 7], rotation: [0, 0, 0], scale: scales[type] || [1, 1, 1], color: type === 'pine' || type === 'cone' ? '#174f43' : '#536576', fixtureIds: [] });
  return { layout: validateDraft(result), selection: { kind: 'object', id } };
}
export function addFixture(layout, type) {
  if (!['string', 'tree', 'arch'].includes(type)) throw new Error('Unknown light fixture type.');
  const result = clone(layout), id = uniqueId(result.fixtures, `light-${type}`), pixels = [];
  if (type === 'string') for (let i = 0; i < 64; i++) pixels.push([-2 + 4 * i / 63, 1, 7]);
  if (type === 'arch') for (let i = 0; i < 40; i++) { const angle = Math.PI * i / 39; pixels.push([Math.cos(angle), .08 + Math.sin(angle) * 1.2, 7]); }
  if (type === 'tree') for (let strand = 0; strand < 8; strand++) {
    const angle = Math.PI * 2 * strand / 8, points = [];
    for (let i = 0; i < 24; i++) { const t = i / 23; points.push([Math.cos(angle) * (1 - t), .12 + 2.88 * t, 7 + Math.sin(angle) * (1 - t)]); }
    pixels.push(...(strand % 2 ? points.reverse() : points));
  }
  const startChannel = Math.max(result.channelCount, ...result.fixtures.map(f => f.startChannel - 1 + f.pixels.length * 3)) + 1;
  result.fixtures.push({ id, name: `${type === 'string' ? 'Light string' : type === 'tree' ? 'Pixel tree' : 'Light arch'} ${id.split('-').pop()}`, type, startChannel, pixels });
  return { layout: validateDraft(updateCounts(result)), selection: { kind: 'fixture', id } };
}
export function removeSelection(layout, selection) {
  const result = clone(layout);
  if (selection.kind === 'object') result.scene.objects = result.scene.objects.filter(o => o.id !== selection.id);
  else {
    if (result.fixtures.length <= 1) throw new Error('Keep at least one light fixture in the display.');
    result.fixtures = result.fixtures.filter(f => f.id !== selection.id);
    for (const o of result.scene.objects) o.fixtureIds = o.fixtureIds.filter(id => id !== selection.id);
  }
  return validateDraft(updateCounts(result));
}
export function validateDraft(layout) {
  const vector = (value, min, max) => Array.isArray(value) && value.length === 3 && value.every(n => typeof n === 'number' && Number.isFinite(n) && n >= min && n <= max);
  const hex = value => typeof value === 'string' && /^#[\da-f]{6}$/i.test(value);
  if (!layout || typeof layout !== 'object' || !Array.isArray(layout.fixtures) || !layout.fixtures.length || layout.fixtures.length > 256) throw new Error('A scene needs 1–256 light fixtures.');
  if (typeof layout.name !== 'string' || !layout.name.trim() || layout.name.length > 120) throw new Error('The display needs a name of up to 120 characters.');
  const ids = new Set(), ranges = []; let count = 0;
  for (const fixture of layout.fixtures) {
    if (typeof fixture.id !== 'string' || !/^[\w-]{1,64}$/.test(fixture.id) || ids.has(fixture.id)) throw new Error('Fixture IDs must be unique letters, numbers, dashes, or underscores.');
    if (typeof fixture.name !== 'string' || !fixture.name.trim() || fixture.name.length > 120) throw new Error('Each fixture needs a name.');
    if (typeof fixture.type !== 'string' || !fixture.type || fixture.type.length > 40) throw new Error('Invalid light fixture type.');
    ids.add(fixture.id);
    if (!Number.isInteger(fixture.startChannel) || fixture.startChannel < 1 || !Array.isArray(fixture.pixels) || !fixture.pixels.length) throw new Error('Invalid fixture channel or pixel data.');
    if (fixture.pixelCount !== undefined && fixture.pixelCount !== fixture.pixels.length) throw new Error('Fixture pixel count does not match its pixels.');
    for (const point of fixture.pixels) if (!vector(point, -1000, 1000)) throw new Error('Light positions must be finite coordinates within 1,000 meters.');
    const start = fixture.startChannel - 1, end = start + fixture.pixels.length * 3;
    if (end > 60000 || ranges.some(([a, b]) => start < b && end > a)) throw new Error('Light channel ranges overlap or exceed 60,000 channels.');
    ranges.push([start, end]); count += fixture.pixels.length;
  }
  if (count > 20000) throw new Error('A scene supports up to 20,000 RGB pixels.');
  const span = Math.max(...ranges.map(([, end]) => end));
  if (!Number.isInteger(layout.channelCount) || layout.channelCount < span || layout.channelCount > 60000) throw new Error('Invalid display channel count.');
  if (layout.pixelCount !== undefined && layout.pixelCount !== count) throw new Error('Pixel count does not match the light fixtures.');
  if (layout.universeSize !== undefined && ![510, 512].includes(layout.universeSize)) throw new Error('Universes must use 510 or 512 channels.');
  const first = layout.startUniverse ?? 1;
  if (!Number.isInteger(first) || first < 1 || first + Math.ceil(layout.channelCount / (layout.universeSize || 510)) - 1 > 63999) throw new Error('Invalid starting universe.');
  if (!layout.scene || !Array.isArray(layout.scene.objects) || layout.scene.objects.length > 100) throw new Error('Invalid scenery objects.');
  if (layout.scene.version !== 1 || Object.keys(layout.scene).some(key => !['version', 'environment', 'objects'].includes(key))) throw new Error('Unsupported scene format.');
  const objectIds = new Set(), bound = new Set();
  for (const item of layout.scene.objects) {
    if (!item || typeof item !== 'object' || Object.keys(item).some(key => !['id', 'name', 'type', 'position', 'rotation', 'scale', 'color', 'fixtureIds'].includes(key))) throw new Error('Unsupported scenery object fields.');
    if (typeof item.id !== 'string' || !/^[\w-]{1,64}$/.test(item.id) || objectIds.has(item.id) || typeof item.type !== 'string' || !Object.hasOwn(OBJECT_SIZES, item.type) || typeof item.name !== 'string' || !item.name.trim() || item.name.length > 120 || !hex(item.color)) throw new Error('Invalid scenery object or color.');
    objectIds.add(item.id);
    if (!vector(item.position, -1000, 1000) || !vector(item.rotation, -360, 360) || !vector(item.scale, .001, 1000)) throw new Error('Object transforms are outside the supported range.');
    if (!Array.isArray(item.fixtureIds) || item.fixtureIds.some(id => !ids.has(id) || bound.has(id))) throw new Error('A fixture can be attached to one scenery object.');
    for (const id of item.fixtureIds) { if (bound.has(id)) throw new Error('Duplicate attached fixture.'); bound.add(id); }
  }
  const env = layout.scene.environment;
  if (env && Object.keys(env).some(key => !['skyColor', 'groundColor', 'snowfall', 'glow', 'groundVisible', 'exposure'].includes(key))) throw new Error('Unsupported environment setting.');
  if (!env || !hex(env.skyColor) || !hex(env.groundColor) || !Number.isFinite(env.exposure) || env.exposure < .1 || env.exposure > 3 || ['snowfall', 'glow', 'groundVisible'].some(key => typeof env[key] !== 'boolean')) throw new Error('Invalid environment settings.');
  return layout;
}
