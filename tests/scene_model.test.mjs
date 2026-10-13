import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { test } from 'node:test';
import * as THREE from 'three';
import { clone, poseMatrix, fixtureBounds, applyTransform, editObjectPose, editFixturePose,
  rotateFixture, addObject, addFixture, removeSelection, validateDraft } from '../web/scene-model.js';

function display() {
  return {
    version: 1, name: 'Test yard', units: 'meters', colorOrder: 'RGB', pixelCount: 6,
    channelCount: 36, universeSize: 510, startUniverse: 1, universeCount: 1,
    fixtures: [
      { id: 'roof', name: 'Roof', type: 'string', startChannel: 1, pixelCount: 2, pixels: [[0, 1, 0], [2, 3, 2]] },
      { id: 'window', name: 'Window', type: 'string', startChannel: 10, pixelCount: 2, pixels: [[0, 2, 0], [1, 3, 1]] },
      { id: 'yard', name: 'Yard', type: 'string', startChannel: 25, pixelCount: 2, pixels: [[-3, 0, 1], [-1, 2, 3]] },
    ],
    scene: {
      version: 1,
      environment: { skyColor: '#152238', groundColor: '#8398b2', snowfall: true, glow: true, groundVisible: true, exposure: 1.2 },
      objects: [
        { id: 'house', name: 'House', type: 'house', position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], color: '#354251', fixtureIds: ['roof', 'window'] },
        { id: 'pine', name: 'Pine', type: 'pine', position: [5, 0, 0], rotation: [0, 0, 0], scale: [2, 3, 2], color: '#174f43', fixtureIds: [] },
      ],
    },
  };
}

function close(actual, expected, tolerance = 1e-6) {
  assert.equal(actual.length, expected.length);
  for (let i = 0; i < actual.length; i++) assert.ok(Math.abs(actual[i] - expected[i]) <= tolerance, `${actual} differs from ${expected}`);
}

function channels(layout) {
  return layout.fixtures.map(({ id, startChannel, pixelCount }) => [id, startChannel, pixelCount]);
}

test('poseMatrix uses XYZ rotations in degrees and applies scale before translation', () => {
  const matrix = poseMatrix({ position: [10, 2, 5], rotation: [0, 90, 0], scale: [2, 3, 4] });
  close(new THREE.Vector3(1, 1, 1).applyMatrix4(matrix).toArray(), [14, 5, 3]);
  const rotated = poseMatrix({ position: [0, 0, 0], rotation: [90, 90, 0], scale: [1, 1, 1] });
  close(new THREE.Vector3(0, 0, 1).applyMatrix4(rotated).toArray(), [1, 0, 0]);
});

test('applyTransform applies a world-space matrix delta to every linked fixture', () => {
  const original = display(), frozen = clone(original);
  const previous = original.scene.objects[0];
  const next = { ...previous, position: [3, 1, -2], rotation: [0, 90, 0], scale: [2, 1, 2] };
  const result = applyTransform(original, { kind: 'object', id: 'house' }, {
    ...next, previousMatrix: poseMatrix(previous).toArray(), matrix: poseMatrix(next).toArray(),
  });
  close(result.fixtures[0].pixels[0], [3, 2, -2]);
  close(result.fixtures[0].pixels[1], [7, 4, -6]);
  close(result.fixtures[1].pixels[0], [3, 3, -2]);
  close(result.fixtures[1].pixels[1], [5, 4, -4]);
  assert.deepEqual(result.fixtures[2], original.fixtures[2]);
  assert.deepEqual(result.scene.objects[1], original.scene.objects[1]);
  assert.deepEqual(channels(result), channels(original));
  assert.equal(result.channelCount, 36);
  assert.deepEqual(original, frozen);
});

test('editing a transformed object preserves attachment offsets and supports disabling linkage', () => {
  const initial = display();
  const moved = editObjectPose(initial, 'house', { position: [2, 1, 3], rotation: [0, 40, 0], scale: [2, 3, 1] });
  const restored = editObjectPose(moved, 'house', { position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1] });
  for (let f = 0; f < initial.fixtures.length; f++) for (let p = 0; p < initial.fixtures[f].pixels.length; p++) close(restored.fixtures[f].pixels[p], initial.fixtures[f].pixels[p], 2e-6);
  const independent = editObjectPose(initial, 'house', { position: [8, 0, 0] }, false);
  assert.deepEqual(independent.fixtures, initial.fixtures);
  assert.deepEqual(independent.scene.objects[0].position, [8, 0, 0]);
});

