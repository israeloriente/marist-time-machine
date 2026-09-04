const { contextBridge } = require("electron");

// O renderer é Three.js puro — não precisa de nada do Node. Expomos só as
// versões (pro rodapé do HUD) e a URL que o display deve carregar, que vem do
// processo principal via additionalArguments.
const arg = process.argv.find((a) => a.startsWith("--quadro-screen-url="));

contextBridge.exposeInMainWorld("quadro", {
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
  },
  screenUrl: arg ? arg.slice("--quadro-screen-url=".length) : null,
});
