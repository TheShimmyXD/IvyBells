import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiSession, ListeningSnapshot } from "../../api/types";
import { LAST_OPEN_MESSAGE, useLiveListening } from "./useLiveListening";

const SESSION: ApiSession = { port: 4321, token: "t", error: null };

const SNAPSHOT: ListeningSnapshot = {
  state: "stopped",
  status: "Detenido",
  message: "",
  model: "",
  models: [
    { key: "small", label: "small", help: "" },
    { key: "large-v3-turbo", label: "turbo", help: "" },
  ],
  devices: {},
  closed_sources: ["ellos"],
  path: null,
  transcript: { ellos: { finals: [], partial: null }, tu: { finals: [], partial: null } },
  resumes: { ellos: [], tu: [] },
  last_event: 4,
};

const SSE = [
  'id: 4\nevent: phrase\ndata: {"source":"tu","final":true,"clock":"20:00:00","text":"vieja","stable_words":0}\n\n',
  'id: 5\nevent: phrase\ndata: {"source":"tu","final":true,"clock":"20:00:01","text":"Hola.","stable_words":0}\n\n',
  'id: 6\nevent: latency\ndata: {"last_s":1.5,"median_s":1.6}\n\n',
].join("");

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

/** La API falsa: snapshot, un canal que manda SSE una vez y despues queda abierto. */
function fakeApi(answers: Record<string, unknown> = {}) {
  let streams = 0;
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/listening/events") {
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
    if (init?.method === "POST") {
      return Promise.resolve(json(answers[path] ?? {}));
    }
    return Promise.resolve(json(SNAPSHOT));
  });
}

function posted(fetchMock: ReturnType<typeof fakeApi>, path: string): unknown {
  const call = fetchMock.mock.calls.find(
    ([input, init]) => new URL(String(input)).pathname === path && init?.method === "POST",
  );
  return call === undefined ? undefined : JSON.parse(call[1]?.body as string);
}

afterEach(() => vi.unstubAllGlobals());

describe("useLiveListening", () => {
  it("abre con el snapshot y suma solo los eventos nuevos del canal", async () => {
    const fetchMock = fakeApi();
    vi.stubGlobal("fetch", fetchMock);
    const { result, unmount } = renderHook(() => useLiveListening(SESSION));
    await waitFor(() => expect(result.current.view?.latency.median_s).toBe(1.6));
    expect(result.current.view?.finals.tu.map((line) => line.text)).toEqual(["Hola."]);
    const events = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/events"));
    expect(new Headers(events?.[1]?.headers).get("Last-Event-ID")).toBe("4");
    // Sin eleccion ni recuerdo, el ultimo de la lista (el elegido para la escucha).
    expect(result.current.model).toBe("large-v3-turbo");
    unmount();
  });

  it("inicia con el modelo recordado sin mandar dispositivos y guarda el elegido", async () => {
    const devices = { tu: { name: "mic.usb", label: "mic.usb" } };
    const fetchMock = fakeApi({ "/api/listening/start": { state: "loading", devices } });
    vi.stubGlobal("fetch", fetchMock);
    const { result, unmount } = renderHook(() => useLiveListening(SESSION, "small"));
    await waitFor(() => expect(result.current.view).not.toBeNull());
    act(() => result.current.start());
    await waitFor(() => expect(result.current.view?.devices).toEqual(devices));
    expect(posted(fetchMock, "/api/listening/start")).toEqual({ model: "small" });
    act(() => result.current.chooseModel("large-v3-turbo"));
    expect(result.current.model).toBe("large-v3-turbo");
    await waitFor(() =>
      expect(posted(fetchMock, "/api/prefs")).toEqual({
        key: "live_model",
        value: "large-v3-turbo",
      }),
    );
    unmount();
  });

  it("avisa si se intenta cerrar el ultimo canal abierto", async () => {
    const fetchMock = fakeApi({
      "/api/listening/sources/tu": { changed: false, closed: ["ellos"] },
    });
    vi.stubGlobal("fetch", fetchMock);
    const { result, unmount } = renderHook(() => useLiveListening(SESSION));
    await waitFor(() => expect(result.current.view).not.toBeNull());
    act(() => result.current.toggleSource("tu"));
    await waitFor(() => expect(result.current.notice).toBe(LAST_OPEN_MESSAGE));
    expect(posted(fetchMock, "/api/listening/sources/tu")).toEqual({ open: false });
    unmount();
  });
});
