# Quadro 3D — Formandos Marista 2003

Réplica em 3D do quadro de formandos do Colégio Marista Pio X (turma de 2003,
São Marcelino Champagnat), o painel físico que dá nome a este repositório —
e um estudo de como digitalizá-lo mantendo a mesma moldura.

App **Electron** + **Three.js**, sem nenhum asset externo: toda a geometria e
todas as texturas são geradas em código na inicialização.

## As duas versões

| | Tecla | O que é |
|---|---|---|
| **Original impresso** | `Q` | O quadro de 2003 como ele é hoje: fotos coladas, acrílico amarelado, letra aplicada. |
| **Display único** | `W` | A moldura é reaproveitada e todo o miolo vira **um display ultrawide (2.6:1) rodando a aplicação web de verdade**, viva e clicável. |

### Display único: a aplicação roda mesmo

A página é um elemento DOM real — `<webview>` do Electron — posicionado no
espaço 3D pelo `CSS3DRenderer` via `matrix3d`, com um plano *punch-through* em
WebGL abrindo o buraco no canvas. Não é textura capturada: é o navegador
rodando dentro da cena, com layout, animação e clique.

Por padrão carrega `https://capsula-marista.israeloriente.com/kiosk`. Para
apontar noutro lugar:

```bash
QUADRO_SCREEN_URL=http://localhost:5173/kiosk npm start
```

Se a URL falhar (sem rede, servidor fora), o display cai numa página local de
reserva em `src/screen/offline.html` — sem isso a tela fica preta e a cena
parece quebrada quando na verdade é só falta de rede.

**Modo toque** (`T`, sai com `Esc`): trava a órbita, traz a camada CSS3D pra
frente e liga os eventos de ponteiro. Aí dá pra usar a aplicação de verdade,
clicando dentro do quadro.

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

## Controles

| | |
|---|---|
| Arrastar | orbitar |
| Scroll | aproximar / afastar |
| `Q` / `W` | versão: original impresso / display único |
| `T` / `Esc` | entra e sai do modo toque (só na versão de display único) |
| `1`–`5` | câmeras: frontal, 3/4, fachada, turmas, rasante |
| `A` | acrílico da frente |
| `R` | faixas de reflexo |
| `P` | parede e rodapé de pedra |
| `G` | giro automático |

## Estrutura

```
quadro-3d/
├── index.html            # casca + HUD
├── electron/
│   ├── main.js           # janela (contextIsolation + sandbox, sem Node no renderer)
│   └── preload.js        # só expõe as versões pro rodapé
├── src/
│   ├── config.js         # TODAS as medidas, em metros
│   ├── geo.js            # helpers de geometria (box, plane, moldura oca)
│   ├── textures.js       # texturas procedurais (papel, fotos, pedra, reflexos)
│   ├── facade.js         # a maquete "PIOX" do centro
│   ├── screens.js        # o display: tela viva (CSS3D) + moldura e vidro
│   ├── board.js          # moldura, alas, vãos, os dois modos, acrílico
│   ├── scene-env.js      # parede, rodapé, cartaz, luzes
│   ├── app.js            # renderers, câmera, HUD, troca de modo, loop
│   ├── screen/offline.html  # página de reserva do display
│   └── styles.css
└── dist/app.js           # bundle gerado pelo esbuild (não versionado)
```

Para mexer em proporção, comece sempre por `src/config.js` — nenhum número de
geometria está espalhado pelos outros arquivos.

## Como as medidas foram tiradas

Na foto de referência a moldura ocupa uma caixa de ~1540×630 px, ou seja
**2.44:1**. Fixei a largura real em **4.20 m** (tamanho plausível para um
quadro de formatura de parede) e derivei todo o resto dessa razão, lendo as
posições dos elementos em pixels e convertendo para metros.

O quadro final tem **4.20 × 1.72 × 0.11 m**.

## Decisões que valem registro

