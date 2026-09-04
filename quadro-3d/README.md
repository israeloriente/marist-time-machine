# Quadro 3D — Marista Pio X

Estudo em 3D de um quadro de honra digital para o Colégio Marista Pio X: a
moldura física do quadro de formandos com um **display 16:9 rodando a
aplicação web de verdade** dentro dela.

App **Electron** + **Three.js**, sem nenhum asset externo: toda a geometria e
todas as texturas são geradas em código na inicialização.

## Rodar

```bash
cd quadro-3d
npm install
npm start        # `prestart` já roda o build do bundle
```

Durante o desenvolvimento:

```bash
npm run watch    # esbuild em watch num terminal
npm start        # electron noutro
```

## As duas versões

| | Tecla | O que é |
|---|---|---|
| **Com frontão** | `Q` | Coroamento no topo — cruz, frontão triangular e cornija — com o display 16:9 ocupando todo o resto. É o que sobrou do quadro impresso de 2003. |
| **Tela cheia** | `W` | Moldura limpa, o display ocupa o painel inteiro. A identidade fica numa placa de metal gravada no rodapé da moldura. |

Nos dois casos o display é o **mesmo painel**; muda só o gabinete em volta.

## O display

Área ativa de **1.92 × 1.08 m** — 1000 px por metro, ou seja **1920 × 1080
exatos**, com diagonal de 2.20 m (~87"). É um tamanho comercial de verdade para
hall de escola.

A página é um elemento DOM real — `<webview>` do Electron — posicionado no
espaço 3D pelo `CSS3DRenderer` via `matrix3d`, com um plano *punch-through* em
WebGL abrindo o buraco no canvas. Não é textura capturada: é o navegador
rodando dentro da cena, diagramando em 1920×1080 nativos, com animação e clique.

Por padrão carrega `https://capsula-marista.israeloriente.com/kiosk`. Para
apontar noutro lugar:

```bash
QUADRO_SCREEN_URL=http://localhost:5173/kiosk npm start
```

Se a URL falhar (sem rede, servidor fora), o display cai numa página local de
reserva em `src/screen/offline.html` — sem isso a tela fica preta e a cena
parece quebrada quando na verdade é só falta de rede.

**Modo toque** (`T`, sai com `Esc`): trava a órbita, traz a camada CSS3D para a
frente e liga os eventos de ponteiro. Aí dá para usar a aplicação de verdade,
clicando dentro do quadro.

## Controles

| | |
|---|---|
| Arrastar | orbitar |
| Scroll | aproximar / afastar |
| `Q` / `W` | versão: com frontão / tela cheia |
| `T` / `Esc` | entra e sai do modo toque |
| `1`–`5` | câmeras: frontal, 3/4, frontão, tela, rasante |
| `A` | vidro da frente |
| `R` | faixas de reflexo |
| `P` | parede e rodapé de pedra |
| `G` | giro automático |

## Estrutura

```
quadro-3d/
├── index.html            # casca + HUD
├── electron/
│   ├── main.js           # janela, webviewTag e endurecimento do guest
│   └── preload.js        # versões + a URL do display
├── src/
│   ├── config.js         # TODAS as medidas, em metros
│   ├── geo.js            # helpers de geometria (box, plane, moldura oca)
│   ├── textures.js       # texturas procedurais
│   ├── crown.js          # o coroamento (cruz, frontão, cornija)
│   ├── screens.js        # o display: tela viva (CSS3D) + moldura e vidro
│   ├── board.js          # moldura, painel, os dois modos, vidro
│   ├── scene-env.js      # parede, rodapé, cartaz, luzes
│   ├── app.js            # renderers, câmera, HUD, troca de modo, loop
│   ├── screen/offline.html  # página de reserva do display
│   └── styles.css
└── dist/app.js           # bundle gerado pelo esbuild (não versionado)
```

Para mexer em proporção, comece sempre por `src/config.js` — nenhum número de
geometria está espalhado pelos outros arquivos.

## Decisões

**O display é o dado fixo, não o quadro.** A primeira versão derivava tudo da
foto do quadro na parede (2.44:1) e espremia a tela lá dentro, o que dava um
painel de 3.6:1 que ninguém fabrica. Agora a ordem inverteu: parte-se de um
painel 16:9 real e o gabinete é construído em volta — que é como a coisa
funciona no mundo físico. Por isso os dois modos têm alturas diferentes: o
modo com frontão precisa da faixa extra em cima. `layout(mode)` em `config.js`
resolve isso, e o quadro é deslocado em Y para que a **base** caia sempre na
mesma altura da parede, senão a composição pularia ao trocar de modo.

**Duas composições, não uma.** Orbitando, a camada CSS3D fica *atrás* do canvas
e aparece pelo buraco do punch-through — assim a moldura e o vidro compõem por
cima e a oclusão funciona. Em modo toque ela vai para a *frente*, ganha eventos
de ponteiro e a órbita trava. Não dá para ter as duas coisas ao mesmo tempo:
DOM não entra no z-buffer.

**Uma instância da aplicação por vez.** Os dois modos têm tela viva. Ao trocar
de modo, o `CSS3DObject` sai da cena e o `CSS3DRenderer` remove o elemento do
DOM, então nunca há dois navegadores embutidos rodando junto. `setActive()`
reforça isso escondendo o host.

**O vidro é neutro, não o acrílico amarelado de 2003.** Uma vidraça encardida
sobre um display não faz sentido: quem instala uma tela troca por vidro
antirreflexo. Daí a opacidade de 0.035.

**O mapa de ambiente é gerado em runtime.** Um equirretangular procedural
(luminárias de teto + janela à esquerda) passa pelo `PMREMGenerator`. Sem HDR
externo: o app roda offline e o resultado é idêntico em qualquer máquina.

## Três armadilhas do `<webview>` que custaram depuração

Estão comentadas no código para não custarem de novo.

**Nunca sobrescreva `display`.** Ele usa `display:flex` internamente para fazer
o `<object>` filho preencher o elemento. Trocar por `block` faz a largura
funcionar e a altura colapsar para os 150 px default — a página é renderizada
num viewport errado e aparece cortada.

**O custom element não existe durante o parse do script.** Medido:
`document.createElement('webview')` no parse não tem `loadURL`; no
`DOMContentLoaded` já tem. Como o modo padrão monta uma tela viva na hora,
detectar cedo demais fazia cair no `<iframe>` — que esbarra em
`X-Frame-Options` e derruba justamente o caso de uso principal. Por isso o
`setMode` inicial espera o DOM.

**`allowpopups` é atributo booleano de HTML.** A simples presença vale `true`,
mesmo escrito `allowpopups="false"` — ou seja, escrever isso *liga* popups. A
ausência é o jeito de desligar. O processo principal ainda força
`params.allowpopups = false` em `will-attach-webview`.

## Histórico

O commit `abe6d38` guarda a versão anterior: a réplica completa do quadro
impresso de 2003, com as seis fotos de turma envelhecidas, listas de nomes,
pilastras, a maquete da fachada PIOX inteira (colunas, porta, pórtico,
janelas) e a letra aplicada do cabeçalho. Tudo isso saiu daqui para dar lugar
ao display; se precisar de alguma peça de volta, está lá.
