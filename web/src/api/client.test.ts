import { describe, expect, it, vi } from "vitest";
import { ApiError, getPrefs, listeningApi, messageForStatus, readEvents, savePref } from "./client";
import type { ApiSession } from "./types";

const SESSION: ApiSession = { port: 4321, token: "abc", error: null };

function answer(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("client", () => {
  it("lee lo recordado con el token de la sesion", async () => {
    const fetchMock = vi.fn().mockResolvedValue(answer({ theme: "dark" }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getPrefs(SESSION)).resolves.toEqual({ theme: "dark" });
    const [target, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(target).toBe("http://127.0.0.1:4321/api/prefs");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer abc");
  });

  it("guarda una preferencia por POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue(answer({ module: "agent" }));
    vi.stubGlobal("fetch", fetchMock);
    await savePref(SESSION, "module", "agent");
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ key: "module", value: "agent" });
  });

  it("convierte un 401 en un mensaje en espanol", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(answer({}, 401)));
    await expect(getPrefs(SESSION)).rejects.toThrow(messageForStatus(401));
  });

  it("sin puerto devuelve el error de la sesion sin tocar la red", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const broken: ApiSession = { port: null, token: "", error: "Sin Python" };
    await expect(getPrefs(broken)).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("muestra el motivo en espanol que manda la API", async () => {
    const detail = "Todavía no hay transcripción que guardar.";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(answer({ detail }, 409)));
    await expect(listeningApi.save(SESSION, "/tmp/a.md")).rejects.toThrow(detail);
  });

  it("lee el canal SSE con el token y pide solo lo posterior", async () => {
    const body = 'id: 3\nevent: phrase\ndata: {"text": "Ho"}\n\n: sigue\n\nid: 4\nevent: lat';
    const rest = 'ency\ndata: {"last_s": 1.2}\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(body));
        controller.enqueue(new TextEncoder().encode(rest));
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(new Response(stream));
    vi.stubGlobal("fetch", fetchMock);
    const seen: [number, string, unknown][] = [];
    const signal = new AbortController().signal;
    await readEvents(SESSION, "/api/listening/events", 2, (...e) => seen.push(e), signal);
    expect(seen).toEqual([
      [3, "phrase", { text: "Ho" }],
      [4, "latency", { last_s: 1.2 }],
    ]);
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer abc");
    expect(headers.get("Last-Event-ID")).toBe("2");
  });
});
