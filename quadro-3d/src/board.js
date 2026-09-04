// ---------------------------------------------------------------------------
// board.js — monta o quadro nos dois modos.
//
//   'original' — o quadro físico de 2003, com as fotos impressas.
//   'single'   — moldura reaproveitada, miolo inteiro é um display só.
//
// Ordem de montagem nos modos com painel, de trás pra frente: caixa e moldura
// -> painel creme -> pilastras e rodapés -> janelinhas -> fotos ou displays ->
// letras do cabeçalho -> placa da turma -> acrílico.
// ---------------------------------------------------------------------------

import * as THREE from "three";
import {
  BAYS,
  BAY_GEOM as G,
  BOARD,
  FACADE,
  HEADER,
  PALETTE,
  PANEL,
  PANEL_HALF_H,
  PANEL_HALF_W,
  PILASTER_W,
  PLAQUE,
  SINGLE,
  Z,
} from "./config.js";
import { box, plane } from "./geo.js";
import { buildFacade } from "./facade.js";
import { createLiveScreen, displayHardware, screenGlass, screenMaterials } from "./screens.js";
import * as T from "./textures.js";

// ---------------------------------------------------------------------------
// Distribuição horizontal dos vãos
//
// Cada ala vai da borda interna do painel até a fachada. Entre os vãos entram
// pilastras pretas, e há uma em cada extremidade — por isso são (n + 1)
// pilastras para n vãos.
// ---------------------------------------------------------------------------
function layoutWing(side) {
  const bays = BAYS.filter((b) => b.side === side);
  // Da borda externa em direção ao centro. À direita a ordem visual inverte.
  const ordered = side === -1 ? bays : [...bays].reverse();

  const outerX = side * PANEL_HALF_W;
  const innerX = side * FACADE.halfWidth;
  const span = Math.abs(outerX - innerX);
  const bayTotal = ordered.reduce((s, b) => s + b.width, 0);
  // A sobra vai pras pilastras, então a ala fecha exatamente na fachada mesmo
  // se as larguras dos vãos não baterem certinho.
  const pilaster = Math.max(PILASTER_W, (span - bayTotal) / (ordered.length + 1));

  const out = [];
  let cursor = outerX;
  const step = -side; // caminhamos do exterior pro centro
  cursor += step * pilaster;
  for (const bay of ordered) {
    const start = cursor;
    const end = cursor + step * bay.width;
    out.push({ ...bay, center: (start + end) / 2, pilaster });
    cursor = end + step * pilaster;
  }
  return { bays: out, pilaster, outerX, innerX };
}

