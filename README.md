# Simulación del objetivo de SplitIt

Simulación local del objetivo de producto (`splitit-dirproy/01-vision/splitit-producto.md`):

- al menos el **80% de los owners** se registra, crea el evento y carga el primer gasto en **menos de 2 minutos**;
- al menos el **80% de los invitados** ve su saldo en **menos de 30 segundos**.

Todo corre en esta máquina. No toca el repo de la app, no manda nada a la plataforma de KPIs y no pisa el
stack de desarrollo (usa sus propios puertos y su propia base).

## Cómo funciona

- **Locust** pone la multitud: usuarios ficticios que hacen los dos recorridos por la API, cada uno con su
  propio ritmo. De ahí sale el porcentaje contra la meta.
- **Playwright** pone la pantalla: navegadores reales, en tamaño celular, hacen los mismos recorridos con la
  carga encima. Quedan videos.
- **El Google falso** permite registrarse con Google sin Google. La API lo verifica como si fuera el real
  (firma, emisor, vencimiento), porque dentro del docker de la simulación la dirección de Google apunta a él.
- **Contraste:** sobre la base de la corrida se aplica la regla del KPI de primer gasto. Tiene que dar igual
  o más que el owner de Locust.

Las demoras humanas y sus fuentes están en [`ritmo.json`](ritmo.json). Cambiar ahí cambia las dos herramientas.

## Requisitos

Docker, Node 20+, Python 3.10+ y openssl. El repo de la app en `../SplitItLab/SplitIt` (o indicar otro con
`APP_DIR=...`).

## Uso

```bash
./sim.sh preparar   # una sola vez: certificados del Google falso, Playwright y Locust
./sim.sh levantar   # construye y levanta SplitIt de simulación (front :3100, API :8180)
./sim.sh correr     # corre todo y deja resultados/reporte.md
./sim.sh bajar      # apaga y borra la base de simulación
```

`correr` arranca siempre con la base vacía. Se puede ajustar:

| Variable | Default | Qué cambia |
|---|---|---|
| `USUARIOS` | 30 | Usuarios de Locust a la vez (1 owner cada 3 invitados) |
| `DURACION` | 5m | Cuánto dura la carga |
| `CALENTAMIENTO` | 60 | Segundos de carga antes de largar los navegadores |
| `REPETICIONES` | 3 | Veces que Playwright hace cada recorrido |

Ejemplo: `USUARIOS=50 DURACION=10m ./sim.sh correr`.

Si se cambia algo en la app, hay que volver a `levantar` para reconstruirla.

## Informe final

- [`informe/informe-final.md`](informe/informe-final.md): el informe escrito, con la corrida final del 12/11/2026.
- [`informe/splitit-contra-reloj.html`](informe/splitit-contra-reloj.html): la versión visual, con videos y gráficos.
  Es un solo archivo y se abre en cualquier navegador.

Después de una corrida nueva, `.venv/bin/python -I informe/armar.py .` regenera la versión visual y `public/`.

## Publicarlo en Vercel

`public/` es el sitio: la página del informe y sus videos. `vercel.json` le indica a Vercel que publique solo esa
carpeta, sin instalar ni compilar nada; el resto del repo no queda expuesto.

1. Subir el repo a GitHub.
2. En Vercel: **Add New → Project**, elegir el repo y dejar todo como viene (Framework: Other).
3. **Deploy**. Cada push a la rama principal vuelve a publicarlo.

Para actualizarlo después de una corrida nueva: `armar.py`, commit de `public/` y push.

## Resultados

En `resultados/`: `reporte.md` (lo que se muestra), `locust.html` (detalle de la carga) y
`playwright/` (un video por corrida).

## Límites

- Mide si el recorrido **se puede** hacer a tiempo a ritmo humano. No detecta a alguien que no entiende una
  pantalla: el robot sabe qué tocar.
- No incluye lo que tarda en abrir la ventana real de Google ni la red del celular.
- La variación entre personas (σ en `ritmo.json`) es un supuesto apoyado en la dispersión del tipeo.
# splitit-simulacion
