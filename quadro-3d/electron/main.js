const { app, BrowserWindow, shell } = require("electron");
const path = require("node:path");
const fs = require("node:fs");

const ROOT = path.join(__dirname, "..");

// URL que a versão de display único carrega dentro da tela.
// Sobrescreva com QUADRO_SCREEN_URL=http://localhost:5173/kiosk npm start
const SCREEN_URL =
  process.env.QUADRO_SCREEN_URL || "https://capsula-marista.israeloriente.com/kiosk";

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 960,
    minHeight: 600,
    backgroundColor: "#101216",
    show: false,
    title: "Quadro de Formandos — Marista Pio X · 2003",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      // <webview> é o que permite embutir a aplicação web dentro do display 3D.
      // Um <iframe> esbarraria em X-Frame-Options; o webview é um WebContents
      // separado, como uma aba, e não esbarra. O guest é endurecido em
      // 'will-attach-webview' logo abaixo.
      webviewTag: true,
      // sandbox fica desligado porque webviewTag exige o módulo de webview no
      // renderer. O renderer continua sem nodeIntegration e com isolamento de
      // contexto — ele só executa nosso bundle, que não toca em API do Node.
      sandbox: false,
      additionalArguments: [`--quadro-screen-url=${SCREEN_URL}`],
    },
  });

  win.setMenuBarVisibility(false);
  win.once("ready-to-show", () => win.show());

  // O guest é conteúdo externo: sem preload, sem integração com Node, e sem
  // poder virar uma janela nova.
  win.webContents.on("will-attach-webview", (_event, webPreferences, params) => {
    delete webPreferences.preload;
    webPreferences.nodeIntegration = false;
    webPreferences.contextIsolation = true;
    params.allowpopups = false;
  });

  // Qualquer tentativa de abrir janela — do app ou do guest — vai pro navegador.
  const denyPopups = (contents) =>
    contents.setWindowOpenHandler(({ url }) => {
      shell.openExternal(url);
      return { action: "deny" };
    });
  denyPopups(win.webContents);
  win.webContents.on("did-attach-webview", (_e, guest) => denyPopups(guest));

  win.loadFile(path.join(ROOT, "index.html"));
  return win;
}

app.whenReady().then(() => {
  // `npm start` roda `prestart` -> build. Se alguém chamar `electron .` direto
  // sem ter buildado, a janela abriria em branco — melhor avisar.
  if (!fs.existsSync(path.join(ROOT, "dist", "app.js"))) {
    console.error(
      "\n[quadro-3d] dist/app.js não existe. Rode `npm run build` (ou use `npm start`).\n",
    );
  }
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
