"""Usuarios ficticios de SplitIt, a ritmo humano, contra la API local.

Cada iteración de un usuario es una persona nueva que hace el recorrido completo:
- Owner: llega a la portada, se registra con Google, crea el evento y carga el primer gasto.
- Invitado: abre un link compartido, entra sin cuenta y mira su saldo.

Entre pedido y pedido la persona "lee", "piensa", "toca" y "tipea" con las demoras de ritmo.json.
Las llamadas a la API son las mismas que hace el front en cada pantalla.
"""

import json
import math
import os
import random
import threading
import time
import uuid
from pathlib import Path

import requests
from locust import HttpUser, between, events, task

SIM_DIR = Path(__file__).resolve().parent.parent
RITMO = json.loads((SIM_DIR / "ritmo.json").read_text())
MINT_URL = f"http://localhost:{os.environ.get('MINT_PORT', '8099')}/mint"
RESULTADOS = SIM_DIR / "resultados"

LINKS: list[dict] = []  # links que comparten los owners, para que entren los invitados
DURACIONES: dict[str, list[tuple[float, bool, float]]] = {"owner": [], "invitado": []}
LOCK = threading.Lock()

NOMBRES_EVENTO = ["Asado del sábado", "Viaje a Bariloche", "Cumple de Juli", "Cena de egresados"]
AMIGOS = ["Lucas", "Marcos", "Fran", "Sofi", "Caro", "Nacho"]
GASTOS = [("Carne", "45000"), ("Super", "23800"), ("Nafta", "18000"), ("Bebidas", "12500")]


class Persona:
    """Una persona con su propio ritmo: algunas más rápidas, otras bastante más lentas."""

    def __init__(self):
        self.factor = math.exp(random.gauss(0, RITMO["dispersion_sigma"]))

    def _esperar(self, segundos):
        v = RITMO["variacion_por_accion"]
        time.sleep(segundos * self.factor * random.uniform(1 - v, 1 + v))

    def pensar(self):
        self._esperar(RITMO["pensar_s"])

    def tocar(self):
        self._esperar(RITMO["tocar_s"])

    def tipear(self, texto):
        self._esperar(RITMO["tecla_s"] * len(texto))

    def leer(self, palabras):
        self._esperar(RITMO["palabra_leida_s"] * palabras)


def registrar(recorrido, inicio, ok, persona, motivo=None):
    segundos = time.time() - inicio
    with LOCK:
        DURACIONES[recorrido].append((segundos, ok, persona.factor))
    events.request.fire(
        request_type="RECORRIDO",
        name=recorrido,
        response_time=segundos * 1000,
        response_length=0,
        exception=None if ok else Exception(f"no terminó: {motivo!r}"),
        context={},
    )


def sesion(client):
    """El front pregunta por la sesión en cada pantalla; sin cuenta, el 401 es la respuesta esperable."""
    with client.get("/api/auth/session", catch_response=True) as r:
        if r.status_code in (200, 401):
            r.success()


def ok(respuesta):
    respuesta.raise_for_status()
    return respuesta


