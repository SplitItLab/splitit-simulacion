# Validación simulada del objetivo de SplitIt

12/11/2026

> Versión visual, con los videos de la corrida y los gráficos: [`splitit-contra-reloj.html`](splitit-contra-reloj.html) (se abre en cualquier navegador, sin conexión salvo por las fuentes).

## Resumen

SplitIt cumple las dos metas del objetivo de producto en una simulación local con usuarios ficticios a ritmo humano. La meta era que al menos el 80% de las personas termine dentro del límite, y en los dos recorridos lo superó.

| Recorrido | Límite | Dentro del límite | El 80% tardó menos de | Resultado |
| --- | --- | --- | --- | --- |
| Owner: se registra con Google, crea el evento y carga el primer gasto | 2 min | 39 de 39 (100%) | 77 s | Cumple |
| Invitado: abre el link, entra sin cuenta y ve su saldo | 30 s | 259 de 269 (96%) | 21 s | Cumple |

## Qué se validó

El objetivo de producto, definido a principio de año en la visión de SplitIt, dice:

> Lograr que al menos el 80% de los usuarios que crean un grupo registren un gasto en menos de 2 minutos y que al menos el 80% de los usuarios invitados puedan visualizar su balance en menos de 30 segundos, validado mediante pruebas de usuario al momento del lanzamiento.

El reloj del owner arranca antes de registrarse: los 2 minutos incluyen crear la cuenta con Google.

## Cómo se simuló

Dos herramientas hacen los recorridos como lo haría una persona, sobre una copia de SplitIt que corre en una sola máquina.

- **Usuarios ficticios (Locust):** muchas personas a la vez recorren la app por la API, con las mismas llamadas que hace cada pantalla. De acá sale el porcentaje contra la meta.
- **Navegadores reales (Playwright):** mientras dura esa carga, navegadores en tamaño celular hacen los mismos recorridos por la pantalla. Cubren lo que la API no ve, como lo que tarda en aparecer el saldo, y dejan video.
- **Google falso:** el botón "Continuar con Google" y la ventana para elegir la cuenta se ven y se usan igual. La API controla el comprobante como lo haría con Google (firma, emisor y vencimiento), porque en la simulación la dirección de Google apunta al falso.
- **Todo local:** la app no se modificó, la simulación usa una base propia y los KPIs quedan forzados a no salir de la máquina. El entorno de desarrollo sigue funcionando en paralelo.

## Ritmo humano

Las personas simuladas no van a la velocidad de la máquina: cada acción tarda lo que dice la literatura de interacción persona-computadora. Se tomó el tipeo en celular porque SplitIt se usa en la mesa, y es la velocidad más lenta.

