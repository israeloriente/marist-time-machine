// ---------------------------------------------------------------------------
// config.js — todas as medidas do quadro num lugar só.
//
// As proporções vieram da foto do quadro na parede: a moldura ocupa uma caixa
// de ~1540x630 px, ou seja 2.44:1. Fixei a largura real em 4.20 m (tamanho
// plausível pra um quadro de formatura de parede) e derivei o resto dessa
// razão. Toda medida abaixo está em METROS.
//
// Sistema de coordenadas: origem no centro do quadro, X pra direita, Y pra
// cima, Z saindo da parede em direção ao observador.
// ---------------------------------------------------------------------------

export const BOARD = {
  width: 4.2,
  height: 1.72,
  depth: 0.11,
  // Largura da face da moldura preta (a borda que aparece em volta de tudo).
  frameFace: 0.055,
};

// Painel interno (o miolo creme), já descontada a moldura.
export const PANEL = {
  width: BOARD.width - BOARD.frameFace * 2, // 4.09
  height: BOARD.height - BOARD.frameFace * 2, // 1.61
};

export const PANEL_HALF_W = PANEL.width / 2; // 2.045
export const PANEL_HALF_H = PANEL.height / 2; // 0.805

// Camadas em Z. O quadro é raso: tudo acontece entre a chapa de fundo e o
// acrílico da frente, num intervalo de ~7 cm.
export const Z = {
  back: 0.0, // fundo da caixa
  panel: 0.03, // face do painel creme (tudo é empilhado a partir daqui)
  pilaster: 0.048, // pilastras pretas que dividem os vãos
  window: 0.042, // janelinhas aplicadas
  photoGlass: 0.062, // chapa de acrílico de cada foto (sobre espaçadores)
  letters: 0.055, // letras em relevo do cabeçalho
  facade: 0.052, // corpo da fachada PIOX
  facadeFront: 0.086, // colunas e frontão (o ponto mais alto do relevo)
  acrylic: 0.1, // vidro/acrílico grande da frente
  frameFront: BOARD.depth, // face da moldura
};

// ---------------------------------------------------------------------------
// Fachada central "PIOX"
// Um templo em baixo-relevo: frontão triangular com cruz, placa PIOX, duas
// colunas ladeando a porta, e embaixo um pórtico com laje e uma placa.
// ---------------------------------------------------------------------------
export const FACADE = {
  halfWidth: 0.46, // até onde a fachada come do painel de cada lado
  // Alturas lidas da foto: ápice do frontão a ~0.62, base a ~0.45, capitéis
  // das colunas a ~0.29. A placa PIOX ocupa a faixa entre os dois.
  pedimentWidth: 0.88,
  pedimentHeight: 0.16,
  pedimentY: 0.4525, // base do frontão
  corniceHeight: 0.026, // banda horizontal sob o frontão
  crossHeight: 0.085,
  bodyWidth: 0.92,
  bodyTop: 0.63,
  bodyBottom: -0.5,
  signWidth: 0.34,
  signHeight: 0.115,
  signY: 0.385, // centro da placa PIOX
  architraveY: 0.302,
  columnRadius: 0.04,
  columnX: 0.35, // ± distância do eixo
  columnTop: 0.288,
  columnBottom: -0.261,
  doorWidth: 0.175,
  doorHeight: 0.385,
  doorY: 0.083, // centro
  // Janelas do corpo central, ladeando a porta (duas fileiras de cada lado).
  bodyWindowX: 0.19,
  bodyWindowRows: [0.255, 0.09],
  bodyWindowW: 0.055,
  bodyWindowH: 0.082,
  porticoWidth: 0.6,
  porticoSlabY: -0.3, // laje horizontal
  porticoSlabH: 0.055,
  porticoLegW: 0.11,
  porticoBottom: -0.645,
  plaqueWidth: 0.30,
  plaqueHeight: 0.215,
  plaqueY: -0.45,
};

// ---------------------------------------------------------------------------
// Vãos (bays) das alas laterais
//
// Na foto a ala esquerda tem um vão estreito (retrato + histórico do colégio)
// e dois largos (BIO EXATAS I e II); a direita espelha isso — dois largos
// (HUMANAS I e II) e um estreito (comissão de formatura). Modelei simétrico:
// o desencontro que aparece na foto é perspectiva, não o objeto.
// ---------------------------------------------------------------------------
export const PILASTER_W = 0.046;

