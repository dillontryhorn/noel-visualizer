import { createEditor } from './editor.js';

const $ = id => document.getElementById(id);
const effectNames = { aurora: 'Aurora', candy: 'Candy cane', rainbow: 'Spectrum', sparkle: 'Starlight', solid: 'Warm white', blackout: 'Blackout' };
const fixtureIcons = { roofline: '⌂', window: '⊞', windows: '⊞', door: '▯', tree: '♧', megatree: '♧', star: '✦', arches: '∩', path: '⋮' };
let state = null, layout = null, scene = null, selectedId = null, connected = false, seekActive = false, toastTimer;
let lastInterfaceUpdate = 0;
let editor = null, refreshingLayout = false;
const pendingFields = new Set();
const activeSliders = new Set();
const formatTime = seconds => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
function notify(message, error = false) {
  clearTimeout(toastTimer); $('toast').textContent = message; $('toast').classList.toggle('error', error); $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 6500 : 3000);
}
function setConnected(value) {
  connected = value;
  $('connection').classList.toggle('disconnected', !value);
  $('connection').replaceChildren(Object.assign(document.createElement('i'), {}), document.createTextNode(value ? 'Local session connected' : 'Reconnecting to service'));
}
async function control(changes) {
  Object.keys(changes).forEach(key => pendingFields.add(key));
  try {
    const response = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes) });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `Service returned ${response.status}`);
    return body;
  } catch (error) { notify(error.message, true); }
  finally { Object.keys(changes).forEach(key => pendingFields.delete(key)); }
}
function renderFixtureList() {
  const list = $('fixture-list'); list.replaceChildren();
  for (const fixture of layout.fixtures) {
    const row = document.createElement('div'); row.className = 'fixture-item'; row.dataset.id = fixture.id;
    const button = document.createElement('button'); button.className = 'fixture-select'; button.title = `Inspect ${fixture.name}`;
    const icon = document.createElement('span'); icon.className = 'fixture-icon'; icon.textContent = fixtureIcons[fixture.type] || '◈';
    const info = document.createElement('span');
    const name = document.createElement('span'); name.className = 'fixture-name'; name.textContent = fixture.name;
    const count = document.createElement('span'); count.className = 'fixture-count'; count.textContent = `${fixture.pixels.length.toLocaleString()} pixels · RGB`;
    info.append(name, count); button.append(icon, info); button.onclick = () => selectFixture(selectedId === fixture.id ? null : fixture.id);
    const label = document.createElement('label'); label.className = 'toggle';
    const input = document.createElement('input'); input.type = 'checkbox'; input.checked = true; input.setAttribute('aria-label', `Enable ${fixture.name}`);
    input.onchange = () => control({ fixtureEnabled: { [fixture.id]: input.checked } });
    label.append(input, document.createElement('span')); row.append(button, label); list.append(row);
  }
  $('pixel-count').textContent = layout.fixtures.reduce((sum, f) => sum + f.pixels.length, 0).toLocaleString();
  $('help-channels').textContent = layout.channelCount || Math.max(...layout.fixtures.map(f => f.startChannel - 1 + f.pixels.length * 3));
}
function selectFixture(id) {
  if (editor?.active && id) { editor.selectFixture(id); return; }
  selectedId = id; scene?.selectFixture(id);
  for (const row of $('fixture-list').children) row.classList.toggle('selected', row.dataset.id === id);
  const fixture = layout.fixtures.find(f => f.id === id);
  $('selected-fixture').hidden = !fixture;
  if (fixture) {
    $('selected-fixture').textContent = `${fixture.name} · ${fixture.pixels.length} pixels`;
    const info = $('selection-info'); info.replaceChildren();
    const eyebrow = document.createElement('span'); eyebrow.className = 'eyebrow'; eyebrow.textContent = 'SELECTED FIXTURE';
    const title = document.createElement('p'); title.textContent = fixture.name;
    const detail = document.createElement('div'); detail.className = 'patch-detail';
    for (const [label, value] of [['RGB channels', `${fixture.startChannel}–${fixture.startChannel + fixture.pixels.length * 3 - 1}`], ['Pixel count', fixture.pixels.length.toLocaleString()]]) {
      const field = document.createElement('div'); const caption = document.createElement('span'); caption.textContent = label;
      const number = document.createElement('strong'); number.textContent = value; field.append(caption, number); detail.append(field);
    }
    info.append(eyebrow, title, detail);
  } else {
    $('selection-info').innerHTML = '<span class="eyebrow">YOUR VIRTUAL DISPLAY</span><p>Every dot is an individually addressed RGB pixel.</p><p class="muted">Select a fixture to inspect its channel patch.</p>';
  }
}
function progress(input) { input.style.setProperty('--progress', `${(Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min)) * 100}%`); }
function updateSlider(id, value, label, format) {
  if (!activeSliders.has(id) && !pendingFields.has(id === 'brightness' ? 'brightness' : 'speed')) $(id).value = value;
  progress($(id)); $(label).textContent = format(Number($(id).value));
}
function render(snapshot) {
  state = snapshot;
  if (snapshot.rgb && scene) { const raw = atob(snapshot.rgb); scene.setFrame(Uint8Array.from(raw, char => char.charCodeAt(0))); }
  if (editor?.active) { editor.remoteRevision(snapshot.layoutRevision); return; }
  if (layout && snapshot.layoutRevision !== undefined && snapshot.layoutRevision !== layout.revision && !refreshingLayout) refreshLayout();
  // Keep RGB output at the full receive rate while updating text at 10 Hz.
  const now = performance.now();
  if (now - lastInterfaceUpdate < 100) return;
  lastInterfaceUpdate = now;
  const live = state.mode === 'live'; document.body.classList.toggle('is-live', live);
  $('demo-source').classList.toggle('active', !live); $('live-source').classList.toggle('active', live);
  $('demo-source').setAttribute('aria-pressed', String(!live)); $('live-source').setAttribute('aria-pressed', String(live));
  $('source-hint').textContent = live ? 'Listening for RGB frames from your sequencer.' : 'A ready-to-play show. No hardware needed.';
  $('live-details').hidden = !live;
  $('mode-badge').classList.toggle('live', live);
  $('mode-badge').replaceChildren(document.createElement('i'), document.createTextNode(live ? 'LIVE INPUT' : 'DEMO'));
  for (const button of document.querySelectorAll('[data-effect]')) {
    button.classList.toggle('selected', button.dataset.effect === state.effect);
    button.setAttribute('aria-pressed', String(button.dataset.effect === state.effect)); button.disabled = live;
  }
  $('effect-title').textContent = live ? 'Sequencer input' : effectNames[state.effect] || state.effect;
  $('album-art').className = `album-art ${live ? 'rainbow' : state.effect}`;
  $('transport-label').textContent = live ? (state.playing ? 'LIVE CHANNEL STREAM' : 'LIVE FRAME HELD') : state.playing ? 'NOW PLAYING' : 'PAUSED';
  $('play-button').innerHTML = `<svg><use href="#i-${state.playing ? 'pause' : 'play'}"/></svg>`;
  $('play-button').setAttribute('aria-label', state.playing ? 'Pause show' : 'Play show');
  $('play-button').disabled = false; $('restart-button').disabled = live; $('seek').disabled = live; $('speed').disabled = live; $('bpm').disabled = live;
  updateSlider('brightness', Math.round(state.brightness * 100), 'brightness-value', v => `${v}%`);
  updateSlider('speed', Math.round(state.speed * 100), 'speed-value', v => `${(v / 100).toFixed(2).replace(/0$/, '')}×`);
  if (document.activeElement !== $('bpm')) $('bpm').value = state.bpm;
  if (!seekActive && !pendingFields.has('time')) $('seek').value = state.time;
  $('current-time').textContent = live ? 'LIVE' : formatTime(Number($('seek').value));
  $('duration').textContent = live ? 'STREAM' : formatTime(state.duration); $('seek').max = state.duration;
  document.querySelector('.loop-label').hidden = live;
  $('playhead').style.left = `${Math.min(Number($('seek').value) / state.duration * 100, 100)}%`;
  $('frame-status').textContent = `${state.fps} FPS output · Frame ${Number(state.frame).toLocaleString()}`;
  $('channel-status').textContent = `${Number(state.channelCount).toLocaleString()} channels · RGB 8-bit`;
  const universeSize = state.universeSize || 510; const universeCount = Math.ceil(state.channelCount / universeSize);
  $('universe-count').textContent = `${universeCount} universes`;
  $('help-universe-count').textContent = universeCount; $('help-universe-size').textContent = universeSize; $('help-universe').textContent = state.startUniverse || 1;
  $('help-ddp').textContent = state.receivers.ddp.port; $('ddp-port').textContent = state.receivers.ddp.port; $('sacn-port').textContent = state.receivers.sacn.port;
  // xLights should use the loopback address for the common same-machine setup.
  const host = location.hostname === 'localhost' ? '127.0.0.1' : location.hostname;
  $('live-host').textContent = host; $('help-host').textContent = host;
  $('relay-address').textContent = `${state.relay.host} : ${state.relay.port}`; $('help-relay').textContent = state.relay.port;
  if (!pendingFields.has('relayEnabled')) $('relay-toggle').checked = state.relay.enabled;
  $('relay-dot').style.background = state.relay.error ? '#e6a484' : state.relay.enabled ? '#79e8bd' : '#647389';
  $('relay-status').textContent = state.relay.error || (state.relay.enabled ? 'Sending the same RGB frames' : 'Bridge paused');
  for (const row of $('fixture-list').children) {
    const enabled = state.fixtureEnabled?.[row.dataset.id] !== false;
    row.classList.toggle('disabled', !enabled);
    if (!pendingFields.has('fixtureEnabled')) row.querySelector('input').checked = enabled;
  }
  $('ddp-packets').replaceChildren(document.createTextNode(Number(state.receivers.ddp.packets).toLocaleString()), Object.assign(document.createElement('span'), { textContent: ' packets' }));
  $('sacn-packets').replaceChildren(document.createTextNode(Number(state.receivers.sacn.packets).toLocaleString()), Object.assign(document.createElement('span'), { textContent: ' packets' }));
  const errors = [state.receivers.ddp.error, state.receivers.sacn.error].filter(Boolean);
  const age = state.lastPacketAge;
  const ageText = age == null ? 'Waiting for your first frame' : age < 1 ? 'Receiving RGB frames' : `Last packet ${Math.floor(age)}s ago`;
  $('live-age').textContent = ageText;
  $('network-badge').textContent = errors.length ? 'ERROR' : age != null && age < 1 ? 'ACTIVE' : 'IDLE';
  $('network-note').textContent = errors.join(' · ') || (age == null ? 'Ready for a local sequencer.' : ageText);
}

