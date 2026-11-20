import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiSession } from "../../api/types";
import { DEMO_SNAPSHOT } from "./demo";
import { useSettings } from "./useSettings";

const SESSION: ApiSession = { port: 4321, token: "t", error: null };

const SSE = [
  // Repetido de antes del snapshot: no cuenta.
  `id: 1\nevent: config\ndata: ${JSON.stringify({ ...DEMO_SNAPSHOT.config, model: "sonnet" })}\n\n`,
  `id: 2\nevent: account\ndata: ${JSON.stringify({ text: "Sesión activa", level: "ok", login: "" })}\n\n`,
].join("");

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function fakeApi(posts: Record<string, Response> = {}) {
  let streams = 0;
  return vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>((input) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/settings/events") {
      streams += 1;
      if (streams > 1) {
        return new Promise<Response>(() => undefined);
      }
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(SSE));
          controller.close();
        },
      });
      return Promise.resolve(new Response(body, { status: 200 }));
    }
    if (path in posts) {
      return Promise.resolve(posts[path]);
    }
    return Promise.resolve(json({ ...DEMO_SNAPSHOT, last_event: 1 }));
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("useSettings", () => {
  it("abre con el snapshot y aplica solo los eventos nuevos", async () => {
    vi.stubGlobal("fetch", fakeApi());
    const { result } = renderHook(() => useSettings(SESSION));
    await waitFor(() => expect(result.current.view?.account.level).toBe("ok"));
    expect(result.current.view?.config.model).toBe("haiku");
    expect(result.current.view?.lastEvent).toBe(2);
  });

  it("un cambio manda su pedido y toma lo guardado que responde la API", async () => {
    const saved = { ...DEMO_SNAPSHOT.config, timeout_s: 300 };
    const api = fakeApi({ "/api/settings/timeout": json(saved) });
    vi.stubGlobal("fetch", api);
    const { result } = renderHook(() => useSettings(SESSION));
    await waitFor(() => expect(result.current.view).not.toBeNull());
    act(() => result.current.setTimeout(300));
    await waitFor(() => expect(result.current.view?.config.timeout_s).toBe(300));
    const call = api.mock.calls.find(([input]) => String(input).endsWith("/timeout"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ seconds: 300 });
  });

  it("un correo mal escrito no se repite arriba: lo dice la insignia", async () => {
    const api = fakeApi({
      "/api/settings/account": json({ detail: "«x» no parece un correo" }, 422),
      "/api/settings/model": json({ detail: "Modelo desconocido: zz." }, 422),
    });
    vi.stubGlobal("fetch", api);
    const { result } = renderHook(() => useSettings(SESSION));
    await waitFor(() => expect(result.current.view).not.toBeNull());
    act(() => result.current.setAccount("x"));
    await waitFor(() =>
      expect(api.mock.calls.some(([input]) => String(input).endsWith("/account"))).toBe(true),
    );
    expect(result.current.error).toBeNull();
    act(() => result.current.setModel("zz"));
    await waitFor(() => expect(result.current.error).toBe("Modelo desconocido: zz."));
  });
});
