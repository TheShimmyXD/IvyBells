// Ventana minima: pide puerto y token a Tauri y prueba /api/health.
const status = document.getElementById("status");
const detail = document.getElementById("detail");
const POLL_MS = 100;
const LIMIT_MS = 30000;

function show(state, text, more = "") {
  status.dataset.state = state;
  status.textContent = text;
  detail.textContent = more;
}

async function waitSession() {
  const started = performance.now();
  while (performance.now() - started < LIMIT_MS) {
    const session = await window.__TAURI__.core.invoke("api_session");
    if (session.port || session.error) {
      return { session, waited: performance.now() - started };
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
  return { session: { error: "La API no anunció su puerto en 30 s." }, waited: LIMIT_MS };
}

async function main() {
  const { session, waited } = await waitSession();
  if (session.error) {
    show("error", session.error);
    return;
  }
  const url = `http://127.0.0.1:${session.port}/api/health`;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${session.token}` } });
  const health = await response.json();
  if (response.ok && health.ok) {
    show(
      "ok",
      `API de Python en 127.0.0.1:${session.port}: responde.`,
      `IvyBells ${health.version} · puerto anunciado en ${Math.round(waited)} ms`,
    );
  } else {
    show("error", `La API respondió ${response.status}.`, health.detail ?? "");
  }
}

main().catch((error) => show("error", "No se pudo hablar con la API.", String(error)));
