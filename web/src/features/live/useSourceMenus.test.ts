import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiSession, SourceMenu, SourceMenus } from "../../api/types";
import { useSourceMenus } from "./useSourceMenus";

const SESSION: ApiSession = { port: 4321, token: "t", error: null };

function menu(preferred: string): SourceMenu {
  return {
    default: { name: "a.monitor", label: "a.monitor" },
    options: [{ name: "a.monitor", label: "a.monitor" }],
    preferred,
    preferred_label: preferred,
    missing: false,
    resolved: "a.monitor",
  };
}

const MENUS: SourceMenus = { ellos: menu(""), tu: menu("") };

afterEach(() => vi.unstubAllGlobals());

function fakeApi(status = 200) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname;
    const chosen = init?.body ? (JSON.parse(String(init.body)) as { name: string }).name : "";
    const body = path.startsWith("/api/listening/devices/")
      ? { ...MENUS, ellos: menu(chosen) }
      : MENUS;
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
}

describe("useSourceMenus", () => {
  it("lee los menus con la escucha detenida y no mientras escucha", async () => {
    const fetchMock = fakeApi();
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(({ idle }) => useSourceMenus(SESSION, idle), {
      initialProps: { idle: false },
    });
    expect(fetchMock).not.toHaveBeenCalled();
    rerender({ idle: true });
    await waitFor(() => expect(result.current.menus).toEqual(MENUS));
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/listening/sources");
  });

  it("elegir manda el equipo y toma los menus que devuelve la API", async () => {
    const fetchMock = fakeApi();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useSourceMenus(SESSION, false));
    act(() => result.current.choose("ellos", "a.monitor"));
    await waitFor(() => expect(result.current.menus?.ellos.preferred).toBe("a.monitor"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/listening/devices/ellos");
    expect(JSON.parse(String(init?.body))).toEqual({ name: "a.monitor" });
  });

  it("un error de la API queda como mensaje", async () => {
    vi.stubGlobal("fetch", fakeApi(422));
    const { result } = renderHook(() => useSourceMenus(SESSION, true));
    await waitFor(() => expect(result.current.error).not.toBeNull());
  });

  it("sin sesion muestra la semilla y no llama a la red", () => {
    const fetchMock = fakeApi();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useSourceMenus(null, true, MENUS));
    expect(result.current.menus).toBe(MENUS);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
