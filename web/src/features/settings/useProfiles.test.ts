import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiSession, ProfilesData } from "../../api/types";
import { SAVE_DELAY_MS } from "./profileView";
import { useProfiles } from "./useProfiles";

const SESSION: ApiSession = { port: 4321, token: "t", error: null };
const PROFILES: ProfilesData = {
  names: ["ejemplo", "soporte", "ventas"],
  active: "ventas",
  editable: ["soporte", "ventas"],
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

type Call = { path: string; method: string; body: unknown };

function fakeApi(answers: Record<string, Response> = {}) {
  const calls: Call[] = [];
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = decodeURIComponent(new URL(String(input)).pathname);
    const method = init?.method ?? "GET";
    calls.push({ path, method, body: init?.body ? JSON.parse(String(init.body)) : null });
    if (path in answers) {
      return Promise.resolve(answers[path]);
    }
    if (method === "GET") {
      const name = path.split("/").pop() ?? "";
      return Promise.resolve(
        json({ name, text: `Texto de ${name}.`, editable: name !== "ejemplo" }),
      );
    }
    return Promise.resolve(json({ ...PROFILES, name: "soporte copia" }));
  });
  return { fetch, calls };
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useProfiles", () => {
  it("abre el perfil en uso y luego el elegido", async () => {
    const api = fakeApi();
    vi.stubGlobal("fetch", api.fetch);
    const { result } = renderHook(() => useProfiles(SESSION, PROFILES, vi.fn()));
    await waitFor(() => expect(result.current.text).toBe("Texto de ventas."));
    expect(result.current.editable).toBe(true);
    act(() => result.current.select("ejemplo"));
    await waitFor(() => expect(result.current.text).toBe("Texto de ejemplo."));
    expect(result.current.editable).toBe(false);
  });

  it("guarda una sola vez tras dejar de escribir", async () => {
    const api = fakeApi();
    vi.stubGlobal("fetch", api.fetch);
    const onProfiles = vi.fn();
    const { result } = renderHook(() => useProfiles(SESSION, PROFILES, onProfiles));
    await waitFor(() => expect(result.current.loading).toBe(false));
    vi.useFakeTimers();
    act(() => result.current.edit("B"));
    act(() => result.current.edit("Br"));
    expect(result.current.saveState).toBe("pending");
    expect(result.current.text).toBe("Br");
    await act(async () => {
      vi.advanceTimersByTime(SAVE_DELAY_MS);
      await Promise.resolve();
    });
    vi.useRealTimers();
    await waitFor(() => expect(result.current.saveState).toBe("saved"));
    const saves = api.calls.filter((call) => call.path.endsWith("/save"));
    expect(saves).toEqual([
      { path: "/api/profiles/ventas/save", method: "POST", body: { text: "Br" } },
    ]);
    expect(onProfiles).toHaveBeenCalled();
  });

  it("antes de cambiar de perfil guarda lo que esperaba su turno", async () => {
    const api = fakeApi();
    vi.stubGlobal("fetch", api.fetch);
    const { result } = renderHook(() => useProfiles(SESSION, PROFILES, vi.fn()));
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.edit("Nuevo texto"));
    act(() => result.current.select("soporte"));
    await waitFor(() => expect(result.current.text).toBe("Texto de soporte."));
    const paths = api.calls.map((call) => call.path);
    expect(paths.indexOf("/api/profiles/ventas/save")).toBeLessThan(
      paths.indexOf("/api/profiles/soporte"),
    );
  });

  it("copiar abre la copia; un pedido rechazado deja su motivo", async () => {
    const api = fakeApi({
      "/api/profiles/ventas/rename": json({ detail: "Ya hay un perfil «soporte»." }, 409),
    });
    vi.stubGlobal("fetch", api.fetch);
    const onProfiles = vi.fn();
    const withCopy = { ...PROFILES, names: [...PROFILES.names, "soporte copia"] };
    const { result, rerender } = renderHook(({ list }) => useProfiles(SESSION, list, onProfiles), {
      initialProps: { list: PROFILES },
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.rename("soporte"));
    await waitFor(() => expect(result.current.error).toBe("Ya hay un perfil «soporte»."));
    act(() => result.current.duplicate());
    await waitFor(() => expect(onProfiles).toHaveBeenCalled());
    rerender({ list: withCopy });
    await waitFor(() => expect(result.current.current).toBe("soporte copia"));
    expect(result.current.error).toBeNull();
  });

  it("sin API muestra el ejemplo y no pide nada", () => {
    const api = fakeApi();
    vi.stubGlobal("fetch", api.fetch);
    const seed = { selected: "soporte", texts: { soporte: "Ejemplo." } };
    const { result } = renderHook(() => useProfiles(null, PROFILES, vi.fn(), seed));
    expect(result.current.current).toBe("soporte");
    expect(result.current.text).toBe("Ejemplo.");
    expect(api.calls).toEqual([]);
  });
});
