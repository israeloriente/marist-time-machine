// ---------------------------------------------------------------------------
// textures.js — tudo desenhado em <canvas> na hora, nada de asset externo.
//
// O envelhecimento é o ponto: na foto original as duas fotos das pontas viraram
// magenta e as quatro do centro viraram ciano. Isso é colapso de corante de
// impressão fotográfica, e acontece por lote — por isso o desvio é diferente
// entre painéis do mesmo quadro. `applyAging()` reproduz isso convertendo a
// imagem pra luminância e re-tingindo com a cor do desvio.
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
// Fotos de turma envelhecidas
// ---------------------------------------------------------------------------

const CASTS = {
  // Luminância -> cor. Ciano puxa verde/azul; mauve puxa vermelho/azul.
  cyan: [0.46, 0.86, 0.92],
  mauve: [0.82, 0.59, 0.79],
  sepia: [0.86, 0.74, 0.55],
};

function applyAging(ctx, w, h, { cast = "cyan", fade = 0.2, contrast = 0.9 }) {
  const c = CASTS[cast] ?? CASTS.cyan;
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const l =
      (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) / 255;
    // Contraste achatado: papel velho perde preto e perde branco.
    const lc = 0.5 + (l - 0.5) * contrast;
    let r = lc * c[0];
    let g = lc * c[1];
    let b = lc * c[2];
    // Lavagem em direção ao branco do papel.
    r += (1 - r) * fade;
    g += (1 - g) * fade;
    b += (1 - b) * fade;
    d[i] = r * 255;
    d[i + 1] = g * 255;
    d[i + 2] = b * 255;
  }
  ctx.putImageData(img, 0, 0);
}

function drawPerson(ctx, x, y, r, rand) {
  const skin = ["#c9a689", "#b98f6f", "#8d6a4f", "#d8b795", "#a57a58"][
    Math.floor(rand() * 5)
  ];
  const hair = ["#2c2318", "#3f3226", "#161311", "#54402c", "#6b5334"][
    Math.floor(rand() * 5)
  ];
  // Uniforme: camisa clara na maioria, alguns de blazer escuro.
  const shirt = rand() < 0.72 ? "#e8e5dd" : "#39404f";

  // Tronco
  ctx.fillStyle = shirt;
  ctx.beginPath();
  ctx.moveTo(x - r * 1.9, y + r * 3.4);
  ctx.quadraticCurveTo(x - r * 1.72, y + r * 0.95, x, y + r * 0.78);
  ctx.quadraticCurveTo(x + r * 1.72, y + r * 0.95, x + r * 1.9, y + r * 3.4);
  ctx.closePath();
  ctx.fill();

  // Pescoço + cabeça
  ctx.fillStyle = skin;
  ctx.fillRect(x - r * 0.33, y + r * 0.3, r * 0.66, r * 0.72);
  ctx.beginPath();
  ctx.ellipse(x, y, r * 0.8, r, 0, 0, Math.PI * 2);
  ctx.fill();

  // Cabelo: calota por cima
  ctx.fillStyle = hair;
  ctx.beginPath();
  ctx.ellipse(x, y - r * 0.16, r * 0.85, r * 0.82, 0, Math.PI, Math.PI * 2);
  ctx.fill();
  if (rand() < 0.45) {
    // Cabelo mais comprido, descendo pelos lados
    ctx.beginPath();
    ctx.ellipse(x, y + r * 0.12, r * 0.9, r * 0.95, 0, 0.15, Math.PI - 0.15);
    ctx.fill();
    ctx.fillStyle = skin;
    ctx.beginPath();
    ctx.ellipse(x, y + r * 0.05, r * 0.6, r * 0.78, 0, 0, Math.PI * 2);
    ctx.fill();
  }
}

export function classPhoto({
  w = 768,
  h = 512,
  rows = 3,
  perRow = 12,
  cast = "cyan",
  seed = 1,
} = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const rand = rng(seed);

  // Fundo: parede do pátio + chão
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, "#9d978d");
  g.addColorStop(0.6, "#b5afa4");
  g.addColorStop(1, "#7c776e");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  // Insinuação de arquitetura atrás (colunas do pátio)
  ctx.globalAlpha = 0.16;
  ctx.fillStyle = "#565249";
  for (let i = 0; i < 6; i++) {
    const x = ((i + 0.5) * w) / 6;
    ctx.fillRect(x - w * 0.013, h * 0.04, w * 0.026, h * 0.52);
  }
  ctx.globalAlpha = 1;

  // Fileiras: de trás pra frente, cada uma um pouco maior e mais baixa.
  for (let r = 0; r < rows; r++) {
    const t = rows > 1 ? r / (rows - 1) : 0;
    const scale = 0.8 + t * 0.34;
    const headR = h * 0.055 * scale;
    const baseY = h * (0.4 + t * 0.29);
    const count = Math.max(5, Math.round(perRow - t * 2));
    const step = w / (count + 0.5);
    for (let i = 0; i < count; i++) {
      const x = step * (i + 0.7) + (rand() - 0.5) * step * 0.2;
      drawPerson(ctx, x, baseY + (rand() - 0.5) * headR * 0.3, headR, rand);
    }
  }

  applyAging(ctx, w, h, { cast, fade: cast === "mauve" ? 0.24 : 0.19, contrast: 0.95 });
  vignette(ctx, w, h, 0.3);

  // Riscos e poeira na superfície do papel
  ctx.strokeStyle = "rgba(255,255,255,0.14)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 14; i++) {
    ctx.beginPath();
    const x = rand() * w;
    const y = rand() * h;
    ctx.moveTo(x, y);
    ctx.lineTo(x + (rand() - 0.5) * 90, y + (rand() - 0.5) * 30);
    ctx.stroke();
  }
  grain(ctx, w, h, 18, rand);

  return toTexture(canvas);
}