// ---------------------------------------------------------------------------
// Um vão: janelas em cima, foto (ou display) no meio, rótulo + nomes embaixo,
// janelas de novo na base.
// ---------------------------------------------------------------------------
function buildBay(bay, index, mats) {
  const group = new THREE.Group();
  group.name = `vao-${bay.key}`;

  // ---- janelinhas ----
  const winStep = bay.width / bay.windows;
  for (const rowY of [G.windowRowTopY, G.windowRowBottomY]) {
    for (let i = 0; i < bay.windows; i++) {
      const x = bay.center - bay.width / 2 + winStep * (i + 0.5);
      group.add(box(mats.window, G.windowW, G.windowH, 0.012, x, rowY, Z.window));
    }
  }

  const photoH = G.photoTop - G.photoBottom;
  const photoY = (G.photoTop + G.photoBottom) / 2;
  const isPortrait = bay.photo.kind === "portrait";

  {
    // ---- foto impressa, colada e coberta por chapa sobre espaçadores ----
    const photoW = isPortrait ? Math.min(bay.width - 0.12, photoH * 0.72) : bay.width - 0.055;
    const tex = isPortrait
      ? T.portrait({ cast: bay.photo.cast, seed: 40 + index })
      : T.classPhoto({
          cast: bay.photo.cast, rows: bay.photo.rows,
          perRow: bay.photo.perRow, seed: 100 + index * 17,
        });

    group.add(
      plane(
        new THREE.MeshStandardMaterial({ map: tex, roughness: 0.68, metalness: 0 }),
        photoW, photoH, bay.center, photoY, Z.photoGlass - 0.016,
      ),
    );

    const glassW = photoW + 0.028;
    const glassH = photoH + 0.028;
    const glass = plane(mats.photoGlass, glassW, glassH, bay.center, photoY, Z.photoGlass);
    glass.castShadow = false;
    group.add(glass);

    for (const sx of [-1, 1]) {
      for (const sy of [-1, 1]) {
        const stud = new THREE.Mesh(new THREE.CylinderGeometry(0.0055, 0.0055, 0.02, 12), mats.chrome);
        stud.rotation.x = Math.PI / 2;
        stud.position.set(
          bay.center + sx * (glassW / 2 - 0.012),
          photoY + sy * (glassH / 2 - 0.012),
          Z.photoGlass - 0.008,
        );
        stud.castShadow = true;
        group.add(stud);
      }
    }
  }

  // ---- rótulo + lista de nomes, impressos direto no fundo ----
  const namesH = G.namesTop - G.namesBottom;
  const namesTex = T.nameBlock({
    w: 512,
    h: Math.round((512 * namesH) / bay.width),
    title: bay.title,
    columns: bay.columns,
    seed: 300 + index * 31,
  });
  group.add(
    plane(
      new THREE.MeshStandardMaterial({ map: namesTex, transparent: true, roughness: 0.85, metalness: 0 }),
      bay.width - 0.03, namesH, bay.center, (G.namesTop + G.namesBottom) / 2, Z.panel + 0.004,
    ),
  );

  return group;
}

