// ---------------------------------------------------------------------------
// app.js — bootstrap: renderer, cena, câmeras, HUD e loop.
//
// Dois renderers empilhados: o WebGL (canvas) e o CSS3DRenderer (DOM). O
// segundo existe só pra versão de display único, onde a aplicação web roda de
// verdade dentro da tela. A ordem entre eles depende do modo — ver setTouch().
// ---------------------------------------------------------------------------

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { CSS3DRenderer } from "three/examples/jsm/renderers/CSS3DRenderer.js";
import { BOARD, SCREEN } from "./config.js";
import { buildAcrylic, buildBoard } from "./board.js";
import { buildLights, buildRoom } from "./scene-env.js";
import * as T from "./textures.js";

// ---------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------
const canvas = document.getElementById("stage");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

T.setAnisotropy(renderer.capabilities.getMaxAnisotropy());

const cssRenderer = new CSS3DRenderer();
cssRenderer.setSize(window.innerWidth, window.innerHeight);
const cssLayer = document.getElementById("css3d");
cssLayer.appendChild(cssRenderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x14161a);
const cssScene = new THREE.Scene();

// ---------------------------------------------------------------------------
// Ambiente (reflexos): equirect procedural -> PMREM. Sem HDR externo, o app
// roda offline e o resultado é idêntico em toda máquina.
// ---------------------------------------------------------------------------
const pmrem = new THREE.PMREMGenerator(renderer);
pmrem.compileEquirectangularShader();
const equirect = T.environmentEquirect();
equirect.mapping = THREE.EquirectangularReflectionMapping;
const envMap = pmrem.fromEquirectangular(equirect).texture;
scene.environment = envMap;
equirect.dispose();
pmrem.dispose();

const room = buildRoom();
const lights = buildLights();
scene.add(room, lights.group);

// ---------------------------------------------------------------------------
// Modos. Construídos sob demanda e mantidos em cache: montar os dois de cara
// custaria duas vezes o tempo de geração de textura na abertura.
// ---------------------------------------------------------------------------
const screenUrl = window.quadro?.screenUrl || SCREEN.defaultUrl;
const built = new Map();
let mode = "original";
let current = null;

function getMode(name) {
  if (built.has(name)) return built.get(name);

  const { board, screens } = buildBoard({
    mode: name,
    envMap,
    screenUrl,
    fallbackUrl: SCREEN.fallback,
  });
  const acrylic = buildAcrylic(envMap, { mode: name });
  board.add(acrylic);

  const entry = {
    board,
    acrylic,
    screens,
    sheet: acrylic.getObjectByName("chapa"),
    glare: acrylic.getObjectByName("reflexos"),
    live: screens.filter((s) => s.kind === "live"),
  };
  built.set(name, entry);
  return entry;
}

function setMode(name) {
  if (current) {
    scene.remove(current.board);
    for (const s of current.live) cssScene.remove(s.object);
  }
  mode = name;
  current = getMode(name);
  scene.add(current.board);
  for (const s of current.live) cssScene.add(s.object);

  // Só faz sentido oferecer o modo toque onde existe uma tela viva.
  const hasLive = current.live.length > 0;
  btnToque.disabled = !hasLive;
  btnToque.title = hasLive ? "" : "Só disponível na versão de display único";
  if (!hasLive && touching) setTouch(false);

  applyToggles();
  for (const b of document.querySelectorAll(".hud-modes button")) {
    b.classList.toggle("on", b.dataset.mode === name);
  }
  goTo(defaultView(name), 700);
  updateFoot();
}

const defaultView = (m) => (m === "single" ? "frontal" : "tresquartos");

// ---------------------------------------------------------------------------
// Câmera
// ---------------------------------------------------------------------------
const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 0.05, 60);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 0.55;
controls.maxDistance = 9;
controls.maxPolarAngle = Math.PI * 0.92;

// Distâncias calculadas pro quadro caber inteiro em 16:9 com o FOV de 38°:
// meia-largura 2.1 m / tan(hfov/2) ~= 3.9 m, mais margem.
const VIEWS = {
  frontal: { pos: [0, 0.0, 4.45], target: [0, 0, 0] },
  tresquartos: { pos: [2.9, 0.95, 3.75], target: [0, -0.04, 0] },
  fachada: { pos: [0.08, 0.1, 1.62], target: [0, 0.06, 0.05] },
  turmas: { pos: [-1.05, 0.0, 1.28], target: [-1.08, -0.02, 0.03] },
  rasante: { pos: [-3.1, -0.55, 1.95], target: [0.5, -0.05, 0] },
};

let tween = null;
function goTo(name, ms = 950) {
  const v = VIEWS[name];
  if (!v) return;
  tween = {
    t: 0, ms,
    fromPos: camera.position.clone(), toPos: new THREE.Vector3(...v.pos),
    fromTarget: controls.target.clone(), toTarget: new THREE.Vector3(...v.target),
  };
  for (const b of document.querySelectorAll(".hud-views button")) {
    b.classList.toggle("on", b.dataset.view === name);
  }
}

