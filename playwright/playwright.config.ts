import { defineConfig, devices } from "@playwright/test";

const WEB_PORT = process.env.WEB_PORT ?? "3100";
const REPETICIONES = Number(process.env.REPETICIONES ?? "3");

export default defineConfig({
  testDir: "./recorridos",
  outputDir: "../resultados/playwright",
  timeout: 5 * 60_000,
  workers: 3,
  repeatEach: REPETICIONES,
  reporter: [["list"]],
  use: {
    // SplitIt se usa en la mesa: celular.
    ...devices["Pixel 7"],
    baseURL: `http://localhost:${WEB_PORT}`,
    video: "on",
    locale: "es-AR",
    actionTimeout: 30_000,
  },
});
