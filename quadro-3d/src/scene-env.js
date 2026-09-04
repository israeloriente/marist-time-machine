// ---------------------------------------------------------------------------
// scene-env.js — a sala em volta do quadro: parede branca, rodapé de pedra,
// piso, o cartaz azul do canto e a iluminação.
//
// A luz-chave vem de cima e da esquerda porque é de lá que ela vem na foto
// original (as sombras da moldura caem pra direita e pra baixo).
// ---------------------------------------------------------------------------

import * as THREE from "three";
import { PALETTE, ROOM } from "./config.js";
import * as T from "./textures.js";

export function buildRoom() {
  const group = new THREE.Group();
  group.name = "sala";

  // ---- parede ----
  const wall = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.wallWidth, ROOM.wallHeight),
    new THREE.MeshStandardMaterial({
      map: T.wallTexture(),
      color: PALETTE.wall,
      roughness: 0.94,
      metalness: 0,
    }),
  );
  wall.position.set(0, ROOM.wainscotTop + ROOM.wallHeight / 2, ROOM.wallZ);
  wall.receiveShadow = true;
  group.add(wall);

  // ---- rodapé de pedra ----
  const stoneH = ROOM.wainscotTop - ROOM.floorY;
  const stone = new THREE.Mesh(
    new THREE.BoxGeometry(ROOM.wallWidth, stoneH, 0.05),
    new THREE.MeshStandardMaterial({
      map: T.stoneTexture(),
      color: PALETTE.stone,
      roughness: 0.98,
      metalness: 0,
    }),
  );
  stone.position.set(0, ROOM.floorY + stoneH / 2, ROOM.wallZ + 0.025);
  stone.receiveShadow = true;
  stone.castShadow = true;
  group.add(stone);

  // ---- piso ----
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.wallWidth, 10),
    new THREE.MeshStandardMaterial({ color: 0x3f3d3a, roughness: 0.7, metalness: 0.05 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, ROOM.floorY, ROOM.wallZ + 5);
  floor.receiveShadow = true;
  group.add(floor);

  // ---- cartaz colado na pedra ----
  const poster = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.posterW, ROOM.posterH),
    new THREE.MeshStandardMaterial({ map: T.posterTexture(), roughness: 0.8 }),
  );
  poster.position.set(
    ROOM.posterX,
    ROOM.posterTop - ROOM.posterH / 2,
    ROOM.wallZ + 0.052,
  );
  poster.rotation.z = -0.012; // colado torto, como na foto
  poster.receiveShadow = true;
  group.add(poster);

  return group;
}

export function buildLights() {
  const group = new THREE.Group();
  group.name = "luzes";

  const key = new THREE.DirectionalLight(0xfff4e2, 1.75);
  key.position.set(-3.2, 3.6, 4.2);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.near = 0.5;
  key.shadow.camera.far = 16;
  const s = 3.4;
  key.shadow.camera.left = -s;
  key.shadow.camera.right = s;
  key.shadow.camera.top = s * 0.6;
  key.shadow.camera.bottom = -s * 0.6;
  key.shadow.bias = -0.0009;
  key.shadow.normalBias = 0.014;
  group.add(key);

  // Preenchimento frio pela direita, pra sombra não fechar em preto.
  const fill = new THREE.DirectionalLight(0xd6e2f0, 0.6);
  fill.position.set(4.5, 1.2, 3.0);
  group.add(fill);

  // Rasante de baixo: devolve um pouco de luz refletida pelo piso.
  const bounce = new THREE.DirectionalLight(0xffe9cc, 0.28);
  bounce.position.set(0, -3, 2.2);
  group.add(bounce);

  const hemi = new THREE.HemisphereLight(0xf2f4f8, 0x30302e, 0.5);
  group.add(hemi);

  return { group, key, fill, bounce, hemi };
}