**As alas são simétricas, a foto não.** Na foto a ala esquerda parece maior que
a direita. Isso é perspectiva — a câmera estava à esquerda. O objeto real é
simétrico: vão estreito nas pontas (retrato / comissão) e dois vãos largos de
cada lado (Bio-Exatas I-II, Humanas I-II).

**A barriga do quadro não foi modelada.** A borda inferior da moldura parece
arqueada na foto, mas a linha do rodapé de pedra arqueia junto — é distorção de
barril da lente, não o objeto. Modelar isso seria copiar um defeito da câmera.

**Nenhum nome foi inventado.** Os rótulos legíveis na foto (`BIO EXATAS I`,
`HUMANAS II`, `TURMA - SÃO MARCELINO CHAMPAGNAT`, `PIOX`, `PATRONO`…) entram
como texto de verdade. As listas de formandos entram como filetes tipográficos:
na escala real cada nome tem ~2 mm de altura, que é exatamente o que o olho
enxerga a qualquer distância de leitura. Inventar nomes num memorial de pessoas
reais seria pior que representá-lo honestamente.

**O envelhecimento é por lote, como no original.** As duas fotos das pontas
colapsaram para magenta e as quatro do centro para ciano — degradação de
corante de impressão fotográfica, que varia por lote de papel. `applyAging()`
em `textures.js` reproduz isso convertendo a imagem para luminância e
re-tingindo com a cor do desvio, além de achatar o contraste e lavar em direção
ao branco do papel.

**As letras do cabeçalho são relevo mapeado, não geometria extrudada.**
`TextGeometry` exigiria empacotar uma fonte `.json`; o par color-map +
bump-map dá o mesmo resultado sob a luz rasante sem dependência de asset.
Todo o resto do relevo (frontão, colunas, pilastras, moldura, espaçadores) é
geometria de verdade.

**O acrílico é reflexo, não transmissão.** `transmission` numa chapa de 4 m
custa um render pass inteiro e ainda lava o conteúdo atrás. Aqui a chapa é
translúcida com `clearcoat` + envMap, mais faixas de brilho aditivas
reproduzindo os reflexos diagonais da foto. Desligável com `A` / `R`.

**O mapa de ambiente é gerado em runtime.** Um equirretangular procedural
(luminárias de teto + janela à esquerda) passa pelo `PMREMGenerator`. Sem HDR
externo: o app roda offline e o resultado é idêntico em qualquer máquina.


## Decisões da versão touchscreen

**No display único a letra aplicada some e vira placa gravada no rodapé.** Se o
miolo inteiro é tela, o cabeçalho passa a ser responsabilidade da aplicação. A
identidade física do objeto migra pra uma placa de metal gravada na moldura —
que é exatamente o que uma instalação real faz ao trocar o miolo por um painel.

**O acrílico amarelado só existe no modo original.** Uma vidraça de 2003
encardida sobre um display não faz sentido: quem instala uma tela troca por
vidro antirreflexo neutro. No modo com tela a vidraça fica quase invisível
(opacidade 0.035 contra 0.11), senão a UI fica suja.

**Duas composições, não uma.** Orbitando, a camada CSS3D fica *atrás* do canvas
e aparece pelo buraco do punch-through — assim a moldura e o vidro compõem por
cima e a oclusão funciona. Em modo toque ela vai pra *frente*, ganha eventos de
ponteiro e a órbita trava. Não dá pra ter as duas coisas ao mesmo tempo: DOM
não entra no z-buffer.

**Nunca sobrescreva `display` num `<webview>`.** Ele usa `display:flex`
internamente pra fazer o `<object>` filho preencher o elemento. Trocar por
`block` faz a largura funcionar e a altura colapsar pros 150 px default — a
página é renderizada num viewport errado e aparece cortada. Isso custou uma
sessão de depuração; está comentado em `styles.css` pra não custar outra.
