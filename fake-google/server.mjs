// Google falso para la simulación local. Sin dependencias.
// - HTTPS :443, con el alias www.googleapis.com dentro de la red de docker: publica la clave pública
//   en /oauth2/v3/certs, igual que Google. La API la usa para verificar los comprobantes.
// - HTTP :8099, solo para Playwright y Locust: POST /mint firma un comprobante para una identidad.
import { createServer as createHttpsServer } from "node:https";
import { createServer as createHttpServer } from "node:http";
import { createPrivateKey, createPublicKey, sign } from "node:crypto";
import { readFileSync } from "node:fs";

const CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
if (!CLIENT_ID) throw new Error("Falta GOOGLE_CLIENT_ID");

const KID = "splitit-simulacion";
const privateKey = createPrivateKey(readFileSync("/certs/firma.pem"));
const jwk = { ...createPublicKey(privateKey).export({ format: "jwk" }), kid: KID, alg: "RS256", use: "sig" };

const b64url = (value) => Buffer.from(value).toString("base64url");

function mint({ sub, email, name }) {
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: "RS256", kid: KID, typ: "JWT" }));
  const payload = b64url(
    JSON.stringify({
      iss: "https://accounts.google.com",
      aud: CLIENT_ID,
      sub,
      email,
      email_verified: true,
      name,
      iat: now,
      exp: now + 3600,
    })
  );
  const signature = sign("sha256", Buffer.from(`${header}.${payload}`), privateKey).toString("base64url");
  return `${header}.${payload}.${signature}`;
}

const json = (res, status, body) => {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
};

createHttpsServer(
  { key: readFileSync("/certs/googleapis.key"), cert: readFileSync("/certs/googleapis.crt") },
  (req, res) => {
    if (req.url.startsWith("/oauth2/v3/certs")) return json(res, 200, { keys: [jwk] });
    json(res, 404, { error: "no existe" });
  }
).listen(443, () => console.log("Google falso: claves en https://www.googleapis.com/oauth2/v3/certs"));

createHttpServer((req, res) => {
  if (req.method === "GET" && req.url === "/salud") return json(res, 200, { ok: true });
  if (req.method === "POST" && req.url === "/mint") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      try {
        const identity = JSON.parse(body);
        if (!identity.sub || !identity.email) return json(res, 400, { error: "faltan sub o email" });
        json(res, 200, { credential: mint(identity) });
      } catch {
        json(res, 400, { error: "json inválido" });
      }
    });
    return;
  }
  json(res, 404, { error: "no existe" });
}).listen(8099, () => console.log("Google falso: comprobantes en http://localhost:8099/mint"));
