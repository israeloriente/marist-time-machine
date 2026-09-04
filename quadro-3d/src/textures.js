// ---------------------------------------------------------------------------
// textures.js — tudo desenhado em <canvas> na hora, nada de asset externo.
//
// Sobrou o que a versão com display ainda usa: o papel envelhecido da faixa do
// coroamento, a placa gravada do rodapé, o ambiente da sala e os reflexos do
// vidro. As texturas do quadro impresso (fotos de turma, retrato, listas de
// nomes, janelinhas, letreiros em relevo) saíram junto com ele.
// ---------------------------------------------------------------------------

import * as THREE from "three";

let MAX_ANISO = 8;
export function setAnisotropy(n) {
  MAX_ANISO = n;
}

// PRNG determinístico: o quadro tem que sair igual em toda execução.
export function rng(seed) {
  let s = (seed >>> 0) || 1;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function makeCanvas(w, h) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  return { canvas, ctx: canvas.getContext("2d", { willReadFrequently: true }) };
}

function toTexture(canvas, { srgb = true, repeat = null } = {}) {
  const tex = new THREE.CanvasTexture(canvas);
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = MAX_ANISO;
  tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
  if (repeat) {
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(repeat[0], repeat[1]);
  }
  tex.needsUpdate = true;
  return tex;
}

// Ruído fino aplicado por pixel — dá "grão" e tira o aspecto de vetor liso.
function grain(ctx, w, h, amount, rand) {
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const n = (rand() - 0.5) * amount;
    d[i] = clamp8(d[i] + n);
    d[i + 1] = clamp8(d[i + 1] + n);
    d[i + 2] = clamp8(d[i + 2] + n);
  }
  ctx.putImageData(img, 0, 0);
}

const clamp8 = (v) => (v < 0 ? 0 : v > 255 ? 255 : v);

function vignette(ctx, w, h, strength = 0.35) {
  const g = ctx.createRadialGradient(
    w / 2, h / 2, Math.min(w, h) * 0.2,
    w / 2, h / 2, Math.max(w, h) * 0.72,
  );
  g.addColorStop(0, "rgba(0,0,0,0)");
  g.addColorStop(1, `rgba(20,14,6,${strength})`);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
}

// ---------------------------------------------------------------------------
// Fundo de papel envelhecido — o creme manchado atrás de tudo.
// ---------------------------------------------------------------------------
export function agedPaper({ w = 2048, h = 1024, seed = 7, base = "#e6dcc4" } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, w, h);
  const rand = rng(seed);

  // Manchas grandes e difusas (umidade, tempo, cola do laminado).
  for (let i = 0; i < 90; i++) {
    const x = rand() * w;
    const y = rand() * h;
    const r = (0.03 + rand() * 0.16) * w;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    const tone = ["216,202,168", "203,187,150", "233,226,207", "198,180,142"][
      Math.floor(rand() * 4)
    ];
    g.addColorStop(0, `rgba(${tone},${0.1 + rand() * 0.22})`);
    g.addColorStop(1, `rgba(${tone},0)`);
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }

  // Amarelamento mais forte nas bordas, que é onde a luz e o ar pegam.
  vignette(ctx, w, h, 0.22);
  grain(ctx, w, h, 14, rand);
  return toTexture(canvas);
}