// ---------------------------------------------------------------------------
export function buildBoard({ mode = "original", envMap = null, screenUrl, fallbackUrl } = {}) {
  const board = new THREE.Group();
  board.name = `quadro-${mode}`;
  const screens = [];

  // ---- materiais ----
  const dark = new THREE.MeshStandardMaterial({ color: PALETTE.frame, roughness: 0.42, metalness: 0.12 });
  const paper = new THREE.MeshStandardMaterial({
    map: T.agedPaper({ seed: 7 }), color: 0xffffff, roughness: 0.86, metalness: 0,
  });
  const chrome = new THREE.MeshStandardMaterial({ color: PALETTE.chrome, roughness: 0.28, metalness: 0.9 });
  const windowMat = new THREE.MeshStandardMaterial({ map: T.windowPane(), roughness: 0.5, metalness: 0.05 });
  const photoGlass = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, transparent: true, opacity: 0.045, roughness: 0.07,
    metalness: 0, clearcoat: 1, clearcoatRoughness: 0.04, depthWrite: false,
  });
  const screenMats = screenMaterials();
  const mats = { window: windowMat, photoGlass, chrome };

  // ---- caixa e moldura (iguais nos três modos) ----
  board.add(box(dark, BOARD.width, BOARD.height, BOARD.depth * 0.28, 0, 0, Z.back - 0.03));
  const f = BOARD.frameFace;
  // Quatro barras de ponta a ponta no seu eixo, pros cantos ficarem sobrepostos
  // como numa moldura real.
  board.add(box(dark, BOARD.width, f, BOARD.depth, 0, PANEL_HALF_H + f / 2, Z.back));
  board.add(box(dark, BOARD.width, f, BOARD.depth, 0, -PANEL_HALF_H - f / 2, Z.back));
  board.add(box(dark, f, BOARD.height, BOARD.depth, -PANEL_HALF_W - f / 2, 0, Z.back));
  board.add(box(dark, f, BOARD.height, BOARD.depth, PANEL_HALF_W + f / 2, 0, Z.back));

  if (mode === "single") {
    buildSinglePanel(board, { dark, chrome, screenMats, envMap, screenUrl, fallbackUrl, screens });
    return { board, materials: { dark, paper, chrome, photoGlass }, screens };
  }

  // ---- painel creme ----
  board.add(plane(paper, PANEL.width, PANEL.height, 0, 0, Z.panel));

  // ---- alas ----
  let bayIndex = 0;
  for (const side of [-1, 1]) {
    const { bays, pilaster, outerX, innerX } = layoutWing(side);
    for (const bay of bays) board.add(buildBay(bay, bayIndex++, mats));

    // Pilastras: uma em cada borda de vão; recolhemos as posições únicas.
    const edges = new Set();
    for (const bay of bays) {
      edges.add(+(bay.center - (bay.width / 2 + pilaster / 2)).toFixed(4));
      edges.add(+(bay.center + (bay.width / 2 + pilaster / 2)).toFixed(4));
    }
    const shaftH = G.top - G.bottom;
    const shaftY = (G.top + G.bottom) / 2;
    for (const x of edges) {
      board.add(box(dark, pilaster, shaftH, 0.018, x, shaftY, Z.panel));
      board.add(box(dark, pilaster * 1.5, G.capitalTop - G.top, 0.024, x, (G.capitalTop + G.top) / 2, Z.panel));
      board.add(box(dark, pilaster * 1.5, G.bottom - G.plinthBottom, 0.024, x, (G.bottom + G.plinthBottom) / 2, Z.panel));
    }

    // Rodapé preto correndo sob toda a ala.
    board.add(
      box(dark, Math.abs(outerX - innerX), 0.03, 0.016, (outerX + innerX) / 2, G.plinthBottom - 0.015, Z.panel),
    );
  }

  // ---- fachada PIOX ----
  const piox = T.reliefText(
    [{ text: "PIOX", x: 0.5, y: 0.08, size: 0.78, align: "center", condense: 1.0 }],
    { w: 512, h: 160, color: "#171a1f" },
  );
  const facade = buildFacade({
    dark, paper, windowMat, signMap: piox.map,
    plaqueMap: T.nameBlock({ w: 440, h: 320, title: "", columns: 2, seed: 77 }),
  });
  board.add(facade);

  // ---- cabeçalho em letra aplicada ----
  const headerW = HEADER.x1 - HEADER.x0;
  const headerH = HEADER.yTop - HEADER.yBottom;
  const header = T.reliefText(
    [
      { text: "FORMANDOS", x: 0.01, y: 0.04, size: 0.32, condense: 0.88 },
      { text: "MARISTA", x: 0.01, y: 0.5, size: 0.32, condense: 0.88 },
      { text: "2003", x: 0.63, y: 0.06, size: 0.6, condense: 0.9 },
    ],
    { w: 2048, h: Math.round((2048 * headerH) / headerW), color: "#1e3a63" },
  );
  board.add(
    plane(
      new THREE.MeshStandardMaterial({
        map: header.map, bumpMap: header.bump, bumpScale: 12,
        transparent: true, roughness: 0.44, metalness: 0.16,
      }),
      headerW, headerH, (HEADER.x0 + HEADER.x1) / 2, (HEADER.yTop + HEADER.yBottom) / 2, Z.letters,
    ),
  );

  // ---- placa da turma ----
  board.add(
    box(
      new THREE.MeshStandardMaterial({ map: T.turmaPlaque(), roughness: 0.38, metalness: 0.55 }),
      PLAQUE.x1 - PLAQUE.x0, PLAQUE.yTop - PLAQUE.yBottom, 0.01,
      (PLAQUE.x0 + PLAQUE.x1) / 2, (PLAQUE.yTop + PLAQUE.yBottom) / 2, Z.panel + 0.004,
    ),
  );

  return { board, materials: { dark, paper, chrome, photoGlass, window: windowMat }, screens };
}