class Owner(HttpUser):
    weight = 1
    wait_time = between(2, 8)

    @task
    def de_la_portada_al_primer_gasto(self):
        self.client.cookies.clear()
        p = Persona()
        sufijo = uuid.uuid4().hex[:10]
        identidad = {
            "sub": f"sim-{sufijo}",
            "email": f"sim-{sufijo}@example.com",
            "name": f"Persona {sufijo[:4]}",
        }
        nombre_evento = random.choice(NOMBRES_EVENTO)
        amigos = random.sample(AMIGOS, 3)
        gasto, monto = random.choice(GASTOS)
        inicio = time.time()
        evento_id = None
        try:
            # Portada: lee titular y bajada, toca "Comenzar".
            sesion(self.client)
            p.leer(20); p.pensar(); p.tocar()
            # Registro: lee la pantalla, toca "Continuar con Google" y elige su cuenta.
            p.leer(12); p.pensar(); p.tocar()
            p.pensar(); p.tocar()
            credencial = requests.post(MINT_URL, json=identidad, timeout=10).json()["credential"]
            ok(self.client.post("/api/auth/google", json={"credential": credencial}))
            # Sus eventos (vacío): lee y toca "Crear evento".
            sesion(self.client)
            ok(self.client.get("/api/events"))
            p.leer(15); p.pensar(); p.tocar()
            # Diálogo de crear evento: nombre, tres amigos y "Crear evento".
            p.pensar(); p.tocar(); p.tipear(nombre_evento)
            p.pensar()
            for amigo in amigos:
                p.tocar(); p.tipear(amigo + "\n")
            p.pensar(); p.tocar()
            evento = ok(
                self.client.post(
                    "/api/events",
                    json={"name": nombre_evento, "baseCurrency": "ARS", "participantNames": amigos},
                )
            ).json()
            evento_id = evento["id"]
            # Toca la tarjeta del evento.
            p.pensar(); p.tocar()
            detalle = ok(self.client.get(f"/api/events/{evento_id}", name="/api/events/[id]")).json()
            self.client.get(f"/api/events/{evento_id}/expenses", name="/api/events/[id]/expenses")
            # Detalle: lee, toca "Agregar gasto", completa nombre y monto, "Guardar gasto".
            p.leer(10); p.pensar(); p.tocar()
            p.pensar(); p.tocar(); p.tipear(gasto)
            p.tocar(); p.tipear(monto)
            p.pensar(); p.tocar()
            yo = next(m for m in detalle["members"] if not m.get("isGuest") and m.get("email"))
            ok(
                self.client.post(
                    f"/api/events/{evento_id}/expenses",
                    name="/api/events/[id]/expenses",
                    json={"name": gasto, "amount": float(monto), "currency": "ARS", "paidByMemberId": yo["id"]},
                )
            )
            registrar("owner", inicio, True, p)
        except Exception as e:
            registrar("owner", inicio, False, p, e)
            return

        # Fuera del cronómetro: comparte el link para que entren los invitados.
        try:
            token = ok(
                self.client.post(f"/api/events/{evento_id}/invite-link", name="/api/events/[id]/invite-link")
            ).json()["token"]
            with LOCK:
                LINKS.append({"token": token, "amigos": amigos})
        except Exception:
            pass


class Invitado(HttpUser):
    weight = 3
    wait_time = between(2, 8)

    @task
    def del_link_a_su_saldo(self):
        with LOCK:
            link = random.choice(LINKS) if LINKS else None
        if link is None:
            time.sleep(2)  # todavía ningún owner compartió un link
            return
        self.client.cookies.clear()
        p = Persona()
        token = link["token"]
        quien = random.choice(link["amigos"])
        inicio = time.time()
        try:
            # Abre el link: lee el encabezado y toca "Continuar sin cuenta".
            ok(self.client.get(f"/api/invitations/{token}", name="/api/invitations/[token]"))
            sesion(self.client)
            p.leer(15); p.pensar(); p.tocar()
            integrantes = ok(
                self.client.get(f"/api/invitations/{token}/members", name="/api/invitations/[token]/members")
            ).json()
            # Se busca en la lista y toca "Entrar como invitado".
            p.pensar(); p.tocar(); p.tocar()
            p.pensar(); p.tocar()
            yo = next(m for m in integrantes if m["name"] == quien)
            entrada = ok(
                self.client.post(
                    f"/api/invite-links/{token}/guest-session",
                    name="/api/invite-links/[token]/guest-session",
                    json={"memberId": yo["id"]},
                )
            ).json()
            evento_id = entrada["eventId"]
            ok(self.client.get(f"/api/events/{evento_id}", name="/api/events/[id]"))
            self.client.get(f"/api/events/{evento_id}/expenses", name="/api/events/[id]/expenses")
            # Toca la pestaña "Saldos" y encuentra su fila.
            p.pensar(); p.tocar()
            ok(self.client.get(f"/api/events/{evento_id}/balances", name="/api/events/[id]/balances"))
            p.leer(3)
            registrar("invitado", inicio, True, p)
        except Exception as e:
            registrar("invitado", inicio, False, p, e)


def percentil(valores, q):
    if not valores:
        return None
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return ordenados[f] if f == c else ordenados[f] + (ordenados[c] - ordenados[f]) * (k - f)


@events.test_stop.add_listener
def resumir(environment, **_):
    resumen = {"usuarios_simultaneos": environment.runner.target_user_count if environment.runner else None}
    for recorrido, datos in DURACIONES.items():
        limite = RITMO["limites_s"][recorrido]
        terminados = [s for s, bien, _ in datos if bien]
        resumen[recorrido] = {
            "personas": len(datos),
            "no_terminaron": len(datos) - len(terminados),
            "dentro_del_limite": sum(1 for s in terminados if s <= limite),
            "limite_s": limite,
            "p50_s": percentil(terminados, 0.5),
            "p80_s": percentil(terminados, 0.8),
            "p95_s": percentil(terminados, 0.95),
            "personas_detalle": [
                {"segundos": round(s, 2), "termino": bien, "ritmo": round(f, 3)} for s, bien, f in datos
            ],
        }
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "locust-resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))