// ---------------------------------------------------------------------------
// Ambiente da sala
// ---------------------------------------------------------------------------
export function wallTexture({ w = 1024, h = 1024, seed = 5 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const rand = rng(seed);
  ctx.fillStyle = "#f2f0ec";
  ctx.fillRect(0, 0, w, h);
  for (let i = 0; i < 40; i++) {
    const x = rand() * w;
    const y = rand() * h;
    const r = (0.05 + rand() * 0.2) * w;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(206,203,196,${0.05 + rand() * 0.1})`);
    g.addColorStop(1, "rgba(206,203,196,0)");
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }
  grain(ctx, w, h, 8, rand);
  return toTexture(canvas, { repeat: [3, 2] });
}

export function stoneTexture({ w = 1024, h = 512, seed = 9 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const rand = rng(seed);
  ctx.fillStyle = "#4c4b47";
  ctx.fillRect(0, 0, w, h);

  // Pedra bruta assentada em fiadas irregulares
  const rows = 6;
  const rowH = h / rows;
  for (let r = 0; r < rows; r++) {
    let x = -rand() * 80;
    while (x < w) {
      const bw = 60 + rand() * 130;
      const tone = 84 + Math.floor(rand() * 52);
      ctx.fillStyle = `rgb(${tone},${tone - 2},${tone - 6})`;
      ctx.fillRect(x + 2, r * rowH + 2, bw - 4, rowH - 4);
      // Speckle de granito dentro de cada bloco
      for (let s = 0; s < 90; s++) {
        const sx = x + 2 + rand() * (bw - 4);
        const sy = r * rowH + 2 + rand() * (rowH - 4);
        const v = rand() < 0.5 ? 40 : 170;
        ctx.fillStyle = `rgba(${v},${v},${v},${0.12 + rand() * 0.25})`;
        ctx.fillRect(sx, sy, 2, 2);
      }
      x += bw;
    }
  }
  grain(ctx, w, h, 16, rand);
  return toTexture(canvas, { repeat: [4, 1] });
}

// O cartaz azul/laranja que aparece no canto inferior esquerdo da foto.
export function posterTexture({ w = 512, h = 384 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const g = ctx.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, "#1b57a8");
  g.addColorStop(1, "#0f3d7d");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.font = `italic 600 ${Math.round(h * 0.13)}px Georgia, serif`;
  ctx.fillText("ir além", w * 0.07, h * 0.1);

  ctx.font = `800 ${Math.round(h * 0.2)}px "Arial Black", Arial, sans-serif`;
  ctx.fillText("AGIR", w * 0.07, h * 0.29);
  ctx.fillStyle = "#f5a11e";
  ctx.fillText("COM", w * 0.07, h * 0.53);

  ctx.fillStyle = "rgba(255,255,255,0.85)";
  ctx.fillRect(w * 0.07, h * 0.8, w * 0.5, h * 0.03);
  return toTexture(canvas);
}

// ---------------------------------------------------------------------------
// Reflexos do acrílico: faixas diagonais claras, como as da foto original.
// ---------------------------------------------------------------------------
export function glareTexture({ w = 1024, h = 512, seed = 13 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const rand = rng(seed);
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, w, h);
  ctx.globalCompositeOperation = "lighter";

  const bands = [
    { x: 0.12, wid: 0.1, a: 0.5 },
    { x: 0.3, wid: 0.05, a: 0.28 },
    { x: 0.62, wid: 0.13, a: 0.42 },
    { x: 0.84, wid: 0.07, a: 0.3 },
  ];
  for (const b of bands) {
    ctx.save();
    ctx.translate(b.x * w, 0);
    ctx.rotate(-0.22);
    const g = ctx.createLinearGradient(-b.wid * w, 0, b.wid * w, 0);
    g.addColorStop(0, "rgba(255,252,240,0)");
    g.addColorStop(0.5, `rgba(255,252,240,${b.a})`);
    g.addColorStop(1, "rgba(255,252,240,0)");
    ctx.fillStyle = g;
    ctx.fillRect(-b.wid * w, -h * 0.4, b.wid * 2 * w, h * 1.8);
    ctx.restore();
  }
  ctx.globalCompositeOperation = "source-over";
  grain(ctx, w, h, 6, rand);
  return toTexture(canvas, { srgb: false });
}

// Mapa de ambiente equirretangular gerado na hora: evita depender de HDR
// externo e dá reflexos previsíveis (luminárias no teto + janela lateral).
export function environmentEquirect({ w = 1024, h = 512 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, "#e8eaee"); // teto
  g.addColorStop(0.45, "#b9bcc2");
  g.addColorStop(0.55, "#8f9298");
  g.addColorStop(1, "#3a3b3e"); // piso
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  // Luminárias de teto
  ctx.fillStyle = "#ffffff";
  for (let i = 0; i < 4; i++) {
    ctx.globalAlpha = 0.9;
    ctx.fillRect(w * (0.1 + i * 0.24), h * 0.06, w * 0.09, h * 0.05);
  }
  // Janela grande à esquerda (a luz-chave da foto vem daí)
  ctx.globalAlpha = 1;
  const wg = ctx.createLinearGradient(0, h * 0.28, 0, h * 0.62);
  wg.addColorStop(0, "#ffffff");
  wg.addColorStop(1, "#cfd6e0");
  ctx.fillStyle = wg;
  ctx.fillRect(w * 0.02, h * 0.28, w * 0.16, h * 0.34);
  return toTexture(canvas, { srgb: false });
}

// ---------------------------------------------------------------------------
// Placa metálica gravada — usada no rodapé da moldura na versão de display
// único, onde a letra aplicada do cabeçalho deu lugar à tela.
// ---------------------------------------------------------------------------
export function engravedPlate({ lines = [], w = 1024, h = 128, seed = 21 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const rand = rng(seed);

  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, "#6f7378");
  g.addColorStop(0.45, "#4b4e53");
  g.addColorStop(0.55, "#5a5e63");
  g.addColorStop(1, "#3c3f44");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  // Escovado horizontal
  ctx.globalAlpha = 0.06;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 1;
  for (let y = 0; y < h; y += 2) {
    if (rand() < 0.35) continue;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const step = h / (lines.length + 1);
  lines.forEach((text, i) => {
    const y = step * (i + 1);
    const size = i === 0 ? h * 0.26 : h * 0.17;
    ctx.font = `${i === 0 ? 700 : 500} ${Math.round(size)}px "Helvetica Neue", Arial, sans-serif`;
    // Gravação: sombra escura embaixo, realce claro em cima. É o que faz o
    // texto parecer cavado no metal em vez de impresso nele.
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillText(text, w / 2, y + h * 0.012);
    ctx.fillStyle = "rgba(255,255,255,0.22)";
    ctx.fillText(text, w / 2, y - h * 0.012);
    ctx.fillStyle = "#22252a";
    ctx.fillText(text, w / 2, y);
  });

  grain(ctx, w, h, 8, rand);
  return toTexture(canvas);
}
