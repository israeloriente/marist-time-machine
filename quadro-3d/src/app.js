// ---------------------------------------------------------------------------
// app.js — bootstrap: renderer, cena, câmeras, HUD e loop.
//
// Dois renderers empilhados: o WebGL (canvas) e o CSS3DRenderer (DOM). O
// segundo é o que faz a aplicação web rodar de verdade dentro do display. A
// ordem entre eles depende do modo — ver setTouch().
// ---------------------------------------------------------------------------

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { CSS3DRenderer } from "three/examples/jsm/renderers/CSS3DRenderer.js";
import { DISPLAY, ROOM, SCREEN } from "./config.js";
import { buildBoard, buildGlass } from "./board.js";
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

// A camada CSS3D tem a própria cena. `cssRoot` espelha o deslocamento vertical
// do quadro, senão a página viva descola do buraco do punch-through quando os
// modos têm alturas diferentes.
const cssScene = new THREE.Scene();
const cssRoot = new THREE.Group();
cssScene.add(cssRoot);

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
let mode = "crown";
let current = null;

function getMode(name) {
  if (built.has(name)) return built.get(name);

  const { board, layout: L, screens } = buildBoard({
    mode: name,
    envMap,
    screenUrl,
    fallbackUrl: SCREEN.fallback,
  });
  const glass = buildGlass(envMap, L);
  board.add(glass);

  // Os dois modos têm alturas diferentes. Deslocamos cada um pra que a BASE do
  // quadro caia sempre na mesma altura da parede — assim a composição com o
  // rodapé de pedra não pula ao trocar de modo.
  const offsetY = ROOM.boardBottom + L.boardH / 2;
  board.position.y = offsetY;

  const entry = {
    board,
    layout: L,
    offsetY,
    glass,
    sheet: glass.getObjectByName("chapa"),
    glare: glass.getObjectByName("reflexos"),
    live: screens.filter((s) => s.kind === "live"),
  };
  built.set(name, entry);
  return entry;
}

function setMode(name) {
  if (current) {
    scene.remove(current.board);
    // Suspender a tela que sai importa: os dois modos têm webview, e sem isso
    // ficariam duas instâncias da aplicação rodando ao mesmo tempo.
    for (const s of current.live) {
      cssRoot.remove(s.object);
      s.setActive(false);
    }
  }
  mode = name;
  current = getMode(name);
  scene.add(current.board);
  cssRoot.position.y = current.offsetY;
  for (const s of current.live) {
    cssRoot.add(s.object);
    s.setActive(true);
  }

  applyToggles();
  for (const b of document.querySelectorAll(".hud-modes button")) {
    b.classList.toggle("on", b.dataset.mode === name);
  }
  goTo("frontal", 700);
  updateFoot();
}

// ---------------------------------------------------------------------------
// Câmera
//
// As posições abaixo são em coordenadas LOCAIS do quadro; o deslocamento
// vertical do modo é somado na hora de aplicar.
// ---------------------------------------------------------------------------
const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 0.05, 60);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 0.4;
controls.maxDistance = 7;
controls.maxPolarAngle = Math.PI * 0.92;

// Distância que enquadra o quadro inteiro com uma folga de 22 cm, dado o FOV
// vertical de 38°. Como os dois gabinetes têm alturas diferentes, as vistas
// gerais são derivadas dela em vez de fixas.
const HALF_FOV = THREE.MathUtils.degToRad(19);
const fitDistance = (L) => (L.boardH / 2 + 0.22) / Math.tan(HALF_FOV);

function views(L) {
  const d = fitDistance(L);
  return {
    frontal: { pos: [0, 0, d], target: [0, 0, 0] },
    tresquartos: { pos: [d * 0.63, d * 0.2, d * 0.82], target: [0, -0.02, 0] },
    rasante: { pos: [-d * 0.67, -d * 0.13, d * 0.41], target: [0.3, -0.05, 0] },
    // Detalhes: distância absoluta, porque o coroamento e a tela têm o mesmo
    // tamanho nos dois modos.
    frontao: { pos: [0, 0.5, 1.15], target: [0, 0.5, 0.04] },
    tela: { pos: [0, -0.22, 1.5], target: [0, -0.22, 0.03] },
  };
}

let tween = null;
function goTo(name, ms = 950) {
  if (!current) return;
  const v = views(current.layout)[name];
  if (!v) return;
  const dy = current.offsetY;
  tween = {
    t: 0, ms,
    fromPos: camera.position.clone(),
    toPos: new THREE.Vector3(v.pos[0], v.pos[1] + dy, v.pos[2]),
    fromTarget: controls.target.clone(),
    toTarget: new THREE.Vector3(v.target[0], v.target[1] + dy, v.target[2]),
  };
  for (const b of document.querySelectorAll(".hud-views button")) {
    b.classList.toggle("on", b.dataset.view === name);
  }
}

controls.update();

const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

// ---------------------------------------------------------------------------
// Modo toque
//
// A camada CSS3D não pode ser ocluída por geometria WebGL nem receber eventos
// ao mesmo tempo em que o canvas os recebe. Então há duas composições:
//
//   orbitar  — CSS3D ATRÁS do canvas. O plano punch-through abre o buraco, o
//              vidro e a moldura compõem por cima, e a órbita funciona.
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
const cbVidro = document.getElementById("t-acrilico");
const cbReflexo = document.getElementById("t-reflexo");
const cbSala = document.getElementById("t-sala");
const cbGirar = document.getElementById("t-girar");

function applyToggles() {
  if (!current) return;
  current.sheet.visible = cbVidro.checked;
  current.glare.visible = cbReflexo.checked;
  room.visible = cbSala.checked;
  autoRotate = cbGirar.checked;
}
for (const el of [cbVidro, cbReflexo, cbSala, cbGirar]) {
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
  const views = { 1: "frontal", 2: "tresquartos", 3: "frontao", 4: "tela", 5: "rasante" };
  if (views[e.key]) return goTo(views[e.key]);
  switch (e.key.toLowerCase()) {
    case "q": return setMode("crown");
    case "w": return setMode("single");
    case "t": return setTouch(true);
    case "a": return toggle(cbVidro);
    case "r": return toggle(cbReflexo);
    case "p": return toggle(cbSala);
    case "g": return toggle(cbGirar);
  }
});

const meta = document.getElementById("foot-meta");
function updateFoot() {
  const v = window.quadro?.versions;
  const live = current?.live[0];
  const L = current?.layout;
  meta.textContent = [
    `display ${DISPLAY.width * 1000}×${DISPLAY.height * 1000} (16:9)`,
    L ? `quadro ${L.boardW.toFixed(2)}×${L.boardH.toFixed(2)} m` : null,
    live ? `${live.engine} · ${screenUrl}` : `three r${THREE.REVISION}`,
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

// O primeiro setMode precisa esperar o DOM ficar pronto.
//
// O custom element <webview> do Electron só é registrado DEPOIS do parse dos
// scripts da página: medido, `document.createElement('webview')` durante o
// parse não tem `loadURL`, e no DOMContentLoaded já tem. Como o modo padrão
// monta uma tela viva na hora, detectar cedo demais faz createLiveScreen cair
// no <iframe> — que esbarra em X-Frame-Options e derruba justamente o caso de
// uso principal.
function start() {
  setMode("crown");
  // Só some com o loader depois do primeiro frame realmente pintado — as
  // texturas procedurais levam alguns ms pra gerar.
  requestAnimationFrame(() =>
    requestAnimationFrame(() => document.getElementById("loader").classList.add("hide")),
  );
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
  start();
}
