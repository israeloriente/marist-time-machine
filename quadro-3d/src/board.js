// ---------------------------------------------------------------------------
// board.js — monta o quadro nos dois modos.
//
//   'crown'  — coroamento no topo (cruz, frontão, cornija) e o display 16:9
//              ocupando o resto do painel.
//   'single' — moldura limpa, display 16:9 ocupando o painel inteiro, com a
//              identidade numa placa gravada no rodapé.
//
// O display é o MESMO painel 1920x1080 nos dois; o que muda é o gabinete em
// volta dele. As dimensões saem de layout(mode) em config.js.
// ---------------------------------------------------------------------------

import * as THREE from "three";
import { DISPLAY, FRAME, PALETTE, PLATE, Z, layout } from "./config.js";
import { box, plane } from "./geo.js";
import { buildCrown } from "./crown.js";
import { createLiveScreen, displayHardware, screenGlass, screenMaterials } from "./screens.js";
import * as T from "./textures.js";

export function buildBoard({ mode = "crown", envMap = null, screenUrl, fallbackUrl } = {}) {
  const L = layout(mode);
  const board = new THREE.Group();
  board.name = `quadro-${mode}`;
  const screens = [];

  // ---- materiais ----
  const dark = new THREE.MeshStandardMaterial({
    color: PALETTE.frame,
    roughness: 0.42,
    metalness: 0.12,
  });
  const paper = new THREE.MeshStandardMaterial({
    map: T.agedPaper({ seed: 7 }),
    color: 0xffffff,
    roughness: 0.86,
    metalness: 0,
  });
  const chrome = new THREE.MeshStandardMaterial({
    color: PALETTE.chrome,
    roughness: 0.28,
    metalness: 0.9,
  });
  const screenMats = screenMaterials();

  // ---- caixa e moldura ----
  board.add(box(dark, L.boardW, L.boardH, FRAME.depth * 0.28, 0, 0, Z.back - 0.03));
  const f = FRAME.face;
  // Quatro barras de ponta a ponta no seu eixo, pros cantos ficarem sobrepostos
  // como numa moldura real.
  board.add(box(dark, L.boardW, f, FRAME.depth, 0, L.panelHalfH + f / 2, Z.back));
  board.add(box(dark, L.boardW, f, FRAME.depth, 0, -L.panelHalfH - f / 2, Z.back));
  board.add(box(dark, f, L.boardH, FRAME.depth, -L.panelHalfW - f / 2, 0, Z.back));
  board.add(box(dark, f, L.boardH, FRAME.depth, L.panelHalfW + f / 2, 0, Z.back));

  // ---- fundo do painel ----
  if (mode === "crown") {
    // Creme por trás de tudo. Só fica visível na faixa do coroamento — o
    // display cobre o resto.
    board.add(plane(paper, L.panelW, L.panelH, 0, 0, Z.panel));
  } else {
    // Nenhuma parte do fundo fica visível, mas um creme atrás de uma tela
    // apagada denunciaria a farsa. Escuro evita isso.
    board.add(
      plane(
        new THREE.MeshStandardMaterial({ color: 0x0c0e12, roughness: 0.9 }),
        L.panelW, L.panelH, 0, 0, Z.panel,
      ),
    );
  }

  // ---- coroamento ----
  if (mode === "crown") board.add(buildCrown({ dark, layout: L }));

  // ---- display ----
  const { width: w, height: h } = DISPLAY;
  const y = L.screenY;

  board.add(
    displayHardware({
      w, h, y, z: Z.screen,
      bezel: DISPLAY.bezel, depth: DISPLAY.depth, materials: screenMats,
    }),
  );

  const live = createLiveScreen({ w, h, y, z: Z.screen + 0.002, url: screenUrl, fallbackUrl });
  board.add(live.punch);
  board.add(screenGlass({ w, h, y, z: Z.screen + 0.006, envMap }));
  screens.push(live);

  // ---- placa gravada (só no modo sem coroamento) ----
  if (mode !== "crown") {
    const plateMap = T.engravedPlate({
      lines: ["FORMANDOS MARISTA · 2003", "TURMA SÃO MARCELINO CHAMPAGNAT"],
    });
    board.add(
      box(
        new THREE.MeshStandardMaterial({ map: plateMap, roughness: 0.3, metalness: 0.85 }),
        PLATE.width, PLATE.height, 0.006,
        0, -L.panelHalfH - f / 2, Z.frameFront,
      ),
    );
    for (const sx of [-1, 1]) {
      const s = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.008, 12), chrome);
      s.rotation.x = Math.PI / 2;
      s.position.set(sx * (PLATE.width / 2 + 0.03), -L.panelHalfH - f / 2, Z.frameFront + 0.004);
      board.add(s);
    }
  }

  return { board, layout: L, materials: { dark, paper, chrome }, screens };
}

// ---------------------------------------------------------------------------
// Vidro grande da frente.
//
// Superfície reflexiva translúcida em vez de `transmission`: transmissão numa
// chapa desse tamanho custa um render pass inteiro e ainda lava o que está
// atrás. Sobre um display, legibilidade vence — daí a opacidade baixa e o tom
// neutro, e não o acrílico amarelado de 2003.
// ---------------------------------------------------------------------------
export function buildGlass(envMap, L) {
  const group = new THREE.Group();
  group.name = "vidro";

  const w = L.boardW - 0.02;
  const h = L.boardH - 0.02;

  const sheet = plane(
    new THREE.MeshPhysicalMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.035,
      roughness: 0.06,
      metalness: 0,
      clearcoat: 1,
      clearcoatRoughness: 0.03,
      envMap,
      envMapIntensity: 1.25,
      depthWrite: false,
      side: THREE.FrontSide,
    }),
    w, h, 0, 0, Z.glass,
  );
  sheet.name = "chapa";
  sheet.renderOrder = 8; // depois do punch-through, pra compor sobre a tela viva
  group.add(sheet);

  // Faixas de reflexo — as diagonais claras que aparecem na foto original.
  const glare = new THREE.Mesh(
    new THREE.PlaneGeometry(1, 1),
    new THREE.MeshBasicMaterial({
      map: T.glareTexture(),
      transparent: true,
      opacity: 0.05,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  glare.scale.set(w, h, 1);
  glare.position.set(0, 0, Z.glass + 0.001);
  glare.renderOrder = 9;
  glare.name = "reflexos";
  group.add(glare);

  return group;
}