// ---------------------------------------------------------------------------
// Modo 'single': o miolo inteiro é um display.
// ---------------------------------------------------------------------------
function buildSinglePanel(board, { dark, chrome, screenMats, envMap, screenUrl, fallbackUrl, screens }) {
  const m = SINGLE.margin;
  const w = PANEL.width - m * 2 - SINGLE.bezel * 2;
  const h = PANEL.height - m * 2 - SINGLE.bezel * 2;

  // Fundo escuro no lugar do painel creme: nenhuma parte dele fica visível,
  // mas evita ver a caixa preta crua se o display não carregar.
  board.add(
    plane(new THREE.MeshStandardMaterial({ color: 0x0c0e12, roughness: 0.9 }), PANEL.width, PANEL.height, 0, 0, Z.panel),
  );

  board.add(
    displayHardware({
      w, h, z: Z.photoGlass, bezel: SINGLE.bezel, depth: SINGLE.depth, materials: screenMats,
    }),
  );

  const live = createLiveScreen({ w, h, z: Z.photoGlass + 0.002, url: screenUrl, fallbackUrl });
  board.add(live.punch);
  board.add(screenGlass({ w, h, z: Z.photoGlass + 0.006, envMap }));
  screens.push(live);

  // A identidade do objeto migra pra uma placa gravada no rodapé da moldura —
  // que é exatamente o que uma instalação real faz ao trocar o miolo por tela.
  const plateMap = T.engravedPlate({
    lines: ["FORMANDOS MARISTA · 2003", "TURMA SÃO MARCELINO CHAMPAGNAT"],
  });
  board.add(
    box(
      new THREE.MeshStandardMaterial({ map: plateMap, roughness: 0.3, metalness: 0.85 }),
      SINGLE.plateWidth, SINGLE.plateHeight, 0.006,
      0, -PANEL_HALF_H - BOARD.frameFace / 2, Z.frameFront,
    ),
  );

  // Dois parafusos de acabamento, um de cada lado da placa.
  for (const sx of [-1, 1]) {
    const s = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.008, 12), chrome);
    s.rotation.x = Math.PI / 2;
    s.position.set(sx * (SINGLE.plateWidth / 2 + 0.03), -PANEL_HALF_H - BOARD.frameFace / 2, Z.frameFront + 0.004);
    board.add(s);
  }
}

// ---------------------------------------------------------------------------
// Acrílico grande da frente.
//
// Modelado como superfície reflexiva translúcida em vez de `transmission`:
// transmissão numa chapa desse tamanho custa um render pass inteiro e ainda
// lava o que está atrás. Aqui a legibilidade vence.
// ---------------------------------------------------------------------------
export function buildAcrylic(envMap, { mode = "original" } = {}) {
  const group = new THREE.Group();
  group.name = "acrilico";

  // O acrílico amarelado de 2003 sobre um display não faz sentido: uma
  // instalação real troca a chapa velha por vidro antirreflexo neutro. Nos
  // modos com tela a vidraça vira quase invisível, senão a UI fica encardida.
  const screenMode = mode !== "original";
  const tint = screenMode ? 0xffffff : 0xfff0c8;
  const sheetOpacity = screenMode ? 0.035 : 0.11;
  const glareOpacity = screenMode ? 0.05 : 0.16;

  const sheet = plane(
    new THREE.MeshPhysicalMaterial({
      color: tint, // amarelado no original; neutro sobre display
      transparent: true, opacity: sheetOpacity, roughness: 0.06, metalness: 0,
      clearcoat: 1, clearcoatRoughness: 0.03,
      envMap, envMapIntensity: 1.25, depthWrite: false, side: THREE.FrontSide,
    }),
    BOARD.width - 0.02, BOARD.height - 0.02, 0, 0, Z.acrylic,
  );
  sheet.name = "chapa";
  sheet.renderOrder = 8; // depois do punch-through, pra compor sobre a tela viva
  group.add(sheet);

  // Faixas de reflexo — as diagonais claras que aparecem na foto original.
  const glare = new THREE.Mesh(
    new THREE.PlaneGeometry(1, 1),
    new THREE.MeshBasicMaterial({
      map: T.glareTexture(), transparent: true, opacity: glareOpacity,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }),
  );
  glare.scale.set(BOARD.width - 0.02, BOARD.height - 0.02, 1);
  glare.position.set(0, 0, Z.acrylic + 0.001);
  glare.renderOrder = 9;
  glare.name = "reflexos";
  group.add(glare);

  return group;
}
