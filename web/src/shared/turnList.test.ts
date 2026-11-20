import { describe, expect, it } from "vitest";
import { withLast } from "./turnList";

describe("withLast", () => {
  it("crece, reemplaza el ultimo y se vacia", () => {
    expect(withLast(["a"], 2, "b")).toEqual(["a", "b"]);
    expect(withLast(["a", "b"], 2, "b2")).toEqual(["a", "b2"]);
    expect(withLast(["a", "b"], 0, null)).toEqual([]);
  });

  it("sin el ultimo queda vacia aunque el contador diga otra cosa", () => {
    expect(withLast(["a"], 3, null)).toEqual([]);
  });
});
