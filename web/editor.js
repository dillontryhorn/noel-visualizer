import { clone, OBJECT_SIZES, fixtureBounds, editObjectPose, editFixturePose, rotateFixture, applyTransform, addObject, addFixture, removeSelection, validateDraft, updateCounts } from './scene-model.js';

const $ = id => document.getElementById(id);
const icons = { house: '⌂', pine: '♧', box: '▣', cone: '△', arch: '∩', arches: '∩', fixture: '✦' };
const round = n => Math.round(n * 1000) / 1000;
export function createEditor({ getLayout, getScene, applyLayout, notify, download }) {
  let active = false, draft = null, baseline = null, selection = null, undo = [], redo = [], busy = false, remoteRevision = null;
  let transition = false, session = 0;
  let linkFixtures = true, mode = 'translate';
  const left = document.createElement('aside'); left.className = 'editor-panel'; left.id = 'editor-panel'; left.hidden = true;
  left.innerHTML = `<div class="panel-heading"><span class="eyebrow">SCENE EDITOR</span><span class="editor-draft-badge" id="editor-draft-badge">SAVED</span></div>
    <h1>Make it your own.</h1><p class="subtitle">Select an object. Move, rotate, or resize it.</p>
    <label class="editor-label" for="editor-display-name">Display name</label><input id="editor-display-name" class="editor-input" maxlength="120">
    <div class="editor-add-row"><select id="editor-add-type" aria-label="Object to add"><optgroup label="Scenery"><option value="house">House</option><option value="pine" selected>Pine tree</option><option value="box">Box</option><option value="cone">Cone tree</option><option value="arch">Arch</option></optgroup><optgroup label="Lights"><option value="light-string">Light string · 64 pixels</option><option value="light-tree">Pixel tree · 192 pixels</option><option value="light-arch">Light arch · 40 pixels</option></optgroup></select><button class="primary-button" id="editor-add">+ Add</button></div>
    <div class="editor-list-heading"><span class="eyebrow">SCENERY</span><span id="editor-object-count"></span></div><div class="editor-object-list" id="editor-object-list"></div>
    <div class="editor-list-heading"><span class="eyebrow">LIGHT FIXTURES</span><span id="editor-fixture-count"></span></div><div class="editor-object-list" id="editor-light-list"></div>
    <div class="editor-history"><button class="quiet-button" id="editor-undo" title="Ctrl+Z">↶ Undo</button><button class="quiet-button" id="editor-redo" title="Ctrl+Shift+Z">↷ Redo</button><button class="quiet-button" id="editor-reset" title="Restore the last saved scene">Reset draft</button></div>
    <div class="editor-file-actions"><button class="quiet-button" id="editor-import">Import scene</button><button class="quiet-button" id="editor-export">Export scene</button><input id="editor-import-file" type="file" accept=".json,application/json" hidden></div>
    <p class="editor-help">Draft changes stay in this preview until you save. New lights are assigned unused RGB channels.</p>`;
  const right = document.createElement('aside'); right.className = 'editor-inspector'; right.id = 'editor-inspector'; right.hidden = true;
  right.innerHTML = `<div class="panel-heading"><span class="eyebrow">OBJECT PROPERTIES</span><span id="editor-kind" class="small-badge">SCENERY</span></div>
    <fieldset id="editor-fields"><div id="editor-selection-fields"><label class="editor-label" for="editor-object-name">Selected object</label><input id="editor-object-name" class="editor-input" maxlength="120">
    <p class="editor-coordinate-help" id="editor-coordinate-help"></p>
    <div class="editor-transform-label">Position <span>meters</span></div><div class="editor-vector" id="editor-position">${vectorMarkup('position', ['X', 'Y', 'Z'], -1000, 1000, .1)}</div>
    <div class="editor-transform-label">Size <span>meters</span></div><div class="editor-vector" id="editor-size">${vectorMarkup('size', ['Width', 'Height', 'Depth'], 0, 1000, .01)}</div>
    <div id="editor-rotation-fields"><div class="editor-transform-label">Rotation <span>degrees</span></div><div class="editor-vector">${vectorMarkup('rotation', ['X', 'Y', 'Z'], -360, 360, 5)}</div></div>
    <div id="editor-fixture-rotation" class="editor-fixture-rotation" hidden><button class="quiet-button" id="editor-rotate-left">↶ Rotate 15°</button><button class="quiet-button" id="editor-rotate-right">Rotate 15° ↷</button></div>
    <label class="editor-color-row" id="editor-object-color-row">Object color<input type="color" id="editor-object-color"></label>
    <label class="editor-check" id="editor-link-row"><input type="checkbox" id="editor-link-lights" checked>Move attached lights</label><p class="editor-binding-note" id="editor-binding-note"></p>
    <div id="editor-fixture-details" class="editor-patch-details" hidden></div><button class="quiet-button editor-focus" id="editor-focus">Frame selection</button><button class="editor-remove" id="editor-remove">Remove object</button></div>
    <section class="editor-environment"><span class="eyebrow">ENVIRONMENT</span><label class="editor-color-row">Sky color<input type="color" id="editor-sky-color"></label><label class="editor-color-row">Ground color<input type="color" id="editor-ground-color"></label><label class="editor-check"><input type="checkbox" id="editor-snowfall">Snowfall</label><label class="editor-check"><input type="checkbox" id="editor-glow">Light glow</label><label class="editor-check"><input type="checkbox" id="editor-ground-visible">Show ground</label><label class="editor-color-row">Exposure<input type="number" id="editor-exposure" min="0.1" max="3" step="0.1" class="editor-input editor-short-input"></label></section></fieldset>
    <div class="editor-save-area"><p id="editor-save-note">Changes are saved to this computer.</p><button class="primary-button editor-save" id="editor-save">Save changes</button><button class="quiet-button editor-done" id="editor-done">Done editing</button></div>`;
  const workspace = document.querySelector('.workspace'); workspace.prepend(left); workspace.append(right);
  const tools = document.createElement('div'); tools.id = 'editor-tools'; tools.className = 'editor-tools'; tools.hidden = true;
  tools.innerHTML = '<button data-transform="translate" class="active">Move</button><button data-transform="rotate">Rotate</button><button data-transform="scale">Resize</button><span>Drag the colored handles</span>';
  $('scene-container').append(tools);
  const exitDialog = document.createElement('dialog'); exitDialog.id = 'editor-exit-dialog';
  exitDialog.innerHTML = '<h2>Save your scene?</h2><p>Your draft has changes that have not been saved.</p><div class="editor-exit-actions"><button class="quiet-button" id="editor-keep">Keep editing</button><button class="quiet-button" id="editor-discard">Discard changes</button><button class="primary-button" id="editor-save-close">Save and close</button></div>';
  document.body.append(exitDialog);

  function dirty() { return draft && JSON.stringify(draft) !== JSON.stringify(baseline); }
  function bindRenderer() {
    $('snow-button').disabled = active; $('glow-button').disabled = active;
    if (active) for (const [id, key] of [['snow-button', 'snowfall'], ['glow-button', 'glow']]) { $(id).classList.toggle('active', draft.scene.environment[key]); $(id).setAttribute('aria-pressed', String(draft.scene.environment[key])); }
    getScene()?.setEditor({ enabled: active && !busy, linkFixtures, onSelectObject: select, onTransform: transform => {
      if (!active || busy) return;
      try { commit(applyTransform(draft, { kind: transform.kind, id: transform.id }, transform, linkFixtures)); }
      catch (error) { notify(error.message, true); getScene()?.setLayout(draft); select(selection); }
    } });
    getScene()?.setTransformMode(mode);
  }
  function renderLists() {
    for (const [id, items, kind] of [['editor-object-list', draft.scene.objects, 'object'], ['editor-light-list', draft.fixtures, 'fixture']]) {
      const list = $(id); list.replaceChildren();
      for (const item of items) {
        const button = document.createElement('button'); button.className = 'editor-object-button'; button.disabled = busy;
        button.classList.toggle('selected', selection?.id === item.id && selection?.kind === kind);
        button.setAttribute('aria-label', `Edit ${item.name}`); button.setAttribute('aria-pressed', String(selection?.id === item.id && selection?.kind === kind));
        const icon = document.createElement('span'); icon.textContent = icons[kind === 'fixture' ? 'fixture' : item.type] || '◈';
        const name = document.createElement('span'); name.textContent = item.name;
        const meta = document.createElement('small'); meta.textContent = kind === 'fixture' ? `${item.pixels.length} px` : item.type;
        button.append(icon, name, meta); button.onclick = () => select({ kind, id: item.id }); list.append(button);
      }
    }
    $('editor-object-count').textContent = draft.scene.objects.length; $('editor-fixture-count').textContent = draft.fixtures.length;
  }
  function renderInspector() {
    const object = selection?.kind === 'object' ? draft.scene.objects.find(o => o.id === selection.id) : null;
    const fixture = selection?.kind === 'fixture' ? draft.fixtures.find(f => f.id === selection.id) : null;
    $('editor-selection-fields').hidden = !object && !fixture;
    $('editor-kind').textContent = fixture ? 'RGB LIGHTS' : object ? object.type.toUpperCase() : 'ENVIRONMENT';
    if (object || fixture) {
      $('editor-object-name').value = (object || fixture).name;
      const bounds = fixture ? fixtureBounds(fixture) : null;
      const position = object?.position || bounds.center;
      const size = object ? object.scale.map((v, i) => v * OBJECT_SIZES[object.type][i]) : bounds.size;
      for (let i = 0; i < 3; i++) {
        $(`editor-position-${i}`).value = round(position[i]); $(`editor-size-${i}`).value = round(size[i]);
        $(`editor-size-${i}`).disabled = !!fixture && bounds.size[i] < .001;
        $(`editor-rotation-${i}`).value = object ? round(object.rotation[i]) : 0;
      }
      $('editor-coordinate-help').textContent = fixture ? 'Position is the center of these lights. Y is height.' : 'Position is the base of the object. Y is height.';
      $('editor-rotation-fields').hidden = !object; $('editor-fixture-rotation').hidden = !fixture;
      $('editor-object-color-row').hidden = !object; $('editor-link-row').hidden = !object || !object.fixtureIds.length;
      if (object) { $('editor-object-color').value = object.color; $('editor-link-lights').checked = linkFixtures; }
      const names = object?.fixtureIds.map(id => draft.fixtures.find(f => f.id === id)?.name).filter(Boolean) || [];
      $('editor-binding-note').textContent = object ? (names.length ? `Attached: ${names.join(', ')}.` : 'This scenery has no attached lights.') : 'Edit the scenery object to move a whole group together.';
      $('editor-fixture-details').hidden = !fixture;
      if (fixture) $('editor-fixture-details').textContent = `${fixture.pixels.length} RGB pixels · Channels ${fixture.startChannel}–${fixture.startChannel + fixture.pixels.length * 3 - 1}`;
      $('editor-remove').textContent = fixture ? 'Remove light fixture' : 'Remove scenery object';
    }
    const env = draft.scene.environment;
    $('editor-sky-color').value = env.skyColor; $('editor-ground-color').value = env.groundColor;
    $('editor-snowfall').checked = env.snowfall; $('editor-glow').checked = env.glow; $('editor-ground-visible').checked = env.groundVisible; $('editor-exposure').value = env.exposure;
  }
  function render() {
    $('editor-display-name').value = draft.name;
    renderLists(); renderInspector();
    const changed = dirty(); $('editor-draft-badge').textContent = changed ? 'UNSAVED' : 'SAVED'; $('editor-draft-badge').classList.toggle('dirty', changed);
    $('editor-undo').disabled = busy || !undo.length; $('editor-redo').disabled = busy || !redo.length; $('editor-reset').disabled = busy || !changed;
    $('editor-save').disabled = busy || !changed; $('editor-save').textContent = busy ? 'Saving…' : 'Save changes';
    $('editor-done').disabled = busy; $('editor-add').disabled = busy; $('editor-import').disabled = busy; $('editor-export').disabled = busy;
    $('edit-scene-button').disabled = busy || transition;
    for (const id of ['editor-keep', 'editor-discard', 'editor-save-close']) $(id).disabled = busy;
    $('editor-save-close').textContent = busy ? 'Saving…' : 'Save and close';
    $('editor-fields').disabled = busy; $('editor-display-name').disabled = busy; $('editor-add-type').disabled = busy;
    $('editor-save-note').textContent = remoteRevision !== null && remoteRevision !== baseline.revision ? 'The active scene changed. Export this draft, then reopen the editor before saving.' : changed ? 'Previewing a draft. Save to keep these changes.' : 'Saved on this computer.';
  }
  function select(next) { selection = next; if (active) { render(); getScene()?.selectEditorObject(next); } }
  function commit(next, nextSelection = selection) {
    if (!active || busy || transition) return;
    validateDraft(next);
    if (JSON.stringify(next) === JSON.stringify(draft)) return;
    undo.push(clone(draft)); if (undo.length > 20) undo.shift(); redo = []; draft = clone(next);
    selection = nextSelection;
    if (selection && !(selection.kind === 'object' ? draft.scene.objects : draft.fixtures).some(item => item.id === selection.id)) selection = null;
    getScene()?.setLayout(draft); bindRenderer(); select(selection); render();
  }
  function change(mutator) { if (!active || busy) return; try { const next = clone(draft); mutator(next); commit(next); } catch (error) { notify(error.message, true); render(); } }
  function history(direction) {
    const source = direction === 'undo' ? undo : redo, target = direction === 'undo' ? redo : undo;
    if (!source.length || busy) return; target.push(clone(draft)); draft = source.pop();
    if (selection && !(selection.kind === 'object' ? draft.scene.objects : draft.fixtures).some(item => item.id === selection.id)) selection = null;
    getScene()?.setLayout(draft); bindRenderer(); select(selection); render();
  }
  async function enter() {
    if (transition || busy) return;
    if (active || !getScene()) { if (!getScene()) notify('The 3D preview must load before editing.', true); return; }
    transition = true; const enteringSession = ++session; $('edit-scene-button').disabled = true;
    try {
      const response = await fetch('/api/layout'); if (!response.ok) throw new Error('Could not load the current scene.');
      const loaded = await response.json(); if (session !== enteringSession) return;
      validateDraft(loaded); baseline = loaded; draft = clone(baseline); applyLayout(baseline);
      active = true; remoteRevision = baseline.revision; undo = []; redo = [];
      left.hidden = right.hidden = tools.hidden = false; document.body.classList.add('editing-scene'); $('edit-scene-button').textContent = 'Exit editor';
      bindRenderer(); select(draft.scene.objects.length ? { kind: 'object', id: draft.scene.objects[0].id } : { kind: 'fixture', id: draft.fixtures[0].id });
    } catch (error) { notify(error.message, true); }
    finally { transition = false; $('edit-scene-button').disabled = busy; }
  }
  async function exit() {
    if (transition) return;
    transition = true; ++session; $('edit-scene-button').disabled = true;
    active = false; getScene()?.setEditor({ enabled: false }); left.hidden = right.hidden = tools.hidden = true;
    $('snow-button').disabled = false; $('glow-button').disabled = false;
    document.body.classList.remove('editing-scene'); $('edit-scene-button').textContent = 'Edit scene';
    try { const response = await fetch('/api/layout'); if (response.ok) applyLayout(await response.json()); else applyLayout(baseline); } catch { applyLayout(baseline); }
    finally { transition = false; $('edit-scene-button').disabled = busy; }
  }
  function requestExit() { if (busy || transition) return; if (dirty()) exitDialog.showModal(); else exit(); }
  async function save(closeAfter = false) {
    if (busy) return; busy = true; render(); bindRenderer();
    try {
      validateDraft(draft);
      const response = await fetch('/api/layout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ layout: draft, revision: baseline.revision }) });
      const body = await response.json(); if (!response.ok) throw new Error(body.error || 'Could not save the scene.');
      baseline = clone(body.layout); draft = clone(body.layout); remoteRevision = baseline.revision; undo = []; redo = []; applyLayout(body.layout);
      notify(body.unrealSync?.error ? `Scene saved. Unreal copy needs attention: ${body.unrealSync.error}` : body.unrealSync?.saved ? 'Scene saved. Restart Unreal Play to load it.' : 'Scene saved to this computer.', !!body.unrealSync?.error);
      if (closeAfter) { exitDialog.close(); await exit(); }
    } catch (error) { notify(error.message, true); }
    finally { busy = false; $('edit-scene-button').disabled = transition; if (active) { render(); bindRenderer(); select(selection); } }
  }
  $('edit-scene-button').onclick = () => active ? requestExit() : enter();
  $('editor-done').onclick = requestExit; $('editor-save').onclick = () => save();
  $('editor-focus').onclick = () => getScene()?.focusSelection();
  $('editor-keep').onclick = () => { if (!busy) exitDialog.close(); }; $('editor-discard').onclick = () => { if (busy) return; exitDialog.close(); exit(); }; $('editor-save-close').onclick = () => save(true);
  $('editor-undo').onclick = () => history('undo'); $('editor-redo').onclick = () => history('redo'); $('editor-reset').onclick = () => commit(clone(baseline));
  $('editor-add').onclick = () => {
    try { const type = $('editor-add-type').value; const added = type.startsWith('light-') ? addFixture(draft, type.slice(6)) : addObject(draft, type); commit(added.layout, added.selection); }
    catch (error) { notify(error.message, true); }
  };
  $('editor-remove').onclick = () => {
    try { const object = selection?.kind === 'object' ? draft.scene.objects.find(o => o.id === selection.id) : null;
      commit(removeSelection(draft, selection), null); if (object?.fixtureIds.length) notify('Scenery removed. Its lights remain in the Light fixtures list.');
    } catch (error) { notify(error.message, true); }
  };
  $('editor-display-name').onchange = () => change(next => { next.name = $('editor-display-name').value.trim(); });
  $('editor-object-name').onchange = () => change(next => { (selection.kind === 'object' ? next.scene.objects : next.fixtures).find(item => item.id === selection.id).name = $('editor-object-name').value.trim(); });
  for (const field of ['position', 'size', 'rotation']) for (let i = 0; i < 3; i++) $(`editor-${field}-${i}`).onchange = () => {
    try {
      const values = [0, 1, 2].map(index => Number($(`editor-${field}-${index}`).value));
      if (values.some(v => !Number.isFinite(v))) throw new Error('Enter a valid number for each axis.');
      if (field === 'size' && values.some((v, axis) => !$(`editor-size-${axis}`).disabled && v <= 0)) throw new Error('Size must be greater than zero.');
      if (selection.kind === 'object') {
        const object = draft.scene.objects.find(o => o.id === selection.id);
        commit(editObjectPose(draft, selection.id, { [field === 'size' ? 'scale' : field]: field === 'size' ? values.map((v, axis) => v / OBJECT_SIZES[object.type][axis]) : values }, linkFixtures));
      } else commit(editFixturePose(draft, selection.id, field, values));
    } catch (error) { notify(error.message, true); render(); }
  };
  $('editor-rotate-left').onclick = () => { try { commit(rotateFixture(draft, selection.id, -15)); } catch (error) { notify(error.message, true); } };
  $('editor-rotate-right').onclick = () => { try { commit(rotateFixture(draft, selection.id, 15)); } catch (error) { notify(error.message, true); } };
  $('editor-object-color').onchange = () => change(next => { next.scene.objects.find(o => o.id === selection.id).color = $('editor-object-color').value; });
  $('editor-link-lights').onchange = () => { linkFixtures = $('editor-link-lights').checked; bindRenderer(); };
  for (const [id, key, boolean] of [['editor-sky-color', 'skyColor'], ['editor-ground-color', 'groundColor'], ['editor-snowfall', 'snowfall', true], ['editor-glow', 'glow', true], ['editor-ground-visible', 'groundVisible', true], ['editor-exposure', 'exposure']]) {
    $(id).onchange = () => change(next => { next.scene.environment[key] = boolean ? $(id).checked : key === 'exposure' ? Number($(id).value) : $(id).value; });
  }
  tools.querySelectorAll('button').forEach(button => { button.onclick = () => { mode = button.dataset.transform; getScene()?.setTransformMode(mode); tools.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === button)); }; });
  $('editor-export').onclick = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' })); download(url, 'noel-scene.json'); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  $('editor-import').onclick = () => $('editor-import-file').click();
  $('editor-import-file').onchange = async () => {
    const file = $('editor-import-file').files[0]; if (!file) return;
    const importingSession = session;
    try {
      if (file.size > 8000000) throw new Error('Scene files must be smaller than 8 MB.');
      const next = JSON.parse(await file.text());
      if (!active || transition || busy || importingSession !== session) return;
      if (!next.scene) { next.scene = clone(draft.scene); const known = new Set(next.fixtures?.map(f => f.id)); for (const o of next.scene.objects) o.fixtureIds = o.fixtureIds.filter(id => known.has(id)); }
      next.name ||= 'Imported display'; for (const f of next.fixtures || []) { f.name ||= f.id; f.type ||= 'string'; }
      next.revision = baseline.revision; updateCounts(next); commit(validateDraft(next), null); notify('Scene imported into the draft. Save changes to keep it.');
    } catch (error) { notify(`Could not import: ${error.message}`, true); }
    finally { $('editor-import-file').value = ''; }
  };
  document.addEventListener('keydown', event => {
    if (!active || busy || ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) || exitDialog.open || $('help-dialog').open) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); history(event.shiftKey ? 'redo' : 'undo'); }
    if (event.key === 'Escape') requestExit();
    if (event.key.toLowerCase() === 'f' && !event.ctrlKey && !event.metaKey) getScene()?.focusSelection();
  });
  window.addEventListener('beforeunload', event => { if (active && dirty()) { event.preventDefault(); event.returnValue = ''; } });
  return { get active() { return active; }, get draft() { return draft; }, selectFixture(id) { if (active) select({ kind: 'fixture', id }); }, remoteRevision(value) { if (active && remoteRevision !== value) { remoteRevision = value; render(); } } };
}
function vectorMarkup(field, labels, min, max, step) {
  return labels.map((label, index) => `<label><span>${label}</span><input id="editor-${field}-${index}" type="number" min="${min}" max="${max}" step="${step}" aria-label="${field[0].toUpperCase() + field.slice(1)} ${label}"></label>`).join('');
}
