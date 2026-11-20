import { describe, expect, it, vi } from "vitest";
import { ApiError, getPrefs, messageForStatus, savePref } from "./client";
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
});
