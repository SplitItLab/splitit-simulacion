import { expect, test } from "@playwright/test";
import { nuevaIdentidad, Persona, registrar, simularGoogle } from "./apoyo";

test("owner: de la portada al primer gasto, registro con Google incluido", async ({ page }, info) => {
  const identidad = nuevaIdentidad();
  await simularGoogle(page, identidad);
  const p = new Persona(page);
  let inicio = Date.now();
  let terminado = false;

  try {
    inicio = Date.now();
    p.marcar("Llega a la portada");
    await page.goto("/");

    // Portada: lee titular y bajada, toca "Comenzar".
    await p.leer(20);
    await p.pensar();
    await p.tocar(page.getByRole("link", { name: "Comenzar" }));

    // Registro: lee, toca "Continuar con Google" y elige su cuenta.
    p.marcar("Se registra con Google");
    await p.leer(12);
    await p.pensar();
    await p.tocar(page.getByRole("button", { name: "Continuar con Google" }));
    await p.pensar();
    await p.tocar(page.getByRole("dialog", { name: "Elegí una cuenta" }).getByRole("button"));

    // Sus eventos, todavía vacío: lee y toca "Crear evento".
    await page.waitForURL("**/eventos");
    p.marcar("Crea el evento");
    await p.leer(15);
    await p.pensar();
    await p.tocar(page.getByRole("button", { name: "Crear evento" }));

    // Crear evento: nombre, tres amigos y "Crear evento".
    const crear = page.getByRole("dialog", { name: "Crear evento" });
    await p.pensar();
    await p.tipear(crear.getByLabel("Nombre del evento"), "Asado del sábado");
    await p.pensar();
    for (const amigo of ["Lucas", "Marcos", "Fran"]) {
      await p.tipear(crear.getByLabel("Integrantes"), amigo);
      await page.keyboard.press("Enter");
    }
    await p.pensar();
    await p.tocar(crear.getByRole("button", { name: "Crear evento" }));

    // Entra al evento recién creado.
    await p.pensar();
    await p.tocar(page.getByText("Asado del sábado", { exact: true }));

    // Detalle: lee, toca "Agregar gasto", completa y guarda.
    p.marcar("Carga el primer gasto");
    await p.leer(10);
    await p.pensar();
    await p.tocar(page.getByRole("button", { name: "Agregar gasto" }));
    const gasto = page.getByRole("dialog", { name: "Agregar gasto" });
    await p.pensar();
    await p.tipear(gasto.getByLabel("Nombre"), "Carne");
    await p.tipear(gasto.getByLabel("Monto"), "45000");
    await p.pensar();
    await p.tocar(gasto.getByRole("button", { name: "Guardar gasto" }));

    // Ve el gasto en la lista.
    await expect(gasto).toBeHidden();
    await expect(page.getByText("Carne").first()).toBeVisible();
    p.marcar("Ve su gasto");
    terminado = true;
  } finally {
    const segundos = registrar("owner", inicio, terminado, info, p);
    info.annotations.push({ type: "segundos", description: segundos.toFixed(1) });
  }
});
