import { expect, test } from "@playwright/test";
import { azar, Persona, prepararEvento, registrar } from "./apoyo";

test("invitado: del link compartido a ver su saldo, sin cuenta", async ({ page }, info) => {
  // La persona se crea primero: sus marcas cuentan desde que arranca el video.
  const p = new Persona(page);
  const amigos = ["Lucas", "Marcos", "Fran"];
  const token = await prepararEvento(amigos);
  const quien = amigos[Math.floor(azar() * amigos.length)];
  let inicio = Date.now();
  let terminado = false;

  try {
    inicio = Date.now();
    p.marcar("Abre el link");
    await page.goto(`/eventos/invitacion/${token}`);

    // Invitación: lee el encabezado y toca "Continuar sin cuenta".
    await p.leer(15);
    await p.pensar();
    await p.tocar(page.getByRole("button", { name: "Continuar sin cuenta" }));

    // Se busca en la lista y entra.
    p.marcar("Se elige en la lista");
    await p.pensar();
    await p.elegir(page.getByLabel("¿Quién sos en este evento?"), quien);
    await p.pensar();
    await p.tocar(page.getByRole("button", { name: "Entrar como invitado" }));

    // En el evento: toca "Saldos" y encuentra su fila.
    await page.waitForURL(/\/eventos\/\d+/);
    p.marcar("Busca su saldo");
    await p.pensar();
    await p.tocar(page.getByRole("tab", { name: "Saldos" }));
    await expect(page.getByRole("tabpanel").getByText(quien).first()).toBeVisible();
    p.marcar("Ve su saldo");
    await p.leer(3);
    terminado = true;
  } finally {
    const segundos = registrar("invitado", inicio, terminado, info, p);
    info.annotations.push({ type: "segundos", description: segundos.toFixed(1) });
  }
});
