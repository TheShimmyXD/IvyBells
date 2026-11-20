import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiSession, ChatSnapshot, ChatTurn } from "../../api/types";
import { useChat } from "./useChat";

const SESSION: ApiSession = { port: 4321, token: "t", error: null };

const SNAPSHOT: ChatSnapshot = {
  model: "haiku",
  effort: "",
  sending: false,
  turns: [],
  last_first_text_s: null,
  choices: { models: [], efforts: [] },
  last_event: 1,
};

const TURN: ChatTurn = {
  clock: "10:00:00",
  request: "Resume",
  model: "haiku",
  effort: "",
  answer: "Listo",
  error: "",
  cancelled: false,
  done: true,
  first_text_s: 1.5,
};

const SSE = [
  // Repetido de antes del snapshot: no cuenta.
  `id: 1\nevent: turns\ndata: ${JSON.stringify({ count: 0, last: null, last_first_text_s: null })}\n\n`,
  `id: 2\nevent: turns\ndata: ${JSON.stringify({ count: 1, last: TURN, last_first_text_s: 1.5 })}\n\n`,
].join("");

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

function fakeApi() {
  let streams = 0;
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/chat/events") {
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
    if (path === "/api/chat/send") {
      return Promise.resolve(json({ sent: true, model: "haiku", effort: "", sending: true }));
    }
    if (init?.method === "POST") {
      return Promise.resolve(json({ model: "sonnet", effort: "low", sending: false }));
    }
    return Promise.resolve(json(SNAPSHOT));
  });
}

function posts(fetchMock: ReturnType<typeof fakeApi>): [string, unknown][] {
  return fetchMock.mock.calls
    .filter(([, init]) => init?.method === "POST")
    .map(([input, init]) => [
      new URL(String(input)).pathname,
      JSON.parse(String(init?.body)) as unknown,
    ]);
}

afterEach(() => vi.unstubAllGlobals());

describe("useChat", () => {
  it("abre con el snapshot y sigue los turnos nuevos", async () => {
    vi.stubGlobal("fetch", fakeApi());
    const { result, unmount } = renderHook(() => useChat(SESSION));
    await waitFor(() => expect(result.current.view?.turns[0]?.answer).toBe("Listo"));
    expect(result.current.view?.lastFirstText).toBe(1.5);
    unmount();
  });

  it("manda el texto sin espacios y avisa si la API lo acepto", async () => {
    const fetchMock = fakeApi();
    vi.stubGlobal("fetch", fetchMock);
    const { result, unmount } = renderHook(() => useChat(SESSION));
    await waitFor(() => expect(result.current.view).not.toBeNull());
    let sent = false;
    await act(async () => {
      sent = await result.current.send("  ¿Qué dijeron?  ");
    });
    expect(sent).toBe(true);
    expect(result.current.view?.sending).toBe(true);
    // Con un envio en curso no sale otro.
    await act(async () => {
      sent = await result.current.send("otra");
    });
    expect(sent).toBe(false);
    expect(posts(fetchMock)).toEqual([["/api/chat/send", { text: "¿Qué dijeron?" }]]);
    unmount();
  });

  it("modelo, esfuerzo, cancelar y vaciar van a sus rutas", async () => {
    const fetchMock = fakeApi();
    vi.stubGlobal("fetch", fetchMock);
    const { result, unmount } = renderHook(() => useChat(SESSION));
    await waitFor(() => expect(result.current.view).not.toBeNull());
    act(() => {
      result.current.setModel("sonnet");
      result.current.setEffort("low");
      result.current.cancel();
      result.current.clear();
    });
    await waitFor(() => expect(result.current.view?.model).toBe("sonnet"));
    expect(posts(fetchMock)).toEqual([
      ["/api/chat/model", { model: "sonnet" }],
      ["/api/chat/effort", { effort: "low" }],
      ["/api/chat/cancel", {}],
      ["/api/chat/clear", {}],
    ]);
    unmount();
  });

  it("sin API no manda nada", async () => {
    const fetchMock = fakeApi();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useChat(null));
    expect(await result.current.send("hola")).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
