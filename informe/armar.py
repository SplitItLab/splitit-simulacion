"""Arma informe/index.html a partir de resultados/: datos de la corrida + los videos en mp4.

Uso: .venv/bin/python -I informe/armar.py <carpeta de la simulación>
"""

import base64
import copy
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sim = Path(sys.argv[1]).resolve()
res = sim / "resultados"
inf = sim / "informe"
ritmo = json.loads((sim / "ritmo.json").read_text())
locust = json.loads((res / "locust-resumen.json").read_text())
corridas = [json.loads(l) for l in (res / "playwright.jsonl").read_text().splitlines() if l.strip()]
eventos, rapidos = (int(x) for x in (res / "contraste-kpi.csv").read_text().strip().split(","))

# Acciones de cada recorrido, contadas en los scripts de Playwright (a ritmo 1).
ACCIONES = {
    "owner": {"palabras": 57, "pensar": 11, "tocar": 14, "teclas": 41},
    "invitado": {"palabras": 18, "pensar": 4, "tocar": 5, "teclas": 0},
}


def desglose(recorrido):
    a = ACCIONES[recorrido]
    return [
        {"accion": "Leer", "s": round(a["palabras"] * ritmo["palabra_leida_s"], 1)},
        {"accion": "Pensar", "s": round(a["pensar"] * ritmo["pensar_s"], 1)},
        {"accion": "Tocar", "s": round(a["tocar"] * ritmo["tocar_s"], 1)},
        {"accion": "Tipear", "s": round(a["teclas"] * ritmo["tecla_s"], 1)},
    ]


def video(recorrido):
    """El recorrido terminado con el ritmo más cercano al promedio: el más representativo."""
    candidatas = [c for c in corridas if c["recorrido"] == recorrido and c["ok"]]
    elegida = min(candidatas, key=lambda c: abs(c["ritmo"] - 1))
    origen = res / elegida["video"] / "video.webm"
    destino = inf / "videos" / f"{recorrido}.mp4"
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(origen), "-an", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-crf", "26", "-preset", "slow", "-movflags", "+faststart", str(destino)],
        check=True,
    )
    webm = inf / "videos" / f"{recorrido}.webm"
    webm.write_bytes(origen.read_bytes())
    return {
        "mp4": f"videos/{recorrido}.mp4",
        "webm": f"videos/{recorrido}.webm",
        "ritmo": elegida["ritmo"],
        "segundos": round(elegida["segundos"], 1),
        "momentos": elegida["momentos"],
    }


def resumen(recorrido):
    r = locust[recorrido]
    return {
        "personas": r["personas"],
        "dentro": r["dentro_del_limite"],
        "p50": r["p50_s"],
        "p80": r["p80_s"],
        "p95": r["p95_s"],
        "detalle": r["personas_detalle"],
    }


datos = {
    "fecha": datetime.now().strftime("%d/%m/%Y"),
    "usuarios": locust["usuarios_simultaneos"],
    "meta": ritmo["meta_porcentaje"],
    "limites": ritmo["limites_s"],
    "locust": {"owner": resumen("owner"), "invitado": resumen("invitado")},
    "navegadores": [
        {"recorrido": c["recorrido"], "segundos": round(c["segundos"], 1), "ok": c["ok"], "ritmo": c["ritmo"]}
        for c in corridas
    ],
    "videos": {"owner": video("owner"), "invitado": video("invitado")},
    "contraste": {"eventos": eventos, "rapidos": rapidos},
    "desglose": {"owner": desglose("owner"), "invitado": desglose("invitado")},
}

plantilla = (inf / "plantilla.html").read_text()
(inf / "index.html").write_text(plantilla.replace("__DATOS__", json.dumps(datos, ensure_ascii=False)))
print("informe/index.html listo (para publicar, con los videos en informe/videos/)")

def documento(cuerpo):
    """Documento HTML completo: lo de antes del primer </style> va al head."""
    corte = cuerpo.index("</style>") + len("</style>")
    return (
        '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="Validación simulada del objetivo de producto de SplitIt.">\n'
        + cuerpo[:corte] + "\n</head>\n<body>\n" + cuerpo[corte:] + "\n</body>\n</html>\n"
    )


# Sitio para Vercel: public/ con la página y los videos como archivos.
publico = sim / "public"
(publico / "videos").mkdir(parents=True, exist_ok=True)
for v in datos["videos"].values():
    for formato in ("mp4", "webm"):
        (publico / v[formato]).write_bytes((inf / v[formato]).read_bytes())
(publico / "index.html").write_text(documento(plantilla.replace("__DATOS__", json.dumps(datos, ensure_ascii=False))))
print("public/ listo (lo que publica Vercel)")

# Versión que se abre sola: un único archivo, con los videos adentro.
solo = copy.deepcopy(datos)
for v in solo["videos"].values():
    for formato, mime in (("mp4", "video/mp4"), ("webm", "video/webm")):
        crudo = (inf / v[formato]).read_bytes()
        v[formato] = f"data:{mime};base64,{base64.b64encode(crudo).decode()}"
(inf / "splitit-contra-reloj.html").write_text(documento(plantilla.replace("__DATOS__", json.dumps(solo, ensure_ascii=False))))
print("informe/splitit-contra-reloj.html listo (se abre solo, con los videos adentro)")