export const BAY_GEOM = {
  top: 0.345, // topo do vão
  bottom: -0.585, // base do vão (onde começa o rodapé preto)
  plinthBottom: -0.675,
  capitalTop: 0.385,
  // Faixa de janelinhas acima e abaixo do bloco foto+nomes
  windowRowTopY: 0.255,
  windowRowBottomY: -0.525,
  windowW: 0.058,
  windowH: 0.085,
  // Chapa da foto
  photoTop: 0.165,
  photoBottom: -0.15,
  // Bloco de rótulo + lista de nomes, impresso direto no fundo creme
  namesTop: -0.185,
  namesBottom: -0.462,
};

export const BAYS = [
  {
    key: "historia",
    side: -1,
    width: 0.38,
    title: "COLÉGIO MARISTA PIO X",
    columns: 1,
    photo: { kind: "portrait", cast: "mauve" },
    windows: 2,
  },
  {
    key: "bio1",
    side: -1,
    width: 0.51,
    title: "BIO EXATAS I",
    columns: 3,
    photo: { kind: "group", cast: "cyan", rows: 3, perRow: 12 },
    windows: 4,
  },
  {
    key: "bio2",
    side: -1,
    width: 0.51,
    title: "BIO EXATAS II",
    columns: 3,
    photo: { kind: "group", cast: "cyan", rows: 3, perRow: 11 },
    windows: 4,
  },
  {
    key: "hum1",
    side: 1,
    width: 0.51,
    title: "HUMANAS I",
    columns: 3,
    photo: { kind: "group", cast: "cyan", rows: 3, perRow: 12 },
    windows: 4,
  },
  {
    key: "hum2",
    side: 1,
    width: 0.51,
    title: "HUMANAS II",
    columns: 3,
    photo: { kind: "group", cast: "cyan", rows: 3, perRow: 11 },
    windows: 4,
  },
  {
    key: "comissao",
    side: 1,
    width: 0.38,
    title: "COMISSÃO DE FORMATURA",
    columns: 1,
    photo: { kind: "group", cast: "mauve", rows: 2, perRow: 7 },
    windows: 2,
  },
];

// ---------------------------------------------------------------------------
// Cabeçalho: "FORMANDOS / MARISTA" em duas linhas + "2003" maior à direita,
// tudo em letra aplicada com relevo. E, no canto superior direito, a placa
// metálica escura da turma.
// ---------------------------------------------------------------------------
export const HEADER = {
  x0: -1.74, // início do bloco de texto
  x1: -0.46, // fim (já incluindo o "2003")
  yTop: 0.68,
  yBottom: 0.4,
};

export const PLAQUE = {
  x0: 0.7,
  x1: 1.75,
  yTop: 0.585,
  yBottom: 0.34,
  barHeight: 0.085, // altura da tarja escura com o nome da turma
};

// ---------------------------------------------------------------------------
// Ambiente: parede branca, rodapé de pedra e o cartaz azul no canto.
// ---------------------------------------------------------------------------
export const ROOM = {
  wallZ: -0.02,
  wallWidth: 16,
  wallHeight: 9,
  floorY: -1.9,
  wainscotTop: -0.915, // topo do rodapé de pedra
  posterX: -1.75,
  posterTop: -1.02,
  posterW: 0.56,
  posterH: 0.42,
};

export const PALETTE = {
  frame: 0x14161a, // preto do enquadramento e das pilastras
  paper: 0xe6dcc4, // fundo creme envelhecido
  letters: 0x1e3a63, // azul-marinho das letras aplicadas
  metal: 0x2a2c30,
  wall: 0xf2f0ec,
  stone: 0x5f5e5a,
  chrome: 0xb9bcc0,
};

// ---------------------------------------------------------------------------
// Versão touchscreen
//
// 'single' — a moldura física é reaproveitada e todo o miolo vira UM display
//            ultrawide (2.6:1) rodando a aplicação web de verdade. A identidade
//            do objeto sobrevive numa placa gravada no rodapé da moldura, que é
//            o que uma instalação real faria.
// ---------------------------------------------------------------------------

export const SINGLE = {
  margin: 0.014, // folga entre a moldura e o bezel do display
  bezel: 0.028,
  depth: 0.055,
  // Placa gravada no rodapé da moldura, no lugar da letra aplicada.
  plateWidth: 1.32,
  plateHeight: 0.04,
};

// URL que a versão 'single' carrega dentro do display.
// Sobrescrevível por QUADRO_SCREEN_URL (ver electron/main.js).
export const SCREEN = {
  defaultUrl: "https://capsula-marista.israeloriente.com/kiosk",
  devUrl: "http://localhost:5173/kiosk",
  // Página local mostrada se a rede/URL falhar — sem isso o display fica
  // preto e a cena parece quebrada, quando na verdade é só falta de rede.
  fallback: "./src/screen/offline.html",
};
