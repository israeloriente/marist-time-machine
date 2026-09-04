// ---------------------------------------------------------------------------
// facade.js — a maquete do prédio do colégio, no centro do quadro.
//
// Lendo a foto de fora pra dentro: cruz, frontão triangular sobre uma cornija,
// placa "PIOX", arquitrave, duas colunas ladeando a porta com janelas nas
// laterais, e embaixo um pórtico com laje, pernas e uma placa de nomes.
// ---------------------------------------------------------------------------

import * as THREE from "three";
import { FACADE as F, Z } from "./config.js";
import { box as slab, hollowFrame } from "./geo.js";

function pediment(material) {
  // Prisma triangular via ExtrudeGeometry a partir de um Shape — não depende
  // de fonte nem de asset externo, ao contrário de TextGeometry.
  const halfW = F.pedimentWidth / 2;
  const shape = new THREE.Shape();
  shape.moveTo(-halfW, 0);
  shape.lineTo(halfW, 0);
  shape.lineTo(0, F.pedimentHeight);
  shape.closePath();

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 0.03,
    bevelEnabled: true,
    bevelThickness: 0.004,
    bevelSize: 0.005,
    bevelSegments: 2,
  });
  const mesh = new THREE.Mesh(geo, material);
  mesh.position.set(0, F.pedimentY, Z.facadeFront - 0.03);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function column(material, x) {
  const g = new THREE.Group();
  const h = F.columnTop - F.columnBottom;
  const yMid = (F.columnTop + F.columnBottom) / 2;

  // Fuste com leve êntase, projetado à frente do corpo.
  const shaft = new THREE.Mesh(
    new THREE.CylinderGeometry(F.columnRadius * 0.87, F.columnRadius, h, 20, 1),
    material,
  );
  shaft.position.set(x, yMid, Z.facadeFront - F.columnRadius);
  shaft.castShadow = true;
  shaft.receiveShadow = true;
  g.add(shaft);

  const capW = F.columnRadius * 2.6;
  g.add(slab(material, capW, 0.03, 0.05, x, F.columnTop + 0.015, Z.facade));
  g.add(slab(material, capW, 0.034, 0.05, x, F.columnBottom - 0.017, Z.facade));
  return g;
}

export function buildFacade({ dark, paper, signMap, windowMat, plaqueMap }) {
  const group = new THREE.Group();
  group.name = "fachada";

  // Exatamente o mesmo material do painel. Qualquer tinta (pra mais ou pra
  // menos) recorta um retângulo visível no fundo creme.
  const bodyMat = paper;

  // ---- corpo do prédio ----
  // Chapa bem rasa (6 mm) e no mesmo tom do painel. Com mais profundidade ou
  // um creme mais claro ela recorta um retângulo visível no fundo e o frontão
  // passa a parecer o telhado de um quiosque solto, em vez de um elemento
  // aplicado sobre a mesma parede das alas.
  group.add(
    slab(bodyMat, F.bodyWidth, F.bodyTop - F.bodyBottom, 0.005, 0, (F.bodyTop + F.bodyBottom) / 2, Z.facade),
  );

  // ---- frontão, cornija e cruz ----
  group.add(pediment(dark));
  group.add(
    slab(dark, F.pedimentWidth, F.corniceHeight, 0.04, 0, F.pedimentY - F.corniceHeight / 2, Z.facade),
  );

  const crossY = F.pedimentY + F.pedimentHeight;
  const arm = 0.013;
  group.add(slab(dark, arm, F.crossHeight, 0.026, 0, crossY + F.crossHeight / 2, Z.facade));
  group.add(slab(dark, F.crossHeight * 0.55, arm, 0.026, 0, crossY + F.crossHeight * 0.68, Z.facade));

  // ---- placa "PIOX" ----
  // Fundo claro com moldura escura e letras escuras, como no original.
  group.add(slab(dark, F.signWidth + 0.026, F.signHeight + 0.026, 0.016, 0, F.signY, Z.facade));
  group.add(slab(paper, F.signWidth, F.signHeight, 0.008, 0, F.signY, Z.facade + 0.016));
  const sign = new THREE.Mesh(
    new THREE.PlaneGeometry(F.signWidth * 0.94, F.signHeight * 0.8),
    new THREE.MeshStandardMaterial({ map: signMap, transparent: true, roughness: 0.5 }),
  );
  sign.position.set(0, F.signY, Z.facade + 0.0245);
  group.add(sign);

  // ---- arquitrave sobre as colunas ----
  group.add(
    slab(dark, F.pedimentWidth + 0.02, 0.032, 0.05, 0, F.architraveY, Z.facade),
  );

  // ---- colunas ----
  group.add(column(dark, -F.columnX));
  group.add(column(dark, F.columnX));

  // ---- janelas do corpo, ladeando a porta ----
  for (const sx of [-1, 1]) {
    for (const wy of F.bodyWindowRows) {
      group.add(
        slab(windowMat, F.bodyWindowW, F.bodyWindowH, 0.01, sx * F.bodyWindowX, wy, Z.facade + 0.01),
      );
    }
  }

  // ---- porta ----
  // Folha clara recuada + batente escuro por cima: a moldura oca é o que dá
  // a sensação de vão. Um `slab` sólido na frente escondia a porta inteira.
  group.add(slab(paper, F.doorWidth, F.doorHeight, 0.008, 0, F.doorY, Z.facade + 0.01));
  group.add(
    hollowFrame(dark, F.doorWidth + 0.042, F.doorHeight + 0.042, 0.024, 0.022, 0, F.doorY, Z.facade + 0.018),
  );

  // ---- pórtico inferior ----
  group.add(slab(dark, F.porticoWidth, F.porticoSlabH, 0.07, 0, F.porticoSlabY, Z.facade));
  const legTop = F.porticoSlabY - F.porticoSlabH / 2;
  const legH = legTop - F.porticoBottom;
  for (const sx of [-1, 1]) {
    group.add(
      slab(dark, F.porticoLegW, legH, 0.055, sx * (F.porticoWidth / 2 - F.porticoLegW / 2), F.porticoBottom + legH / 2, Z.facade),
    );
  }
  group.add(slab(dark, F.porticoWidth + 0.06, 0.042, 0.062, 0, F.porticoBottom + 0.021, Z.facade));

  // ---- placa de nomes dentro do pórtico ----
  group.add(slab(paper, F.plaqueWidth, F.plaqueHeight, 0.008, 0, F.plaqueY, Z.facade + 0.006));
  const plaque = new THREE.Mesh(
    new THREE.PlaneGeometry(F.plaqueWidth * 0.9, F.plaqueHeight * 0.9),
    new THREE.MeshStandardMaterial({ map: plaqueMap, transparent: true, roughness: 0.85 }),
  );
  plaque.position.set(0, F.plaqueY, Z.facade + 0.0155);
  group.add(plaque);

  return group;
}