camera.position.set(...VIEWS.tresquartos.pos);
controls.target.set(...VIEWS.tresquartos.target);
controls.update();

const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

// ---------------------------------------------------------------------------
// Modo toque
//
// A camada CSS3D não pode ser ocluída por geometria WebGL nem receber eventos
// ao mesmo tempo em que o canvas os recebe. Então há duas composições:
//
//   orbitar  — CSS3D ATRÁS do canvas. O plano punch-through abre o buraco, o
//              acrílico e a moldura compõem por cima, e a órbita funciona.
//   tocar    — CSS3D NA FRENTE, com eventos ligados e a órbita travada. A
//              página fica clicável de verdade, ao custo de ficar por cima de
//              tudo (o que só se nota fora do enquadramento frontal).
// ---------------------------------------------------------------------------
let touching = false;

function setTouch(on) {
  touching = on && current?.live.length > 0;
  cssLayer.classList.toggle("front", touching);
  cssLayer.classList.toggle("interactive", touching);
  controls.enabled = !touching;
  btnToque.classList.toggle("on", touching);
  document.body.classList.toggle("touching", touching);
  if (touching) goTo("frontal", 700);
}

// ---------------------------------------------------------------------------
// HUD
// ---------------------------------------------------------------------------
const btnToque = document.getElementById("btn-toque");

for (const b of document.querySelectorAll(".hud-views button")) {
  b.addEventListener("click", () => goTo(b.dataset.view));
}
for (const b of document.querySelectorAll(".hud-modes button")) {
  b.addEventListener("click", () => setMode(b.dataset.mode));
}
btnToque.addEventListener("click", () => setTouch(!touching));
document.getElementById("btn-reload").addEventListener("click", () => {
  for (const s of current?.live ?? []) s.reload();
});

let autoRotate = false;
const cbAcrilico = document.getElementById("t-acrilico");
const cbReflexo = document.getElementById("t-reflexo");
const cbSala = document.getElementById("t-sala");
const cbGirar = document.getElementById("t-girar");

function applyToggles() {
  if (!current) return;
  current.sheet.visible = cbAcrilico.checked;
  current.glare.visible = cbReflexo.checked;
  room.visible = cbSala.checked;
  autoRotate = cbGirar.checked;
}
for (const el of [cbAcrilico, cbReflexo, cbSala, cbGirar]) {
  el.addEventListener("change", applyToggles);
}

const luz = document.getElementById("t-luz");
luz.addEventListener("input", () => {
  renderer.toneMappingExposure = parseFloat(luz.value);
});

const toggle = (el) => {
  el.checked = !el.checked;
  el.dispatchEvent(new Event("change"));
};

window.addEventListener("keydown", (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  // Em modo toque o teclado pertence à página embutida; só Esc sai.
  if (touching) {
    if (e.key === "Escape") setTouch(false);
    return;
  }
  const views = { 1: "frontal", 2: "tresquartos", 3: "fachada", 4: "turmas", 5: "rasante" };
  if (views[e.key]) return goTo(views[e.key]);
  switch (e.key.toLowerCase()) {
    case "q": return setMode("original");
    case "w": return setMode("single");
    case "t": return setTouch(true);
    case "a": return toggle(cbAcrilico);
    case "r": return toggle(cbReflexo);
    case "p": return toggle(cbSala);
    case "g": return toggle(cbGirar);
  }
});

const meta = document.getElementById("foot-meta");
function updateFoot() {
  const v = window.quadro?.versions;
  const live = current?.live[0];
  meta.textContent = [
    `${BOARD.width.toFixed(2)} × ${BOARD.height.toFixed(2)} m`,
    live ? `display: ${live.engine} · ${screenUrl}` : `three r${THREE.REVISION}`,
    v ? `electron ${v.electron}` : null,
  ].filter(Boolean).join(" · ");
}

// ---------------------------------------------------------------------------
// Loop
// ---------------------------------------------------------------------------
function resize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  cssRenderer.setSize(w, h);
}
window.addEventListener("resize", resize);

const clock = new THREE.Clock();

renderer.setAnimationLoop(() => {
  const dt = clock.getDelta();

  if (tween) {
    tween.t = Math.min(1, tween.t + (dt * 1000) / tween.ms);
    const k = easeInOut(tween.t);
    camera.position.lerpVectors(tween.fromPos, tween.toPos, k);
    controls.target.lerpVectors(tween.fromTarget, tween.toTarget, k);
    if (tween.t >= 1) tween = null;
  } else if (autoRotate && !touching) {
    const a = dt * 0.16;
    const p = camera.position;
    p.set(p.x * Math.cos(a) - p.z * Math.sin(a), p.y, p.x * Math.sin(a) + p.z * Math.cos(a));
  }

  controls.update();
  renderer.render(scene, camera);
  if (current?.live.length) cssRenderer.render(cssScene, camera);
});

setMode("original");

// Só some com o loader depois do primeiro frame realmente pintado — as
// texturas procedurais levam alguns ms pra gerar.
requestAnimationFrame(() =>
  requestAnimationFrame(() => document.getElementById("loader").classList.add("hide")),
);
