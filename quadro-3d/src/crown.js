// ---------------------------------------------------------------------------
// crown.js — o coroamento PIOX.
//
// É o que sobrou da maquete do prédio: cruz, frontão triangular e a cornija
// que o apoia. Colunas, porta, pórtico, janelas e a placa "PIOX" saíram — o
// corpo do prédio deu lugar ao display, e o nome à própria aplicação.
//
// O conjunto apoia direto na borda de cima do bezel (`layout.crownBase`), sem
// faixa creme entre o frontão e a tela.
// ---------------------------------------------------------------------------

import * as THREE from "three";
import { CROWN as C, Z } from "./config.js";
import { box } from "./geo.js";

function pediment(material, baseY) {
  // Prisma triangular via ExtrudeGeometry a partir de um Shape — não depende
  // de fonte nem de asset externo, ao contrário de TextGeometry.
  const halfW = C.pedimentWidth / 2;
  const shape = new THREE.Shape();
  shape.moveTo(-halfW, 0);
  shape.lineTo(halfW, 0);
  shape.lineTo(0, C.pedimentHeight);
  shape.closePath();

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 0.03,
    bevelEnabled: true,
    bevelThickness: 0.004,
    bevelSize: 0.005,
    bevelSegments: 2,
  });
  const mesh = new THREE.Mesh(geo, material);
  mesh.position.set(0, baseY, Z.crownFront - 0.03);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

export function buildCrown({ dark, layout }) {
  const group = new THREE.Group();
  group.name = "coroamento";

  // A cornija ocupa a faixa logo acima do bezel; o frontão começa no topo dela.
  const corniceY = layout.crownBase + C.corniceHeight / 2;
  const pedimentY = layout.crownBase + C.corniceHeight;

  // ---- frontão e cornija ----
  group.add(pediment(dark, pedimentY));
  group.add(box(dark, C.pedimentWidth, C.corniceHeight, 0.04, 0, corniceY, Z.crown));

  // ---- cruz no ápice ----
  const crossY = pedimentY + C.pedimentHeight;
  const arm = 0.013;
  group.add(box(dark, arm, C.crossHeight, 0.026, 0, crossY + C.crossHeight / 2, Z.crown));
  group.add(box(dark, C.crossHeight * 0.55, arm, 0.026, 0, crossY + C.crossHeight * 0.68, Z.crown));

  return group;
}