// Retrato único (o religioso na primeira baia da esquerda).
export function portrait({ w = 420, h = 560, cast = "mauve", seed = 42 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const rand = rng(seed);

  const g = ctx.createRadialGradient(w * 0.5, h * 0.35, 0, w * 0.5, h * 0.5, h * 0.8);
  g.addColorStop(0, "#a49c8e");
  g.addColorStop(1, "#5d574d");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  const cx = w * 0.5;
  const headR = h * 0.14;
  const headY = h * 0.34;

  // Batina escura
  ctx.fillStyle = "#2b2820";
  ctx.beginPath();
  ctx.moveTo(cx - w * 0.46, h);
  ctx.quadraticCurveTo(cx - w * 0.34, headY + headR * 1.6, cx, headY + headR * 1.25);
  ctx.quadraticCurveTo(cx + w * 0.34, headY + headR * 1.6, cx + w * 0.46, h);
  ctx.closePath();
  ctx.fill();

  // Rabat / colarinho branco
  ctx.fillStyle = "#ddd8cc";
  ctx.beginPath();
  ctx.moveTo(cx - headR * 0.5, headY + headR * 1.15);
  ctx.lineTo(cx + headR * 0.5, headY + headR * 1.15);
  ctx.lineTo(cx + headR * 0.32, headY + headR * 1.75);
  ctx.lineTo(cx - headR * 0.32, headY + headR * 1.75);
  ctx.closePath();
  ctx.fill();

  // Rosto
  ctx.fillStyle = "#c2a184";
  ctx.fillRect(cx - headR * 0.28, headY + headR * 0.6, headR * 0.56, headR * 0.7);
  ctx.beginPath();
  ctx.ellipse(cx, headY, headR * 0.78, headR, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#2f2820";
  ctx.beginPath();
  ctx.ellipse(cx, headY - headR * 0.2, headR * 0.82, headR * 0.72, 0, Math.PI, Math.PI * 2);
  ctx.fill();

  applyAging(ctx, w, h, { cast, fade: 0.22, contrast: 0.86 });
  vignette(ctx, w, h, 0.42);
  grain(ctx, w, h, 16, rand);
  return toTexture(canvas);
}

// ---------------------------------------------------------------------------
// Rótulo + lista de nomes
//
// Os rótulos ("BIO EXATAS I") saem como texto de verdade porque são legíveis
// na foto. Os nomes viram linhas tipográficas: na escala real cada nome tem
// ~2 mm de altura e é exatamente isso que o olho enxerga. Inventar nomes num
// memorial de gente real seria pior que representá-lo honestamente.
// ---------------------------------------------------------------------------
export function nameBlock({
  w = 512,
  h = 384,
  title = "TURMA",
  columns = 3,
  seed = 3,
} = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const rand = rng(seed);
  ctx.clearRect(0, 0, w, h);

  // Rótulo
  const titleSize = Math.round(h * 0.075);
  ctx.fillStyle = "#2a2620";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.font = `700 ${titleSize}px "Helvetica Neue", Arial, sans-serif`;
  ctx.save();
  ctx.translate(w / 2, h * 0.02);
  ctx.scale(0.92, 1); // levemente condensado, como na placa
  ctx.fillText(title, 0, 0);
  ctx.restore();

  // Filete sob o rótulo
  ctx.fillStyle = "rgba(42,38,32,0.45)";
  ctx.fillRect(w * 0.16, h * 0.125, w * 0.68, Math.max(1, h * 0.004));

  // Colunas de nomes
  const top = h * 0.17;
  const bottom = h * 0.97;
  const gutter = w * 0.03;
  const colW = (w - gutter * (columns + 1)) / columns;
  const lineH = Math.max(3, h * 0.036);
  const lines = Math.floor((bottom - top) / lineH);

  ctx.fillStyle = "rgba(40,35,28,0.72)";
  for (let c = 0; c < columns; c++) {
    const x0 = gutter + c * (colW + gutter);
    for (let i = 0; i < lines; i++) {
      const y = top + i * lineH;
      // Largura variável: nomes têm tamanhos diferentes.
      const len = colW * (0.52 + rand() * 0.46);
      ctx.globalAlpha = 0.55 + rand() * 0.35;
      ctx.fillRect(x0, y, len, Math.max(1.2, lineH * 0.33));
    }
  }
  ctx.globalAlpha = 1;
  return toTexture(canvas);
}

// ---------------------------------------------------------------------------
// Letras aplicadas em relevo (cabeçalho).
// Retorna { map, bump }: o bump faz a luz reagir ao relevo sem precisar
// extrudar geometria por glifo (que exigiria carregar uma fonte .json).
// ---------------------------------------------------------------------------
export function reliefText(items, { w = 2048, h = 512, color = "#1e3a63" } = {}) {
  const draw = (ctx, fill, shadow) => {
    for (const it of items) {
      ctx.save();
      ctx.translate(it.x * w, it.y * h);
      ctx.scale(it.condense ?? 0.86, 1);
      ctx.font = `${it.weight ?? 900} ${Math.round(it.size * h)}px "Arial Black", "Helvetica Neue", Impact, sans-serif`;
      ctx.textAlign = it.align ?? "left";
      ctx.textBaseline = "top";
      if (shadow) {
        ctx.fillStyle = shadow;
        ctx.fillText(it.text, h * 0.012, h * 0.014);
      }
      ctx.fillStyle = fill;
      ctx.fillText(it.text, 0, 0);
      ctx.restore();
    }
  };

  const a = makeCanvas(w, h);
  a.ctx.clearRect(0, 0, w, h);
  draw(a.ctx, color, "rgba(60,50,35,0.4)");

  const b = makeCanvas(w, h);
  b.ctx.fillStyle = "#000";
  b.ctx.fillRect(0, 0, w, h);
  draw(b.ctx, "#ffffff", null);

  const map = toTexture(a.canvas);
  const bump = toTexture(b.canvas, { srgb: false });
  return { map, bump };
}

// ---------------------------------------------------------------------------
// Placa metálica escura da turma (canto superior direito).
// ---------------------------------------------------------------------------
export function turmaPlaque({ w = 1024, h = 256, seed = 11 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  const rand = rng(seed);
  const barH = h * 0.35;

  // Tarja escura com escovado horizontal
  const g = ctx.createLinearGradient(0, 0, 0, barH);
  g.addColorStop(0, "#3a3d43");
  g.addColorStop(0.5, "#22252a");
  g.addColorStop(1, "#34373d");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, barH);
  ctx.globalAlpha = 0.08;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 1;
  for (let y = 0; y < barH; y += 2) {
    if (rand() < 0.4) continue;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  ctx.fillStyle = "#dfe2e6";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = `600 ${Math.round(h * 0.18)}px "Helvetica Neue", Arial, sans-serif`;
  ctx.save();
  ctx.translate(w / 2, barH * 0.52);
  ctx.scale(0.9, 1);
  ctx.fillText("TURMA - SÃO MARCELINO CHAMPAGNAT", 0, 0);
  ctx.restore();

  // Bloco de homenagens: rótulos legíveis, nomes como filete.
  ctx.fillStyle = "rgba(214,206,186,0.55)";
  ctx.fillRect(0, barH, w, h - barH);

  const roles = [
    ["PATRONO", "PARANINFO", "HOMENAGEADOS"],
    ["MADRINHA", "PADRINHO", "ORADOR"],
  ];
  const colW = w / 3;
  const rowH = (h - barH) / 2;
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  for (let r = 0; r < roles.length; r++) {
    for (let c = 0; c < roles[r].length; c++) {
      const x = c * colW + w * 0.02;
      const y = barH + r * rowH + rowH * 0.14;
      ctx.fillStyle = "#2b2822";
      ctx.font = `700 ${Math.round(h * 0.085)}px "Helvetica Neue", Arial, sans-serif`;
      ctx.fillText(roles[r][c], x, y);
      ctx.fillStyle = "rgba(43,40,34,0.6)";
      ctx.fillRect(x, y + h * 0.115, colW * (0.5 + rand() * 0.34), Math.max(1.5, h * 0.02));
    }
  }

  grain(ctx, w, h, 10, rand);
  return toTexture(canvas);
}

// ---------------------------------------------------------------------------
// Janelinhas aplicadas: caixilho claro com bandeira e caixilho em cruz.
// ---------------------------------------------------------------------------
export function windowPane({ w = 128, h = 192 } = {}) {
  const { canvas, ctx } = makeCanvas(w, h);
  ctx.fillStyle = "#cfc7b2";
  ctx.fillRect(0, 0, w, h);
  const inset = w * 0.11;
  ctx.fillStyle = "#7f8a90";
  ctx.fillRect(inset, inset, w - inset * 2, h - inset * 2);
  // Caixilhos
  ctx.fillStyle = "#cfc7b2";
  const bar = w * 0.055;
  ctx.fillRect(w / 2 - bar / 2, inset, bar, h - inset * 2);
  for (const f of [0.34, 0.67]) {
    ctx.fillRect(inset, inset + (h - inset * 2) * f - bar / 2, w - inset * 2, bar);
  }
  // Reflexo diagonal no vidro
  ctx.globalAlpha = 0.22;
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.moveTo(inset, h * 0.62);
  ctx.lineTo(w * 0.62, inset);
  ctx.lineTo(w - inset, inset);
  ctx.lineTo(inset, h * 0.86);
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;
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
