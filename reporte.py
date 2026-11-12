"""Junta lo de Locust, Playwright y el contraste con el KPI en resultados/reporte.md."""

import json
import sys
from datetime import datetime
from pathlib import Path

sim = Path(sys.argv[1])
res = sim / "resultados"
ritmo = json.loads((sim / "ritmo.json").read_text())
meta = ritmo["meta_porcentaje"]
NOMBRES = {"owner": "Owner: de la portada al primer gasto (con registro)", "invitado": "Invitado: del link a su saldo"}


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "—"


def seg(v):
    return "—" if v is None else f"{v:.0f} s"


def veredicto(dentro, total):
    if not total:
        return "sin datos"
    return "✅ cumple" if 100 * dentro / total >= meta else "❌ no cumple"


lineas = [
    "# Validación simulada del objetivo de SplitIt",
    "",
    f"Corrida del {datetime.now():%d/%m/%Y %H:%M}, local. Meta: al menos el {meta}% de las personas dentro del límite.",
    "",
]

locust = json.loads((res / "locust-resumen.json").read_text()) if (res / "locust-resumen.json").exists() else None
lineas += ["## Usuarios simulados (Locust)", ""]
if locust:
    lineas += [
        f"{locust.get('usuarios_simultaneos')} usuarios a la vez, cada uno con su propio ritmo.",
        "",
        "| Recorrido | Personas | Dentro del límite | Mediana | 80% tardó menos de | 95% tardó menos de | Resultado |",
        "|---|---|---|---|---|---|---|",
    ]
    for clave in ("owner", "invitado"):
        r = locust[clave]
        lineas.append(
            f"| {NOMBRES[clave]} (límite {r['limite_s']} s) | {r['personas']} "
            f"| {r['dentro_del_limite']} ({pct(r['dentro_del_limite'], r['personas'])}) "
            f"| {seg(r['p50_s'])} | {seg(r['p80_s'])} | {seg(r['p95_s'])} "
            f"| {veredicto(r['dentro_del_limite'], r['personas'])} |"
        )
        if r["no_terminaron"]:
            lineas.append(f"|  ↳ {r['no_terminaron']} no pudieron terminar (cuentan como fuera del límite) | | | | | | |")
else:
    lineas.append("Locust no dejó resumen: mirar resultados/locust.log.")

lineas += ["", "## Navegadores reales con la carga encima (Playwright, celular)", ""]
pw_archivo = res / "playwright.jsonl"
if pw_archivo.exists():
    corridas = [json.loads(l) for l in pw_archivo.read_text().splitlines() if l.strip()]
    lineas += ["| Recorrido | Corrida | Ritmo de la persona | Tiempo | Límite | Resultado |", "|---|---|---|---|---|---|"]
    for c in sorted(corridas, key=lambda c: (c["recorrido"], c["repeticion"])):
        if not c["ok"]:
            estado = "❌ no terminó"
        else:
            estado = "✅ dentro" if c["segundos"] <= c["limite_s"] else "❌ fuera"
        lineas.append(f"| {NOMBRES[c['recorrido']]} | {c['repeticion'] + 1} | {c.get('ritmo', 1):.2f}× | {c['segundos']:.0f} s | {c['limite_s']} s | {estado} |")
    lineas += [
        "",
        "Ritmo 1× es una persona promedio; 2× tarda el doble en cada acción. "
        "Los videos de cada corrida están en `resultados/playwright/`.",
    ]
else:
    lineas.append("Playwright no dejó resultados.")

lineas += ["", "## Contraste con el KPI de primer gasto", ""]
contraste = res / "contraste-kpi.csv"
if contraste.exists() and contraste.read_text().strip():
    total, rapidos = (int(x) for x in contraste.read_text().strip().split(","))
    lineas += [
        f"Con la misma regla que usa el motor de KPIs (del evento creado al primer gasto, en 2 minutos), "
        f"sobre la base de esta corrida: **{rapidos} de {total} eventos ({pct(rapidos, total)})**.",
        "",
        "Tiene que dar igual o más que el owner de Locust, porque el KPI no cuenta el registro. "
        "Si da menos, alguno de los dos está midiendo mal.",
    ]
else:
    lineas.append("No se pudo consultar la base.")

lineas += [
    "",
    "## De dónde salen las demoras",
    "",
    "| Acción | Tiempo | Fuente |",
    "|---|---|---|",
    f"| Pensar antes de actuar | {ritmo['pensar_s']} s | {ritmo['_fuentes']['pensar_s']} |",
    f"| Apuntar y tocar | {ritmo['tocar_s']} s | {ritmo['_fuentes']['tocar_s']} |",
    f"| Tipear, por carácter | {ritmo['tecla_s']} s | {ritmo['_fuentes']['tecla_s']} |",
    f"| Leer, por palabra | {ritmo['palabra_leida_s']} s | {ritmo['_fuentes']['palabra_leida_s']} |",
    f"| Variación entre personas | σ = {ritmo['dispersion_sigma']} | {ritmo['_fuentes']['dispersion_sigma']} |",
    "",
    "Al tiempo humano se le suma el tiempo real de la app: cada paso espera a que la pantalla responda.",
    "No incluye la carga de la ventana real de Google ni la red del celular.",
]

(res / "reporte.md").write_text("\n".join(lineas) + "\n")
