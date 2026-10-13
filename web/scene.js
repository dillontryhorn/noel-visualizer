import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

// Pixel addresses and editable scenery are both supplied by the shared layout.
export function createScene(container, initialLayout, onSelect) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.prepend(renderer.domElement);
  renderer.domElement.setAttribute('aria-label', 'Interactive 3D Christmas light display and scene editor');
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#152238');
  scene.fog = new THREE.FogExp2('#152238', .017);
  const camera = new THREE.PerspectiveCamera(40, 1, .1, 150);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = .07;
  controls.maxPolarAngle = Math.PI / 2 - .015;
  controls.minDistance = 2;
  controls.maxDistance = 100;
  let view = 'perspective';
  function setCamera(name) {
    view = name;
    controls.target.set(.7, 2.2, .9);
    const positions = { perspective: [14, 9, 23], front: [.7, 5.5, 28], top: [.7, 28, 1.01] };
    camera.position.fromArray(positions[name] || positions.perspective);
    controls.update();
  }
  setCamera('perspective');
  scene.add(new THREE.HemisphereLight('#bdcfee', '#25303b', 1.45));
  const moon = new THREE.DirectionalLight('#b6cff5', 2.2);
  moon.position.set(-8, 18, 12);
  moon.castShadow = true;
  moon.shadow.mapSize.set(1024, 1024);
  moon.shadow.camera.left = -30; moon.shadow.camera.right = 30;
  moon.shadow.camera.top = 30; moon.shadow.camera.bottom = -30;
  moon.shadow.bias = -.001;
  moon.shadow.normalBias = .04;
  scene.add(moon);
  const blueFill = new THREE.DirectionalLight('#849dcd', .65);
  blueFill.position.set(14, 7, -6); scene.add(blueFill);

  let seed = 17;
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const snowCanvas = document.createElement('canvas'); snowCanvas.width = snowCanvas.height = 256;
  const snowContext = snowCanvas.getContext('2d');
  snowContext.fillStyle = '#aabed3'; snowContext.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 6000; i++) {
    snowContext.fillStyle = `rgba(${random() > .5 ? '255,255,255' : '35,61,89'},${random() * .085})`;
    snowContext.fillRect(random() * 256, random() * 256, 1 + random() * 2, 1 + random() * 2);
  }
  const snowTexture = new THREE.CanvasTexture(snowCanvas);
  snowTexture.wrapS = snowTexture.wrapT = THREE.RepeatWrapping; snowTexture.repeat.set(16, 16);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(120, 120), new THREE.MeshStandardMaterial({ color: '#8398b2', map: snowTexture, roughness: .93 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -.065; ground.receiveShadow = true; scene.add(ground);
  const scenery = new THREE.Group(); scene.add(scenery);
  const wires = new THREE.Group(); scene.add(wires);
  const objects = new Map(), fixtureWires = new Map(), fixtureBoxes = new Map(), fixtureRanges = new Map();

  function material(color, extra = {}) { return new THREE.MeshStandardMaterial({ color, roughness: .88, ...extra }); }
  function addMesh(parent, geometry, mat, position = [0, 0, 0], shadow = true) {
    const mesh = new THREE.Mesh(geometry, mat);
    mesh.position.fromArray(position); mesh.castShadow = shadow; mesh.receiveShadow = shadow;
    parent.add(mesh); return mesh;
  }
  function box(parent, w, h, d, x, y, z, mat, shadow = true) {
    return addMesh(parent, new THREE.BoxGeometry(w, h, d), mat, [x, y, z], shadow);
  }
  function buildHouse(parent, color) {
    const m = {
      walls: material(color || '#354251'), trim: material('#abb9c5', { roughness: .75 }),
      roof: material('#c5d3df', { roughness: .94 }), door: material('#263b37'),
      pine: material('#122d2b', { roughness: .95 }), black: material('#1e2e3d'),
      glass: material('#bea77c', { emissive: '#d3964d', emissiveIntensity: .65, roughness: .32 }),
    };
    box(parent, 8, 3.5, 4, 0, 1.75, -2, m.walls);
    const siding = new THREE.LineBasicMaterial({ color: '#1e2d3f', transparent: true, opacity: .55 });
    for (let y = .12; y < 3.5; y += .16) {
      parent.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-4, y, .009), new THREE.Vector3(4, y, .009)]), siding));
    }
    const gableShape = new THREE.Shape(); gableShape.moveTo(-4, 3.5); gableShape.lineTo(0, 5.8); gableShape.lineTo(4, 3.5); gableShape.closePath();
    addMesh(parent, new THREE.ExtrudeGeometry(gableShape, { depth: 4, bevelEnabled: false }), m.walls, [0, 0, -4]);
    function roofPlane(vertices) {
      const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
      geometry.setIndex([0, 1, 2, 0, 2, 3]); geometry.computeVertexNormals();
      addMesh(parent, geometry, material('#c7d6e5', { roughness: .96, side: THREE.DoubleSide }));
    }
    roofPlane([-3.98, 3.49, -.02, 0, 5.79, -.02, 0, 5.79, -3.98, -3.98, 3.49, -3.98]);
    roofPlane([0, 5.79, -.02, 3.98, 3.49, -.02, 3.98, 3.49, -3.98, 0, 5.79, -3.98]);
    box(parent, .17, 3.5, .06, -3.96, 1.75, .02, m.trim);
    box(parent, .17, 3.5, .06, 3.96, 1.75, .02, m.trim);
    box(parent, 8.2, .18, .05, 0, .10, .022, m.trim);
    box(parent, .7, 1.3, .8, 2.5, 5.02, -2.4, m.black);
    box(parent, .86, .13, .96, 2.5, 5.7, -2.4, m.roof);
    for (const x of [-2.3, 2.3]) {
      box(parent, 1.68, 1.58, .035, x, 2, .019, m.trim);
      box(parent, 1.48, 1.38, .018, x, 2, .047, m.glass, false);
      box(parent, .045, 1.38, .018, x, 2, .062, m.black, false);
      box(parent, 1.48, .045, .018, x, 2, .062, m.black, false);
      box(parent, 1.84, .08, .10, x, 1.18, .02, m.roof);
      const room = new THREE.PointLight('#ffc675', .6, 3, 2); room.position.set(x, 2, .5); parent.add(room);
    }
    box(parent, 1.3, 2.43, .035, 0, 1.215, .019, m.trim);
    box(parent, 1.13, 2.3, .025, 0, 1.17, .047, m.door);
    box(parent, .83, .66, .018, 0, 1.8, .065, m.glass, false);
    for (const y of [.45, .96]) box(parent, .77, .32, .018, 0, y, .065, m.black, false);
    addMesh(parent, new THREE.SphereGeometry(.045, 12, 8), material('#d5b77a', { metalness: .7, roughness: .3 }), [.43, 1.2, .25]);
    addMesh(parent, new THREE.TorusGeometry(.24, .075, 8, 24), m.pine, [0, 1.75, .30]);
    box(parent, .10, .12, .03, 0, 1.51, .40, material('#9e3441'), false);
    box(parent, 1.8, .12, .8, 0, -.03, .52, m.roof);
  }
  function buildPine(parent, color) {
    const branches = material(color || '#122d2b', { roughness: .95 });
    const snowCap = material('#c5d3df', { roughness: .94 });
    box(parent, .09, .18, .09, 0, .09, 0, material('#1e2e3d'));
    for (const [base, height, radius] of [[.1, .58, .5], [.32, .47, .37], [.62, .38, .24]]) {
      addMesh(parent, new THREE.ConeGeometry(radius, height, 9), branches, [0, base + height / 2, 0]);
      addMesh(parent, new THREE.ConeGeometry(radius * .74, height * .75, 9), snowCap, [0, base + height * .625, 0]);
    }
  }
  function buildArch(parent, center, width, height, mat) {
    const points = [];
    for (let i = 0; i <= 40; i++) {
      const angle = i / 40 * Math.PI;
      points.push(new THREE.Vector3(center + Math.cos(angle) * width / 2, Math.sin(angle) * height, -.04));
    }
    addMesh(parent, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 40, .022, 5, false), mat);
  }
  function buildObject(data) {
    const group = new THREE.Group(); group.name = data.name; group.userData.sceneObjectId = data.id;
    const color = data.color;
    if (data.type === 'house') buildHouse(group, color);
    else if (data.type === 'pine') buildPine(group, color);
    else if (data.type === 'cone') {
      addMesh(group, new THREE.ConeGeometry(.5, 1, 16, 1, true), material(color || '#112827', { transparent: true, opacity: .55, side: THREE.DoubleSide, roughness: 1 }), [0, .5, 0]).renderOrder = -1;
      box(group, .015, 1, .015, 0, .5, 0, material('#1e2e3d'), false);
    } else if (data.type === 'box') box(group, 1, 1, 1, 0, .5, 0, material(color || '#70839a'));
    else if (data.type === 'arch') buildArch(group, 0, 1, 1, material(color || '#abb9c5'));
    else if (data.type === 'arches') {
      const mat = material(color || '#abb9c5');
      for (const center of [-2.3, 0, 2.3]) buildArch(group, center, 2, 1.2, mat);
    }
    group.position.fromArray(data.position || [0, 0, 0]);
    group.rotation.set(...(data.rotation || [0, 0, 0]).map(THREE.MathUtils.degToRad), 'XYZ');
    group.scale.fromArray(data.scale || [1, 1, 1]);
    group.updateMatrixWorld(true);
    scenery.add(group); objects.set(data.id, group);
  }
  function disposeTree(root) {
    const geometries = new Set(), materials = new Set();
    root.traverse(object => {
      if (object.geometry) geometries.add(object.geometry);
      if (object.material) for (const mat of Array.isArray(object.material) ? object.material : [object.material]) materials.add(mat);
    });
    for (const geometry of geometries) geometry.dispose();
    for (const mat of materials) mat.dispose();
    root.clear();
  }

  const starsPositions = [];
  for (let i = 0; i < 130; i++) starsPositions.push((random() - .5) * 110, 12 + random() * 35, -22 - random() * 22);
  const starsGeometry = new THREE.BufferGeometry(); starsGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starsPositions, 3));
  scene.add(new THREE.Points(starsGeometry, new THREE.PointsMaterial({ size: .10, color: '#b2c6e4', transparent: true, opacity: .65, depthWrite: false })));
  let geometry = new THREE.BufferGeometry(), colorAttribute, colors, channelOffsets = [], pixelFixtures = [], layout, lastFrame;
  const pixelMaterial = new THREE.ShaderMaterial({
    vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { pointSize: { value: 17 * renderer.getPixelRatio() }, glow: { value: 1 } },
    vertexShader: `varying vec3 pixelColor; uniform float pointSize;
      void main(){pixelColor=color; vec4 mv=modelViewMatrix*vec4(position,1.); gl_PointSize=clamp(pointSize*24./max(1.,-mv.z),2.,60.); gl_Position=projectionMatrix*mv;}`,
    fragmentShader: `varying vec3 pixelColor; uniform float glow;
      void main(){vec2 p=gl_PointCoord*2.-1.;float r=dot(p,p);if(r>1.)discard;float core=exp(-r*(glow>.5?32.:4.));float halo=glow*exp(-r*5.)*.19;
      float intensity=max(pixelColor.r,max(pixelColor.g,pixelColor.b));gl_FragColor=vec4(pixelColor*(core*1.9+halo),intensity);}`,
  });
  const pixels = new THREE.Points(geometry, pixelMaterial); pixels.frustumCulled = false; scene.add(pixels);
  const selectedBox = new THREE.Box3Helper(new THREE.Box3(), '#9ce5c2');
  selectedBox.material.transparent = true; selectedBox.material.opacity = .5; selectedBox.visible = false; scene.add(selectedBox);
  const fixturePivot = new THREE.Object3D(); scene.add(fixturePivot);
  const transform = new TransformControls(camera, renderer.domElement);
  transform.setSize(.85); transform.enabled = false; transform.detach();
  const transformHelper = transform.getHelper(); scene.add(transformHelper);
  let editor = { enabled: false, linkFixtures: true }, editorSelection = null, selectedId = null, dragState = null, down = null;
  const snowCount = 750, snowPositions = new Float32Array(snowCount * 3), snowVelocity = [];
  for (let i = 0; i < snowCount; i++) { snowPositions.set([(random() - .5) * 42, random() * 20, (random() - .35) * 38], i * 3); snowVelocity.push(.25 + random() * .5); }
  const snowGeometry = new THREE.BufferGeometry(); snowGeometry.setAttribute('position', new THREE.BufferAttribute(snowPositions, 3));
  const snow = new THREE.Points(snowGeometry, new THREE.PointsMaterial({ color: '#cadbec', size: .035, transparent: true, opacity: .6, depthWrite: false })); scene.add(snow);
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function setGlow(enabled) {
    pixelMaterial.uniforms.glow.value = enabled ? 1 : 0;
    pixelMaterial.uniforms.pointSize.value = (enabled ? 17 : 4) * renderer.getPixelRatio();
  }
  function setFrame(rgb) {
    lastFrame = rgb;
    for (let i = 0; i < channelOffsets.length; i++) {
      const c = channelOffsets[i];
      if (editor.enabled && c >= rgb.length) {
        // New draft fixtures have no server channels until Save. Keep their pixels
        // visible while arranging them without changing live channel data.
        colors[i * 3] = .8; colors[i * 3 + 1] = .6; colors[i * 3 + 2] = .3;
      } else {
        colors[i * 3] = (rgb[c] || 0) / 255; colors[i * 3 + 1] = (rgb[c + 1] || 0) / 255; colors[i * 3 + 2] = (rgb[c + 2] || 0) / 255;
      }
    }
    colorAttribute.needsUpdate = true;
  }
  function selectionBounds() {
    if (editor.enabled && editorSelection?.kind === 'object') {
      const object = objects.get(editorSelection.id);
      return object ? new THREE.Box3().setFromObject(object) : undefined;
    }
    return fixtureBoxes.get(editor.enabled ? editorSelection?.id : selectedId);
  }
  function updateSelectionBox() {
    const bounds = selectionBounds();
    selectedBox.visible = !!bounds && !bounds.isEmpty();
    if (selectedBox.visible) selectedBox.box.copy(bounds).expandByScalar(.1);
  }
  function focusSelection() {
    const bounds = selectionBounds();
    if (!bounds || bounds.isEmpty()) return false;
    const center = bounds.getCenter(new THREE.Vector3());
    const radius = Math.max(.15, bounds.getSize(new THREE.Vector3()).length() / 2);
    const verticalFov = THREE.MathUtils.degToRad(camera.getEffectiveFOV());
    const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
    const distance = Math.max(controls.minDistance * 1.15, radius / Math.sin(Math.min(verticalFov, horizontalFov) / 2) * 1.15);
    const direction = camera.position.clone().sub(controls.target);
    if (direction.lengthSq() < 1e-8) direction.set(14, 9, 23);
    direction.normalize();
    controls.target.copy(center); camera.position.copy(center).addScaledVector(direction, distance);
    controls.maxDistance = Math.max(100, distance * 3);
    camera.far = Math.max(150, distance + radius * 4); camera.updateProjectionMatrix();
    controls.update();
    return true;
  }
  function attachSelection() {
    if (dragState) {
      // Switching tools or selection during a gesture cancels its uncommitted preview.
      setLayout(layout);
      return;
    }
    transform.detach(); transform.enabled = editor.enabled;
    if (!editor.enabled || !editorSelection) { updateSelectionBox(); return; }
    if (editorSelection.kind === 'object') {
      const object = objects.get(editorSelection.id);
      if (object) transform.attach(object);
    } else {
      const bounds = fixtureBoxes.get(editorSelection.id);
      if (bounds && !bounds.isEmpty()) {
        bounds.getCenter(fixturePivot.position); fixturePivot.rotation.set(0, 0, 0); fixturePivot.scale.set(1, 1, 1);
        fixturePivot.updateMatrixWorld(true); transform.attach(fixturePivot);
      }
    }
    updateSelectionBox();
  }
  function selectEditorObject(selection) {
    editorSelection = selection ? { kind: selection.kind, id: selection.id } : null;
    if (selection?.kind === 'fixture') selectedId = selection.id;
    attachSelection();
  }
  function selectFixture(id) {
    selectedId = id;
    if (editor.enabled) selectEditorObject(id ? { kind: 'fixture', id } : null);
    else updateSelectionBox();
  }
  function setLayout(nextLayout) {
    layout = nextLayout;
    transform.detach(); dragState = null; transform.dragging = false; controls.enabled = true;
    disposeTree(scenery); disposeTree(wires);
    objects.clear(); fixtureWires.clear(); fixtureBoxes.clear(); fixtureRanges.clear();
    for (const object of layout.scene?.objects || []) buildObject(object);
    const positions = []; channelOffsets = []; pixelFixtures = [];
    for (const fixture of layout.fixtures) {
      const vectors = fixture.pixels.map(point => new THREE.Vector3(...point));
      fixtureBoxes.set(fixture.id, new THREE.Box3().setFromPoints(vectors));
      fixtureRanges.set(fixture.id, { start: pixelFixtures.length, count: vectors.length });
      const wireGroup = new THREE.Group(); wires.add(wireGroup); fixtureWires.set(fixture.id, wireGroup);
      const wireMaterial = new THREE.LineBasicMaterial({ color: '#435569', transparent: true, opacity: .55 });
      let segment = [];
      const addSegment = () => { if (segment.length > 1) wireGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(segment), wireMaterial)); segment = []; };
      for (let i = 0; i < vectors.length; i++) {
        const point = vectors[i];
        if (i && point.distanceTo(vectors[i - 1]) > .35) addSegment();
        segment.push(point); positions.push(...point.toArray());
        channelOffsets.push(fixture.startChannel - 1 + i * 3); pixelFixtures.push(fixture.id);
      }
      addSegment();
      if (!wireGroup.children.length) wireMaterial.dispose();
    }
    geometry.dispose(); geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.attributes.position.setUsage(THREE.DynamicDrawUsage);
    colors = new Float32Array(positions.length);
    colorAttribute = new THREE.BufferAttribute(colors, 3); colorAttribute.setUsage(THREE.DynamicDrawUsage); geometry.setAttribute('color', colorAttribute);
    pixels.geometry = geometry;
    if (lastFrame) setFrame(lastFrame);
    const environment = layout.scene?.environment || {};
    scene.background.set(environment.skyColor || '#152238'); scene.fog.color.copy(scene.background);
    ground.material.color.set(environment.groundColor || '#8398b2'); ground.visible = environment.groundVisible !== false;
    renderer.toneMappingExposure = environment.exposure ?? 1.2;
    snow.visible = environment.snowfall !== false && !reduceMotion; setGlow(environment.glow !== false);
    attachSelection();
  }

  // Linked fixture geometry follows the object while dragging; the editor receives
  // one final matrix delta so undo and persistence remain atomic.
  transform.addEventListener('dragging-changed', event => { controls.enabled = !event.value; });
  transform.addEventListener('mouseDown', () => {
    if (!editorSelection || !transform.object) return;
    transform.object.updateMatrixWorld(true);
    const ids = editorSelection.kind === 'fixture' ? [editorSelection.id]
      : editor.linkFixtures ? layout.scene.objects.find(object => object.id === editorSelection.id)?.fixtureIds || [] : [];
    dragState = {
      selection: { ...editorSelection }, target: transform.object, previousMatrix: transform.object.matrixWorld.clone(),
      positions: geometry.attributes.position.array.slice(), fixtureIds: ids,
    };
    down = null;
  });
  transform.addEventListener('objectChange', () => {
    if (!dragState) return;
    dragState.target.scale.clampScalar(.001, 1000);
    dragState.target.updateMatrixWorld(true);
    const delta = dragState.target.matrixWorld.clone().multiply(dragState.previousMatrix.clone().invert());
    const positions = geometry.attributes.position.array, point = new THREE.Vector3();
    for (const id of dragState.fixtureIds) {
      const range = fixtureRanges.get(id);
      if (!range) continue;
      const bounds = new THREE.Box3();
      for (let i = range.start; i < range.start + range.count; i++) {
        point.fromArray(dragState.positions, i * 3).applyMatrix4(delta); point.toArray(positions, i * 3); bounds.expandByPoint(point);
      }
      fixtureBoxes.set(id, bounds);
      const wire = fixtureWires.get(id); wire.matrixAutoUpdate = false; wire.matrix.copy(delta); wire.updateMatrixWorld(true);
    }
    geometry.attributes.position.needsUpdate = true; geometry.computeBoundingSphere(); updateSelectionBox();
  });
  transform.addEventListener('mouseUp', () => {
    if (!dragState) return;
    const completed = dragState; dragState = null;
    completed.target.updateMatrixWorld(true);
    const matrix = completed.target.matrixWorld.toArray();
    if (matrix.every((value, i) => Math.abs(value - completed.previousMatrix.elements[i]) < 1e-9)) return;
    try {
      editor.onTransform?.({
        ...completed.selection, matrix, previousMatrix: completed.previousMatrix.toArray(),
        position: completed.target.position.toArray(), rotation: completed.target.rotation.toArray().slice(0, 3).map(THREE.MathUtils.radToDeg),
        scale: completed.target.scale.toArray(), end: true,
      });
    } catch (error) {
      setLayout(layout);
      document.dispatchEvent(new CustomEvent('scene-error', { detail: error.message || 'That scene transformation could not be applied.' }));
    }
  });
  const raycaster = new THREE.Raycaster(); raycaster.params.Points.threshold = .15;
  const pointerDown = event => { down = transform.dragging ? null : [event.clientX, event.clientY]; };
  const pointerUp = event => {
    const start = down; down = null;
    if (!start || Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 5) return;
    const rect = renderer.domElement.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera);
    const pixelHit = raycaster.intersectObject(pixels)[0];
    if (editor.enabled) {
      // Pixels take precedence when in front of scenery. Mesh picking still works
      // when all RGB channels are blacked out.
      const sceneryHit = raycaster.intersectObjects([...objects.values()], true).find(hit => hit.object.isMesh);
      let selection = null;
      if (pixelHit && (!sceneryHit || pixelHit.distance <= sceneryHit.distance + .18)) selection = { kind: 'fixture', id: pixelFixtures[pixelHit.index] };
      else if (sceneryHit) {
        let object = sceneryHit.object;
        while (object && !object.userData.sceneObjectId) object = object.parent;
        if (object) selection = { kind: 'object', id: object.userData.sceneObjectId };
      }
      selectEditorObject(selection); editor.onSelectObject?.(selection);
    } else if (pixelHit) onSelect?.(pixelFixtures[pixelHit.index]);
  };
  renderer.domElement.addEventListener('pointerdown', pointerDown);
  renderer.domElement.addEventListener('pointerup', pointerUp);
  const contextLost = event => {
    event.preventDefault(); document.dispatchEvent(new CustomEvent('scene-error', { detail: 'The graphics context was lost. Reload the page to restore the preview.' }));
  };
  renderer.domElement.addEventListener('webglcontextlost', contextLost);
  function resize() {
    const width = Math.max(1, container.clientWidth), height = Math.max(1, container.clientHeight);
    renderer.setSize(width, height); camera.aspect = width / height; camera.updateProjectionMatrix();
  }
  const observer = new ResizeObserver(resize); observer.observe(container); resize();
  setLayout(initialLayout);
  let last = performance.now(), animationId, disposed = false;
  function animate(now) {
    if (disposed) return;
    animationId = requestAnimationFrame(animate);
    if (now - last < 1000 / 30) return;
    const dt = Math.min((now - last) / 1000, .05); last = now;
    if (snow.visible) {
      for (let i = 0; i < snowCount; i++) {
        snowPositions[i * 3 + 1] -= snowVelocity[i] * dt;
        snowPositions[i * 3] += Math.sin(now / 3000 + i) * dt * .12;
        if (snowPositions[i * 3 + 1] < 0) snowPositions[i * 3 + 1] = 20;
      }
      snowGeometry.attributes.position.needsUpdate = true;
    }
    controls.update(); renderer.render(scene, camera);
  }
  animationId = requestAnimationFrame(animate);
  return {
    setLayout, setFrame, setCamera, focusSelection, resetCamera() { setCamera(view); }, selectFixture, selectEditorObject,
    setEditor(options) {
      editor = { ...editor, ...options };
      if (!editor.enabled) editorSelection = null;
      attachSelection();
      if (lastFrame) setFrame(lastFrame);
    },
    setTransformMode(mode) { if (['translate', 'rotate', 'scale'].includes(mode)) transform.setMode(mode); },
    setSnow(enabled) { snow.visible = enabled; }, setGlow,
    capture() { renderer.render(scene, camera); return renderer.domElement.toDataURL('image/png'); },
    get selectedId() { return selectedId; }, get snowEnabled() { return snow.visible; },
    dispose() {
      disposed = true; cancelAnimationFrame(animationId); observer.disconnect(); controls.dispose(); transform.dispose();
      moon.shadow.dispose();
      scene.remove(transformHelper);
      renderer.domElement.removeEventListener('pointerdown', pointerDown); renderer.domElement.removeEventListener('pointerup', pointerUp);
      renderer.domElement.removeEventListener('webglcontextlost', contextLost);
      disposeTree(scene); snowTexture.dispose(); renderer.dispose(); renderer.domElement.remove();
    },
  };
}

