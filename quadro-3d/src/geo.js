// ---------------------------------------------------------------------------
// geo.js — helpers de geometria compartilhados.
//
// Uma única BoxGeometry/PlaneGeometry reaproveitada e escalada por instância,
// em vez de criar geometria nova pra cada elemento. O quadro tem ~200 peças;
// isso mantém a contagem de buffers baixa.
// ---------------------------------------------------------------------------

import * as THREE from "three";

export const UNIT_BOX = new THREE.BoxGeometry(1, 1, 1);
export const UNIT_PLANE = new THREE.PlaneGeometry(1, 1);

/** Caixa apoiada em `z` (a face de trás encosta em z, não o centro). */
export function box(material, w, h, d, x, y, z) {
  const m = new THREE.Mesh(UNIT_BOX, material);
  m.scale.set(w, h, d);
  m.position.set(x, y, z + d / 2);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

export function plane(material, w, h, x, y, z) {
  const m = new THREE.Mesh(UNIT_PLANE, material);
  m.scale.set(w, h, 1);
  m.position.set(x, y, z);
  m.receiveShadow = true;
  return m;
}

/**
 * Moldura oca: quatro barras em volta de um vazio.
 * Diferente de um `box`, deixa ver o que está atrás — é o que dá a sensação
 * de vão numa porta rebaixada ou de moldura num display.
 */
export function hollowFrame(material, w, h, bar, d, x, y, z) {
  const g = new THREE.Group();
  g.add(box(material, w, bar, d, x, y + h / 2 - bar / 2, z));
  g.add(box(material, w, bar, d, x, y - h / 2 + bar / 2, z));
  g.add(box(material, bar, h - bar * 2, d, x - w / 2 + bar / 2, y, z));
  g.add(box(material, bar, h - bar * 2, d, x + w / 2 - bar / 2, y, z));
  return g;
}
