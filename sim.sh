#!/usr/bin/env bash
# Uso: ./sim.sh preparar | levantar | correr | bajar
set -euo pipefail

SIM_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${APP_DIR:-$SIM_DIR/../SplitItLab/SplitIt}"
export SIM_DIR
set -a; source "$SIM_DIR/.env.sim"; set +a

compose() {
  docker compose -p splitit-sim --env-file "$SIM_DIR/.env.sim" \
    -f "$APP_DIR/docker-compose.yml" -f "$SIM_DIR/compose.sim.yml" "$@"
}

preparar() {
  local certs="$SIM_DIR/certs"
  mkdir -p "$certs"
  if [ ! -f "$certs/ca.crt" ]; then
    echo "→ Certificados del Google falso"
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=SplitIt Simulacion CA" \
      -keyout "$certs/ca.key" -out "$certs/ca.crt" 2>/dev/null
    openssl req -newkey rsa:2048 -nodes -subj "/CN=www.googleapis.com" \
      -keyout "$certs/googleapis.key" -out "$certs/googleapis.csr" 2>/dev/null
    printf "subjectAltName=DNS:www.googleapis.com\n" > "$certs/san.ext"
    openssl x509 -req -in "$certs/googleapis.csr" -CA "$certs/ca.crt" -CAkey "$certs/ca.key" \
      -CAcreateserial -days 3650 -extfile "$certs/san.ext" -out "$certs/googleapis.crt" 2>/dev/null
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$certs/firma.pem" 2>/dev/null
  fi
  if [ ! -f "$certs/truststore.p12" ]; then
    echo "→ Certificados de confianza de la API (los de Java + el del Google falso)"
    docker run --rm -v "$certs:/certs" eclipse-temurin:21-jre sh -c '
      cp "$JAVA_HOME/lib/security/cacerts" /certs/truststore.p12 &&
      keytool -importcert -noprompt -keystore /certs/truststore.p12 -storepass changeit \
        -alias splitit-simulacion -file /certs/ca.crt >/dev/null &&
      chmod 644 /certs/truststore.p12'
  fi
  chmod 644 "$certs"/*.key "$certs"/firma.pem

  echo "→ Playwright"
  (cd "$SIM_DIR/playwright" && npm install --no-audit --no-fund && npx playwright install chromium)

  echo "→ Locust"
  python3 -m venv "$SIM_DIR/.venv"
  "$SIM_DIR/.venv/bin/pip" install -q -r "$SIM_DIR/locust/requirements.txt"
  echo "Listo."
}

esperar() {
  local url="$1" nombre="$2"
  for _ in $(seq 1 90); do
    if curl -fs "$url" >/dev/null; then return 0; fi
    sleep 2
  done
  echo "✗ $nombre no respondió en $url"; exit 1
}

levantar() {
  echo "→ Levantando SplitIt de simulación (base vacía)"
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  compose up -d --build
  esperar "http://localhost:$API_PORT/api/status" "La API"
  esperar "http://localhost:$WEB_PORT" "El front"
  esperar "http://localhost:$MINT_PORT/salud" "El Google falso"
  echo "Arriba: front http://localhost:$WEB_PORT · API http://localhost:$API_PORT"
}

correr() {
  local usuarios="${USUARIOS:-30}" duracion="${DURACION:-5m}" calentamiento="${CALENTAMIENTO:-60}"
  local res="$SIM_DIR/resultados"
  rm -rf "$res"; mkdir -p "$res"

  echo "→ Base vacía para esta corrida"
  compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q -c \
    "truncate expenses, invite_links, event_members, events, users restart identity cascade" >/dev/null

  echo "→ Locust: $usuarios usuarios simulados durante $duracion"
  "$SIM_DIR/.venv/bin/locust" -f "$SIM_DIR/locust/locustfile.py" --headless \
    -u "$usuarios" -r 2 -t "$duracion" --stop-timeout 180 --host "http://localhost:$API_PORT" \
    --csv "$res/locust" --html "$res/locust.html" --only-summary >"$res/locust.log" 2>&1 &
  local locust_pid=$!

  echo "→ Calentamiento de ${calentamiento}s antes de los navegadores"
  sleep "$calentamiento"

  echo "→ Playwright: recorridos reales en navegador, con la carga encima"
  (cd "$SIM_DIR/playwright" && npx playwright test) || echo "  (algún recorrido de Playwright falló; queda en el reporte)"

  echo "→ Esperando que termine Locust"
  wait "$locust_pid" || true

  echo "→ Contraste con la regla del KPI de primer gasto"
  compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F ',' -c "
    with primeros as (
      select e.id, e.created_at, min(x.created_at) as primero
      from events e left join expenses x on x.event_id = e.id
      where e.name not like '[prep]%'
      group by e.id, e.created_at)
    select count(*),
           count(*) filter (where primero - created_at <= interval '2 minutes')
    from primeros;" >"$res/contraste-kpi.csv"

  "$SIM_DIR/.venv/bin/python" -I "$SIM_DIR/reporte.py" "$SIM_DIR"
  echo "Reporte: $res/reporte.md"
}

bajar() { compose down -v --remove-orphans; }

case "${1:-}" in
  preparar) preparar ;;
  levantar) levantar ;;
  correr) correr ;;
  bajar) bajar ;;
  *) echo "Uso: ./sim.sh preparar | levantar | correr | bajar"; exit 1 ;;
esac
