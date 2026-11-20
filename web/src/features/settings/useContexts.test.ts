import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiSession, ContextsData } from "../../api/types";
import { useContexts } from "./useContexts";

const SESSION: ApiSession = { port: 4321, token: "t", error: null };
const CONTEXTS: ContextsData = {
  names: ["empresa"],
  active: "empresa",
  folder: "/x/contextos/empresa",
  target: "/x/contexto/contexto.md",
  weights: {},
  entries: [],
  busy: false,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function fakeApi(answer: () => Response = () => json(CONTEXTS)) {
  const calls: { path: string; body: unknown }[] = [];
  const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = decodeURIComponent(new URL(String(input)).pathname);
    calls.push({ path, body: init?.body ? JSON.parse(String(init.body)) : null });
    return Promise.resolve(answer());
  });
  return { fetch, calls };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useContexts", () => {
  it("cada accion llama su ruta y pone la lista que respondio", async () => {
    const api = fakeApi();
    vi.stubGlobal("fetch", api.fetch);
    const onContexts = vi.fn();
    const { result } = renderHook(() => useContexts(SESSION, onContexts));
    act(() => {
      result.current.choose("");
      result.current.create();
      result.current.rename("empresa", "  clientes ");
      result.current.reload();
      result.current.openFolder();
      result.current.openSnapshot();
    });
    await waitFor(() => expect(onContexts).toHaveBeenCalledTimes(6));
    expect(api.calls).toEqual([
      { path: "/api/contexts/active", body: { name: "" } },
      { path: "/api/contexts", body: {} },
      { path: "/api/contexts/empresa/rename", body: { name: "clientes" } },
      { path: "/api/contexts/reload", body: {} },
      { path: "/api/contexts/open-folder", body: {} },
      { path: "/api/contexts/open-snapshot", body: {} },
    ]);
  });

  it("renombrar al mismo nombre o vacio no pide nada", () => {
    const api = fakeApi();
    vi.stubGlobal("fetch", api.fetch);
    const { result } = renderHook(() => useContexts(SESSION, vi.fn()));
    act(() => {
      result.current.rename("empresa", "empresa");
      result.current.rename("empresa", "   ");
    });
    expect(api.calls).toEqual([]);
  });

  it("un 409 queda como mensaje", async () => {
    const api = fakeApi(() => json({ detail: "No hay un contexto en uso" }, 409));
    vi.stubGlobal("fetch", api.fetch);
    const onContexts = vi.fn();
    const { result } = renderHook(() => useContexts(SESSION, onContexts));
    act(() => result.current.openFolder());
    await waitFor(() => expect(result.current.error).toContain("No hay un contexto en uso"));
    expect(onContexts).not.toHaveBeenCalled();
  });

  it("sin sesion no llama a la API", () => {
    const api = fakeApi();
    vi.stubGlobal("fetch", api.fetch);
    const { result } = renderHook(() => useContexts(null, vi.fn()));
    act(() => result.current.reload());
    expect(api.fetch).not.toHaveBeenCalled();
  });
});