| Acción | Tiempo | Fuente |
| --- | --- | --- |
| Pensar antes de actuar | 1,35 s | Modelo KLM, operador M. [Card, Moran y Newell, 1980](https://doi.org/10.1145/358886.358895) |
| Apuntar y tocar un botón | 1,2 s | Modelo KLM, operadores P (1,1 s) + B (0,1 s). Card, Moran y Newell, 1980 |
| Tipear, por carácter | 0,33 s | Tipeo en celular, ~36 palabras/min. [Palin et al., 2019](https://doi.org/10.1145/3338286.3340120), 37.370 personas |
| Leer, por palabra | 0,25 s | Lectura silenciosa, ~240 palabras/min. [Brysbaert, 2019](https://doi.org/10.1016/j.jml.2019.104047) |
| Elegir la cuenta de Google | ~2,5 s | Pensar + tocar, mismo modelo KLM |

A cada persona le toca un ritmo propio al azar: la mitad va más rápido que el promedio y la otra mitad más lento. Algunas tardan el doble en cada acción. El tamaño de esa variación es un supuesto, del orden de la dispersión de la velocidad de tipeo que muestran Palin (2019) y [Dhakal et al. (2018)](https://doi.org/10.1145/3173574.3174220). Además, cada acción varía ±15% dentro de la misma persona.

Al tiempo humano se suma el tiempo real de la app: cada paso espera a que la pantalla responda antes de seguir. A ritmo promedio, el owner tarda unos 60 s y el invitado unos 16 s.

## Resultados de la corrida final

La corrida duró 5 minutos, con 30 usuarios simulados a la vez (un owner cada tres invitados), y no hubo errores de la app. Los porcentajes contra la meta están en el resumen. Acá va cómo se reparten los tiempos.

**Usuarios simulados**

| Recorrido | Personas | Mediana | El 95% tardó menos de | Fuera del límite |
| --- | --- | --- | --- | --- |
| Owner (límite 2 min) | 39 | 61 s | 103 s | 0 |
| Invitado (límite 30 s) | 269 | 15 s | 29 s | 10 |

Los 10 invitados que se pasaron fueron personas con ritmo lento. La app respondió en milisegundos en todos los pasos, así que el tiempo lo pone la persona y no la espera.

**Navegadores reales en celular, con la carga encima**

| Recorrido | Ritmo de la persona | Tiempo | Resultado |
| --- | --- | --- | --- |
| Owner | 0,98× | 60 s | Dentro |
| Owner | 1,13× | 70 s | Dentro |
| Owner | 1,26× | 75 s | Dentro |
| Invitado | 0,74× | 13 s | Dentro |
| Invitado | 0,78× | 13 s | Dentro |
| Invitado | 1,26× | 21 s | Dentro |

Un ritmo de 1× es una persona promedio, y 2× tarda el doble en cada acción. Cada corrida en navegador quedó grabada en video. En una prueba anterior, una persona con ritmo 2,1× tardó 127 s como owner y se pasó del límite, como es esperable en alguien tan lento.

## Contraste con el KPI de primer gasto

La regla del KPI diario se aplicó a los datos de la corrida y dio 42 de 42 eventos (100%) con primer gasto en menos de 2 minutos, coherente con la simulación. La regla mide desde que se crea el evento, sin el registro, así que tiene que dar igual o más que el owner simulado, y así fue.

En una corrida de prueba el contraste dio menos que la simulación. La causa fue que al cortar la carga quedaban owners a mitad de camino, con el evento creado y sin gasto. Se corrigió dejando que cada persona termine su recorrido antes de cortar.

## Límites

La simulación mide si los recorridos se pueden hacer a tiempo a ritmo humano. Queda fuera de su alcance:

- **Entender la pantalla:** el robot sabe qué botón tocar. Una persona puede dudar, equivocarse o volver atrás, y eso no está medido.
- **Google real:** no incluye lo que tarda en abrir la ventana real de Google.
- **Red del celular:** todo corre en una sola máquina, sin la demora de una red móvil.
- **Variación entre personas:** el tamaño de la variación es un supuesto. Si fuera mayor, habría más personas lentas fuera del límite.
- **Recorridos cortos:** el owner carga un evento con tres amigos y un gasto. Un evento más grande lleva más tiempo.

## Cómo repetirla

Se repite con cuatro comandos desde esta carpeta:

```bash
./sim.sh preparar   # una sola vez
./sim.sh levantar   # SplitIt de simulación en localhost:3100
./sim.sh correr     # deja resultados/reporte.md y los videos
./sim.sh bajar      # apaga y borra la base de simulación
```

Cada corrida arranca con la base vacía. La cantidad de usuarios, la duración y las repeticiones se ajustan con variables, por ejemplo `USUARIOS=50 DURACION=10m ./sim.sh correr`. Las demoras humanas se cambian en `ritmo.json`, y el cambio vale para las dos herramientas. Si la app cambia, hay que volver a `levantar` para reconstruirla.

Para regenerar la página con los resultados de una corrida nueva: `.venv/bin/python -I informe/armar.py .`