$('demo-source').onclick = () => control({ mode: 'demo' });
$('live-source').onclick = () => control({ mode: 'live', playing: true });
document.querySelectorAll('[data-effect]').forEach(button => { button.onclick = () => control({ effect: button.dataset.effect }); });
$('play-button').onclick = () => { if (state) control({ playing: !state.playing }); };
$('restart-button').onclick = () => control({ time: 0 });
$('relay-toggle').onchange = () => control({ relayEnabled: $('relay-toggle').checked });
let sliderTimer;
for (const id of ['brightness', 'speed']) {
  const input = $(id);
  input.addEventListener('pointerdown', () => activeSliders.add(id));
  const send = () => control({ [id]: Number(input.value) / 100 });
  input.addEventListener('input', () => {
    progress(input); $(id + '-value').textContent = id === 'brightness' ? `${input.value}%` : `${(input.value / 100).toFixed(2)}×`;
    clearTimeout(sliderTimer); sliderTimer = setTimeout(send, 90);
  });
  input.addEventListener('change', () => { clearTimeout(sliderTimer); send(); activeSliders.delete(id); });
  input.addEventListener('pointerup', () => activeSliders.delete(id));
}
$('bpm').onchange = () => {
  if (!$('bpm').checkValidity()) { $('bpm').reportValidity(); return; }
  control({ bpm: Number($('bpm').value) });
};
$('seek').addEventListener('pointerdown', () => { seekActive = true; });
$('seek').addEventListener('input', () => { seekActive = true; $('current-time').textContent = formatTime(Number($('seek').value)); $('playhead').style.left = `${Number($('seek').value) / (state?.duration || 120) * 100}%`; });
$('seek').addEventListener('change', async () => { await control({ time: Number($('seek').value) }); seekActive = false; });
window.addEventListener('pointerup', () => { activeSliders.clear(); if (seekActive) setTimeout(() => { seekActive = false; }, 300); });
document.querySelectorAll('[data-view]').forEach(button => {
  button.onclick = () => { scene?.setCamera(button.dataset.view); document.querySelectorAll('[data-view]').forEach(b => { b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button)); }); };
});
$('camera-reset').onclick = () => scene?.resetCamera();
for (const [id, method] of [['snow-button', 'setSnow'], ['glow-button', 'setGlow']]) {
  $(id).onclick = () => { const enabled = !$(id).classList.contains('active'); $(id).classList.toggle('active', enabled); $(id).setAttribute('aria-pressed', String(enabled)); scene?.[method](enabled); };
}
function download(url, filename) { const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); }
$('capture-button').onclick = () => { if (scene) { download(scene.capture(), 'noel-light-show.png'); notify('Preview image saved'); } };
$('download-layout').onclick = () => { if (layout) { const url = URL.createObjectURL(new Blob([JSON.stringify(layout, null, 2)], { type: 'application/json' })); download(url, 'light-show-layout.json'); setTimeout(() => URL.revokeObjectURL(url), 1000); } };
const showHelp = () => $('help-dialog').showModal();
$('help-button').onclick = showHelp; $('setup-card').onclick = showHelp;
$('close-help').onclick = () => $('help-dialog').close(); $('help-done').onclick = () => $('help-dialog').close();
$('help-dialog').addEventListener('click', event => { if (event.target === $('help-dialog')) { const r = $('help-dialog').getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) $('help-dialog').close(); } });
document.addEventListener('keydown', event => {
  if (event.code === 'Space' && !editor?.active && !['INPUT', 'BUTTON', 'TEXTAREA', 'SELECT', 'A'].includes(document.activeElement?.tagName) && !$('help-dialog').open && state?.mode === 'demo') { event.preventDefault(); control({ playing: !state.playing }); }
});
document.addEventListener('scene-error', event => notify(event.detail, true));
function applyLayout(next) {
  layout = next; scene?.setLayout(next); renderFixtureList(); selectFixture(null);
  const env = next.scene?.environment;
  if (env) for (const [id, key] of [['snow-button', 'snowfall'], ['glow-button', 'glow']]) { $(id).classList.toggle('active', env[key]); $(id).setAttribute('aria-pressed', String(env[key])); }
  document.querySelector('.workspace-label > span:nth-child(2)').textContent = next.name;
  document.querySelector('.stage-title').textContent = `${next.name} / Night scene`;
}
async function refreshLayout() {
  refreshingLayout = true;
  try { const response = await fetch('/api/layout'); if (response.ok && !editor?.active) applyLayout(await response.json()); }
  catch (error) { console.error('Could not refresh scene', error); }
  finally { refreshingLayout = false; }
}
async function initialize() {
  try {
    const response = await fetch('/api/layout'); if (!response.ok) throw new Error(`Layout request failed (${response.status})`);
    layout = await response.json(); renderFixtureList();
    try {
      const module = await import('./scene.js'); scene = module.createScene($('scene-container'), layout, selectFixture);
      editor = createEditor({ getLayout: () => layout, getScene: () => scene, applyLayout, notify, download });
      applyLayout(layout);
      $('scene-loading').hidden = true; if (!scene.snowEnabled) { $('snow-button').classList.remove('active'); $('snow-button').setAttribute('aria-pressed', 'false'); }
    } catch (error) {
      $('scene-loading').querySelector('strong').textContent = '3D preview unavailable';
      $('scene-loading').querySelector('span:last-child').textContent = 'Enable WebGL, or check that the local Three.js assets are present.';
      console.error(error); notify(`Could not initialize 3D preview: ${error.message}`, true);
    }
    const events = new EventSource('/api/events');
    events.onopen = () => setConnected(true);
    events.onerror = () => setConnected(false);
    events.onmessage = message => { try { render(JSON.parse(message.data)); } catch (error) { console.error('Invalid frame', error); } };
    // Also load immediately; EventSource reconnects automatically after an interruption.
    const frame = await fetch('/api/frame'); if (frame.ok) render(await frame.json());
  } catch (error) {
    setConnected(false); $('scene-loading').querySelector('strong').textContent = 'Could not connect to the service';
    $('scene-loading').querySelector('span:last-child').textContent = 'Start python server.py, then reload this page.'; notify(error.message, true);
  }
}
initialize();
