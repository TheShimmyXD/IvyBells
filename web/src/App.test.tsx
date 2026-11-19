import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("muestra el titulo y el saludo", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "IvyBells" })).toBeInTheDocument();
    expect(screen.getByText("Hola: la interfaz web arranca.")).toBeInTheDocument();
  });
});