test('fixture pose edits move and resize only the selected pixels around their center', () => {
  const original = display();
  const moved = editFixturePose(original, 'roof', 'position', [4, 5, 6]);
  assert.deepEqual(fixtureBounds(moved.fixtures[0]).center, [4, 5, 6]);
  assert.deepEqual(moved.fixtures.slice(1), original.fixtures.slice(1));
  assert.deepEqual(moved.scene, original.scene);
  const resized = editFixturePose(moved, 'roof', 'size', [4, 6, 8]);
  assert.deepEqual(fixtureBounds(resized.fixtures[0]), { center: [4, 5, 6], size: [4, 6, 8] });
  assert.deepEqual(channels(resized), channels(original));
  assert.deepEqual(original, display());
});

test('resizing a flat string keeps its degenerate axes finite', () => {
  const original = display();
  original.fixtures[0].pixels = [[-2, 1, 7], [2, 1, 7]];
  const resized = editFixturePose(original, 'roof', 'size', [8, 2, 2]);
  assert.deepEqual(resized.fixtures[0].pixels, [[-4, 1, 7], [4, 1, 7]]);
});

test('fixture rotation is around its own center and does not affect scenery or channel order', () => {
  const original = display(), result = rotateFixture(original, 'roof', 90);
  close(result.fixtures[0].pixels[0], [0, 1, 2]);
  close(result.fixtures[0].pixels[1], [2, 3, 0]);
  assert.deepEqual(result.scene, original.scene);
  assert.deepEqual(channels(result), channels(original));
  assert.deepEqual(result.fixtures.slice(1), original.fixtures.slice(1));
});

test('operations return independent undo snapshots', () => {
  const original = display(), frozen = clone(original);
  const changed = editFixturePose(original, 'window', 'position', [5, 5, 5]);
  const history = clone(original);
  changed.scene.environment.skyColor = '#ffffff';
  changed.scene.objects[0].fixtureIds.pop();
  changed.fixtures[0].pixels[0][0] = 99;
  assert.deepEqual(original, frozen);
  assert.deepEqual(history, frozen);
});

test('adding supported scenery creates unique selectable objects without attaching lights', () => {
  let layout = display();
  for (const type of ['house', 'pine', 'box', 'cone', 'arch', 'arches']) {
    const result = addObject(layout, type), object = result.layout.scene.objects.at(-1);
    assert.equal(result.selection.kind, 'object');
    assert.equal(result.selection.id, object.id);
    assert.equal(object.type, type);
    assert.equal(typeof object.name, 'string');
    assert.ok(!object.name.includes('undefined'));
    assert.deepEqual(object.fixtureIds, []);
    assert.deepEqual(result.layout.fixtures, layout.fixtures);
    layout = result.layout;
  }
  assert.equal(new Set(layout.scene.objects.map(o => o.id)).size, layout.scene.objects.length);
});

test('new strings, arches and trees append after all declared channels without overlap', () => {
  let layout = display();
  for (const [type, count] of [['string', 64], ['arch', 40], ['tree', 192]]) {
    const previous = clone(layout), result = addFixture(layout, type), fixture = result.layout.fixtures.at(-1);
    assert.equal(result.selection.kind, 'fixture');
    assert.equal(result.selection.id, fixture.id);
    assert.equal(fixture.startChannel, previous.channelCount + 1);
    assert.equal(fixture.pixels.length, count);
    assert.equal(result.layout.channelCount, previous.channelCount + count * 3);
    assert.deepEqual(result.layout.fixtures.slice(0, -1), previous.fixtures);
    assert.deepEqual(result.layout.scene, previous.scene);
    layout = result.layout;
  }
});

test('removing scenery keeps lights; removing a fixture detaches it and preserves retired channels', () => {
  const original = display();
  const objectRemoved = removeSelection(original, { kind: 'object', id: 'house' });
  assert.deepEqual(objectRemoved.fixtures, original.fixtures);
  assert.equal(objectRemoved.scene.objects.length, 1);
  const lightRemoved = removeSelection(original, { kind: 'fixture', id: 'window' });
  assert.deepEqual(lightRemoved.scene.objects[0].fixtureIds, ['roof']);
  assert.equal(lightRemoved.fixtures.length, 2);
  assert.equal(lightRemoved.pixelCount, 4);
  const lastRemoved = removeSelection(lightRemoved, { kind: 'fixture', id: 'yard' });
  assert.equal(lastRemoved.channelCount, original.channelCount);
  const appended = addFixture(lastRemoved, 'arch').layout.fixtures.at(-1);
  assert.equal(appended.startChannel, original.channelCount + 1);
  assert.throws(() => removeSelection(lastRemoved, { kind: 'fixture', id: 'roof' }), /at least one/i);
  assert.deepEqual(original, display());
});

