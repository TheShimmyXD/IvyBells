import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentSnapshot, ApiSession } from "../../api/types";
import type { Bubble } from "./conversation";
import { useAgent } from "./useAgent";

const SESSION: ApiSession = { port: 4321, token: "t", error: null };

const SNAPSHOT: AgentSnapshot = {
  state: "idle",
  status: "",
  mode: "manual",
  speaker: "ellos",
  busy: false,
  start_mark: null,
  sent: { ellos: [], tu: [] },
  budget: null,
  turns: [],
  last_event: 2,
};

const TURN = {
  source: "ellos",
  model: "haiku",
  mode: "manual",
  clock: "10:00:20",
  done_clock: "",
  fragment: "[10:00:08] Quería saber el precio.",
  start: { phrase: 1, word: 0 },
  end: { phrase: 1, word: 0 },
  error: "",
  cancelled: false,
  done: false,
  superseded: false,
  first_text_s: null,
};

const SSE = [
  `id: 2\nevent: turns\ndata: ${JSON.stringify({ count: 1, last: { ...TURN, answer: "vieja" } })}\n\n`,
  `id: 3\nevent: turns\ndata: ${JSON.stringify({ count: 1, last: { ...TURN, answer: "Con gusto" } })}\n\n`,
].join("");

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

function fakeApi() {
  let streams = 0;
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/agent/events") {
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
      return Promise.resolve(json({ ...SNAPSHOT, state: "start_marked" }));
    }
    return Promise.resolve(json(SNAPSHOT));
  });
}

function phrase(key: string, source: "ellos" | "tu", index: number | null): Bubble {
  return {
    kind: "phrase",
    key,
    source,
    index,
    clock: "10:00:08",
    text: "Hola",
    final: index !== null,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("useAgent", () => {
  it("abre con el snapshot y la respuesta crece con los eventos nuevos", async () => {
    vi.stubGlobal("fetch", fakeApi());
    const { result, unmount } = renderHook(() => useAgent(SESSION));
    await waitFor(() => expect(result.current.view?.turns[0]?.answer).toBe("Con gusto"));
    expect(result.current.view?.turns).toHaveLength(1);
    unmount();
  });

  it("un clic en la frase del interlocutor manda la marca; en el otro canal, nada", async () => {
    const fetchMock = fakeApi();
    vi.stubGlobal("fetch", fetchMock);
    const { result, unmount } = renderHook(() => useAgent(SESSION));
    await waitFor(() => expect(result.current.view).not.toBeNull());
    act(() => result.current.mark(phrase("tu-0", "tu", 0), "left"));
    act(() => result.current.mark(phrase("ellos-1", "ellos", 1), "left"));
    await waitFor(() => expect(result.current.view?.state).toBe("start_marked"));
    const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");
    expect(posts).toHaveLength(1);
    expect(new URL(String(posts[0][0])).pathname).toBe("/api/agent/mark_start");
    expect(JSON.parse(posts[0][1]?.body as string)).toEqual({ phrase: 1, offset: 0 });
    unmount();
  });
});
