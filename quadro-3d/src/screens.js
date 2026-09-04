// ---------------------------------------------------------------------------
// screens.js — o display.
//
// createLiveScreen monta uma página web de verdade, viva e clicável, dentro da
// cena 3D. Feito com CSS3DRenderer: o elemento DOM (<webview> no Electron,
// <iframe> como reserva) é posicionado no espaço 3D por matrix3d, e um plano
// "punch-through" em WebGL abre o buraco no canvas pra ele aparecer. É a única
// forma de ter a página viva E interativa — textura capturada seria estática.
//
// O resto do arquivo é o "hardware" em volta: moldura, chassi e vidro.
// ---------------------------------------------------------------------------

import * as THREE from "three";
import { CSS3DObject } from "three/examples/jsm/renderers/CSS3DRenderer.js";
import { box, hollowFrame, plane, UNIT_PLANE } from "./geo.js";
import { PALETTE } from "./config.js";

// Pixels de DOM por metro de mundo. Mais alto = página mais nítida e mais cara
// de compor. 420 dá ~1700 px de largura num display de 4 m.
const PX_PER_METER = 420;

// ---------------------------------------------------------------------------
// Hardware do display
// ---------------------------------------------------------------------------
export function displayHardware({ w, h, bezel = 0.03, depth = 0.05, z, x = 0, y = 0, materials }) {
  const g = new THREE.Group();
  g.name = "display";
  // Chassi atrás (o display é encaixado no vão) + moldura em volta da tela.
  g.add(box(materials.chassis, w + bezel * 0.5, h + bezel * 0.5, depth, x, y, z - depth));
  g.add(hollowFrame(materials.bezel, w + bezel * 2, h + bezel * 2, bezel, depth * 0.42, x, y, z));
  return g;
}

/** Vidro fino sobre a tela: reflexo, sem transmissão (mesma razão do acrílico). */
export function screenGlass({ w, h, x = 0, y = 0, z, envMap }) {
  const mat = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.055,
    roughness: 0.05,
    metalness: 0,
    clearcoat: 1,
    clearcoatRoughness: 0.02,
    envMap,
    envMapIntensity: 1.1,
    depthWrite: false,
  });
  const m = plane(mat, w, h, x, y, z);
  m.name = "vidro-display";
  m.renderOrder = 6;
  return m;
}

// ---------------------------------------------------------------------------
// Tela viva (CSS3D)
// ---------------------------------------------------------------------------

/**
 * `webviewTag` é ligado no processo principal, mas quem sabe se pegou é o
 * renderer: se o custom element foi registrado, o elemento ganha `loadURL` ao
 * entrar no DOM. Checar assim evita depender de uma constante em preload que
 * pode divergir do main.
 */
function webviewSupported() {
  try {
    const el = document.createElement("webview");
    document.body.appendChild(el);
    const ok = typeof el.loadURL === "function" || typeof el.getWebContentsId === "function";
    el.remove();
    return ok;
  } catch {
    return false;
  }
}

let WEBVIEW_OK = null;

export function createLiveScreen({ w, h, x = 0, y = 0, z, url, fallbackUrl }) {
  if (WEBVIEW_OK === null) WEBVIEW_OK = webviewSupported();

  const pxW = Math.round(w * PX_PER_METER);
  const pxH = Math.round(h * PX_PER_METER);

  const host = document.createElement("div");
  host.className = "live-screen";
  host.style.width = `${pxW}px`;
  host.style.height = `${pxH}px`;

  let frame;
  let usedFallback = false;
  const toFallback = () => {
    if (usedFallback || !fallbackUrl) return;
    usedFallback = true;
    frame.setAttribute("src", fallbackUrl);
  };

  if (WEBVIEW_OK) {
    frame = document.createElement("webview");
    frame.setAttribute("src", url);
    // Sem popups e sem preload: o guest é conteúdo externo, tratado como tal.
    frame.setAttribute("allowpopups", "false");
    frame.addEventListener("did-fail-load", (e) => {
      // -3 é ABORTED (navegação cancelada); não vale trocar pela reserva.
      if (e.errorCode !== -3) toFallback();
    });
  } else {
    frame = document.createElement("iframe");
    frame.setAttribute("src", url);
    frame.setAttribute("referrerpolicy", "no-referrer");
    // Um <iframe> não avisa quando o alvo recusa ser embutido (X-Frame-Options
    // falha em silêncio). Se nada carregar no prazo, cai pra reserva local.
    let loaded = false;
    frame.addEventListener("load", () => (loaded = true));
    setTimeout(() => {
      if (!loaded) toFallback();
    }, 6000);
  }
  // Dimensão em pixel explícita, NÃO porcentagem. Um <webview> do Electron não
  // resolve `height: 100%` — o guest cai no default de 150 px de altura e a
  // página é renderizada num viewport errado, ficando cortada. Como o tamanho
  // já é calculado aqui, aplicá-lo direto elimina a dependência de herança.
  frame.style.width = `${pxW}px`;
  frame.style.height = `${pxH}px`;
  host.appendChild(frame);

  const object = new CSS3DObject(host);
  object.scale.setScalar(1 / PX_PER_METER);
  object.position.set(x, y, z);

  // O buraco: com NoBlending o shader escreve alpha 0 direto no canvas em vez
  // de misturar. Onde este plano estiver, o WebGL fica transparente e a camada
  // CSS3D atrás aparece.
  const punch = new THREE.Mesh(
    UNIT_PLANE,
    new THREE.MeshBasicMaterial({ color: 0x000000, opacity: 0, blending: THREE.NoBlending }),
  );
  punch.scale.set(w, h, 1);
  punch.position.set(x, y, z);
  punch.renderOrder = 1; // antes do acrílico, que compõe por cima

  function reload() {
    usedFallback = false;
    if (typeof frame.reload === "function") frame.reload();
    else frame.setAttribute("src", url);
  }

  function setUrl(next) {
    usedFallback = false;
    frame.setAttribute("src", next);
  }

  return { kind: "live", object, host, frame, punch, reload, setUrl, engine: WEBVIEW_OK ? "webview" : "iframe" };
}

export function screenMaterials() {
  return {
    bezel: new THREE.MeshStandardMaterial({ color: 0x1a1c20, roughness: 0.34, metalness: 0.65 }),
    chassis: new THREE.MeshStandardMaterial({ color: PALETTE.frame, roughness: 0.7, metalness: 0.1 }),
  };
}
