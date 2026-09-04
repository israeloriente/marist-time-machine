// ---------------------------------------------------------------------------
// config.js — todas as medidas num lugar só. Tudo em METROS.
//
// A ordem de derivação inverteu em relação à primeira versão. Antes o quadro
// vinha da foto (2.44:1) e a tela se espremia dentro dele. Agora o display é o
// dado fixo — um painel 16:9 de verdade — e a moldura é construída em volta,
// que é como a coisa funciona no mundo físico: você compra o painel e manda
// fazer o gabinete.
//
// Sistema de coordenadas: origem no centro do quadro, X pra direita, Y pra
// cima, Z saindo da parede em direção ao observador.
// ---------------------------------------------------------------------------

// Área ativa de 1.92 x 1.08 m = 1920x1080 a 1000 px por metro, com diagonal de
// 2.20 m (~87"). É um tamanho comercial de verdade pra hall de escola.
export const DISPLAY = {
  width: 1.92,
  height: 1.08,
  bezel: 0.028,
  depth: 0.055,
};

export const FRAME = {
  face: 0.055, // largura da face da moldura preta
  depth: 0.11,
  margin: 0.014, // folga entre a moldura e o bezel do display
};

// ---------------------------------------------------------------------------
// Coroamento PIOX
//
// O único elemento do quadro impresso que sobrevive: cruz, frontão triangular
// e a cornija que o apoia. Sem placa, sem letreiro — a identidade textual fica
// por conta da própria aplicação, na tela logo abaixo.
//
// O conjunto encosta no display: a cornija apoia direto na borda de cima do
// bezel, sem faixa creme entre os dois. Por isso NÃO há um `y` fixo aqui — a
// base sai de `crownBase` em layout(), calculado a partir do topo do bezel.
// Assim mexer no tamanho do painel não descola o coroamento.
// ---------------------------------------------------------------------------
export const CROWN = {
  pedimentWidth: 0.92,
  pedimentHeight: 0.185,
  corniceHeight: 0.028,
  crossHeight: 0.072,
  topMargin: 0.018, // folga entre a ponta da cruz e a moldura
};

// Altura que o coroamento reserva acima do display. Derivada das peças, então
// mudar a altura do frontão ajusta a faixa sozinho.
export const CROWN_BAND =
  CROWN.corniceHeight + CROWN.pedimentHeight + CROWN.crossHeight + CROWN.topMargin;

// ---------------------------------------------------------------------------
// Os dois modos
//
//   'crown'  — coroamento PIOX no topo, display 16:9 embaixo.
//   'single' — moldura limpa, display 16:9 ocupando o painel inteiro.
//
// Nos dois casos o display é o MESMO painel 1920x1080; muda só o gabinete em
// volta. Por isso o quadro do modo 'crown' é mais alto: ele precisa da faixa
// extra pro coroamento.
// ---------------------------------------------------------------------------
export function layout(mode) {
  const pad = DISPLAY.bezel + FRAME.margin;
  const band = mode === "crown" ? CROWN_BAND : 0;

  const panelW = DISPLAY.width + pad * 2;
  const panelH = DISPLAY.height + pad * 2 + band;
  const screenY = -panelH / 2 + pad + DISPLAY.height / 2;

  return {
    mode,
    panelW,
    panelH,
    panelHalfW: panelW / 2,
    panelHalfH: panelH / 2,
    boardW: panelW + FRAME.face * 2,
    boardH: panelH + FRAME.face * 2,
    // O display é alinhado embaixo; o coroamento ocupa a faixa que sobra.
    screenY,
    // Borda de cima do bezel — é aqui que a cornija do coroamento apoia.
    crownBase: screenY + DISPLAY.height / 2 + DISPLAY.bezel,
  };
}

// Placa gravada no rodapé da moldura no modo 'single': sem o coroamento, é ela
// que carrega a identidade do objeto.
export const PLATE = {
  width: 1.05,
  height: 0.04,
};

// Camadas em Z. O quadro é raso: tudo acontece entre a chapa de fundo e o
// vidro da frente, num intervalo de ~7 cm.
export const Z = {
  back: 0.0,
  panel: 0.03, // face do painel creme
  crown: 0.052, // corpo do coroamento
  crownFront: 0.086, // frontão e cruz (ponto mais alto do relevo)
  screen: 0.062, // superfície do display
  glass: 0.1, // vidro grande da frente
  frameFront: FRAME.depth,
};

// URL que o display carrega.
// Sobrescrevível por QUADRO_SCREEN_URL (ver electron/main.js).
export const SCREEN = {
  defaultUrl: "https://capsula-marista.israeloriente.com/kiosk",
  devUrl: "http://localhost:5173/kiosk",
  // Página local mostrada se a rede/URL falhar — sem isso o display fica
  // preto e a cena parece quebrada, quando na verdade é só falta de rede.
  fallback: "./src/screen/offline.html",
};

// ---------------------------------------------------------------------------
// Ambiente: parede, rodapé de pedra e o cartaz azul no canto.
//
// `boardBottom` é a altura em que a base do quadro fica na parede. Os dois
// modos têm alturas diferentes, então o quadro é deslocado em Y pra que a base
// caia sempre aqui — assim a composição com o rodapé não muda ao trocar de
// modo.
// ---------------------------------------------------------------------------
export const ROOM = {
  boardBottom: -0.75,
  wallZ: -0.02,
  wallWidth: 16,
  wallHeight: 9,
  floorY: -1.9,
  wainscotTop: -0.81,
  posterX: -1.5,
  posterTop: -0.92,
  posterW: 0.5,
  posterH: 0.38,
};

export const PALETTE = {
  frame: 0x14161a, // preto da moldura e do coroamento
  paper: 0xe6dcc4, // fundo creme envelhecido
  metal: 0x2a2c30,
  wall: 0xf2f0ec,
  stone: 0x5f5e5a,
  chrome: 0xb9bcc0,
};