test('validation rejects broken mappings, transforms, attachment duplication, and non-finite data', () => {
  const invalid = [
    d => { d.fixtures[1].startChannel = 3; },
    d => { d.fixtures[0].pixels[0][0] = Infinity; },
    d => { d.scene.objects[0].scale = [1, 0, 1]; },
    d => { d.scene.objects[0].rotation = [0, 400, 0]; },
    d => { d.scene.objects[1].fixtureIds = ['roof']; },
    d => { d.scene.objects[0].fixtureIds = ['roof', 'roof']; },
    d => { d.scene.objects[0].fixtureIds = ['missing']; },
    d => { d.scene.environment.exposure = 4; },
    d => { d.scene.environment.glow = 'true'; },
  ];
  for (const change of invalid) { const draft = display(); change(draft); assert.throws(() => validateDraft(draft)); }
});

test('import validation rejects unsupported fields and invalid declared channel metadata', () => {
  const invalid = [
    d => { d.scene.secret = 'unknown'; },
    d => { d.scene.objects[0].onClick = 'unknown'; },
    d => { d.scene.environment.sunlight = true; },
    d => { d.scene.version = 99; },
    d => { d.scene.objects[0].id = 123; },
    d => { d.scene.objects[0].type = 'constructor'; },
    d => { d.universeSize = 511; },
    d => { d.startUniverse = 0; },
    d => { d.channelCount = 60001; },
    d => { d.channelCount = 1; },
    d => { d.pixelCount = 2; },
    d => { d.fixtures[0].pixelCount = 3; },
    d => { d.fixtures[0].type = 1; },
    d => { d.name = ''; },
  ];
  for (const [index, change] of invalid.entries()) {
    const draft = display(); change(draft);
    assert.throws(() => validateDraft(draft), `invalid import ${index} was accepted`);
  }
});

test('frontend removal and append preserve padded channels in the backend persisted layout', () => {
  const removed = removeSelection(display(), { kind: 'fixture', id: 'yard' });
  const input = addFixture(removed, 'string').layout;
  const python = [
    'import json, pathlib, sys, tempfile',
    'from lightshow.app import Config, LightShowApplication',
    'request=json.load(sys.stdin); layout=request["draft"]',
    'with tempfile.TemporaryDirectory() as folder:',
    ' path=pathlib.Path(folder)/"scene.json"',
    ' path.write_text(json.dumps(request["initial"]), encoding="utf-8")',
    ' app=LightShowApplication(Config(layout=path,unreal_layout=None))',
    ' app.save_layout({"layout":layout,"revision":app.layout_revision})',
    ' saved=json.loads(path.read_text(encoding="utf-8"))',
    ' backup=json.loads(path.with_suffix(".json.bak").read_text(encoding="utf-8"))',
    ' print(json.dumps({"saved":saved,"backup":backup}))',
  ].join('\n');
  const result = JSON.parse(execFileSync('python', ['-c', python], { input: JSON.stringify({ initial: display(), draft: input }), encoding: 'utf8' }));
  assert.equal(result.saved.channelCount, 228);
  assert.equal(result.saved.fixtures.at(-1).startChannel, 37);
  assert.equal(result.saved.pixelCount, 68);
  assert.deepEqual(channels(result.saved), channels(input));
  assert.equal(result.backup.channelCount, 36);
  assert.equal(result.backup.fixtures.at(-1).startChannel, 25);
});

test('bundled layout remains valid after normalization for the browser editor', async () => {
  const layout = JSON.parse(await readFile(new URL('../layouts/default.json', import.meta.url), 'utf8'));
  const normalized = JSON.parse(execFileSync('python', ['-c', 'import json,sys; from lightshow.layout import validate_layout; print(json.dumps(validate_layout(json.load(sys.stdin))))'], { input: JSON.stringify(layout), encoding: 'utf8' }));
  assert.equal(validateDraft(normalized), normalized);
  assert.equal(normalized.scene.version, 1);
});
