import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { randomInt, randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { request, type Locator, type Page, type TestInfo } from "@playwright/test";

const SIM_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const RITMO = JSON.parse(readFileSync(path.join(SIM_DIR, "ritmo.json"), "utf8"));
const MINT_URL = `http://localhost:${process.env.MINT_PORT ?? "8099"}/mint`;
export const API_URL = `http://localhost:${process.env.API_PORT ?? "8180"}`;

export type Identidad = { sub: string; email: string; name: string };

export function nuevaIdentidad(): Identidad {
  const sufijo = randomUUID().replaceAll("-", "").slice(0, 10);
  return { sub: `sim-${sufijo}`, email: `sim-${sufijo}@example.com`, name: `Persona ${sufijo.slice(0, 4)}` };
}

async function credencial(identidad: Identidad): Promise<string> {
  const res = await fetch(MINT_URL, { method: "POST", body: JSON.stringify(identidad) });
  return (await res.json()).credential;
}

// Azar del sistema, independiente en cada navegador que corre en paralelo.
export function azar(): number {
  return randomInt(0, 2 ** 47) / 2 ** 47;
}

// Normal con Box-Muller, para el ritmo propio de cada persona.
function normal(): number {
  return Math.sqrt(-2 * Math.log(1 - azar())) * Math.cos(2 * Math.PI * azar());
}

/** Una persona con su propio ritmo. Cada acción espera lo que tardaría un humano y después actúa. */
export class Persona {
  readonly factor = Math.exp(normal() * RITMO.dispersion_sigma);
  private readonly page: Page;
  private readonly origen = Date.now();
  readonly momentos: { momento: string; s: number }[] = [];

  constructor(page: Page) {
    this.page = page;
  }

  /** Anota en qué segundo del video pasa algo, para saltar a ese momento. */
  marcar(momento: string) {
    this.momentos.push({ momento, s: Number(((Date.now() - this.origen) / 1000).toFixed(1)) });
  }

  private esperar(segundos: number) {
    const v = RITMO.variacion_por_accion;
    const ms = segundos * this.factor * (1 - v + azar() * 2 * v) * 1000;
    return this.page.waitForTimeout(ms);
  }

  pensar() {
    return this.esperar(RITMO.pensar_s);
  }

  leer(palabras: number) {
    return this.esperar(RITMO.palabra_leida_s * palabras);
  }

  /** Lleva el dedo hasta el elemento (y espera a que esté en pantalla) y lo toca. */
  async tocar(objetivo: Locator) {
    await objetivo.waitFor({ state: "visible" });
    await this.esperar(RITMO.tocar_s);
    await objetivo.click();
  }

  async tipear(campo: Locator, texto: string) {
    await this.tocar(campo);
    const ms = RITMO.tecla_s * this.factor * 1000;
    await campo.pressSequentially(texto, { delay: ms });
  }

  async elegir(lista: Locator, opcion: string) {
    await this.tocar(lista);
    await this.esperar(RITMO.tocar_s);
    await lista.selectOption({ label: opcion });
  }
}

/**
 * Reemplaza el script de Google por uno falso: el mismo botón "Continuar con Google" y, al tocarlo,
 * una ventana para elegir la cuenta. Al elegirla, entrega un comprobante firmado por el Google falso.
 */
export async function simularGoogle(page: Page, identidad: Identidad) {
  await page.exposeFunction("__simCredencial", () => credencial(identidad));
  const script = `
    (() => {
      let config;
      window.google = { accounts: { id: {
        initialize(c) { config = c; },
        renderButton(parent) {
          const boton = document.createElement("button");
          boton.type = "button";
          boton.textContent = "Continuar con Google";
          boton.style.cssText = "height:44px;width:100%;border:1px solid #dadce0;border-radius:4px;background:#fff";
          boton.onclick = () => {
            const ventana = document.createElement("div");
            ventana.setAttribute("role", "dialog");
            ventana.setAttribute("aria-label", "Elegí una cuenta");
            ventana.style.cssText = "position:fixed;inset:0;background:#fff;z-index:99999;padding:24px;font-family:sans-serif";
            ventana.innerHTML = '<p style="font-size:20px">Elegí una cuenta</p><p>para ir a SplitIt</p>';
            const cuenta = document.createElement("button");
            cuenta.type = "button";
            cuenta.textContent = ${JSON.stringify(identidad.email)};
            cuenta.style.cssText = "display:block;width:100%;padding:16px;margin-top:16px;text-align:left";
            cuenta.onclick = async () => {
              ventana.remove();
              config.callback({ credential: await window.__simCredencial() });
            };
            ventana.appendChild(cuenta);
            document.body.appendChild(ventana);
          };
          parent.appendChild(boton);
        },
      } } };
    })();`;
  await page.route("https://accounts.google.com/gsi/client", (route) =>
    route.fulfill({ contentType: "text/javascript", body: script })
  );
}

/** Evento con un gasto y link de invitación, armado por la API. Queda fuera del cronómetro. */
export async function prepararEvento(amigos: string[]): Promise<string> {
  const api = await request.newContext({ baseURL: API_URL });
  const organizador = nuevaIdentidad();
  const ok = async (res: Awaited<ReturnType<typeof api.post>>) => {
    if (!res.ok()) throw new Error(`${res.url()} → ${res.status()} ${await res.text()}`);
    return res.status() === 204 ? null : res.json();
  };
  await ok(await api.post("/api/auth/google", { data: { credential: await credencial(organizador) } }));
  const evento = await ok(
    await api.post("/api/events", {
      data: { name: "[prep] Asado del sábado", baseCurrency: "ARS", participantNames: amigos },
    })
  );
  const detalle = await ok(await api.get(`/api/events/${evento.id}`));
  const yo = detalle.members.find((m: { email?: string | null }) => m.email === organizador.email);
  await ok(
    await api.post(`/api/events/${evento.id}/expenses`, {
      data: { name: "Carne", amount: 45000, currency: "ARS", paidByMemberId: yo.id },
    })
  );
  const { token } = await ok(await api.post(`/api/events/${evento.id}/invite-link`));
  await api.dispose();
  return token;
}

export function registrar(
  recorrido: "owner" | "invitado",
  inicio: number,
  ok: boolean,
  info: TestInfo,
  persona: Persona
) {
  const segundos = (Date.now() - inicio) / 1000;
  const dir = path.join(SIM_DIR, "resultados");
  mkdirSync(dir, { recursive: true });
  appendFileSync(
    path.join(dir, "playwright.jsonl"),
    JSON.stringify({ recorrido, segundos, ok, ritmo: Number(persona.factor.toFixed(2)), momentos: persona.momentos, video: path.relative(dir, info.outputDir), limite_s: RITMO.limites_s[recorrido], prueba: info.title, repeticion: info.repeatEachIndex }) + "\n"
  );
  return segundos;
}
