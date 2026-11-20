import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Dropdown from "./Dropdown";

const OPTIONS = [
  { key: "small", label: "small", help: "El más rápido" },
  { key: "medium", label: "medium" },
  { key: "large-v3-turbo", label: "turbo", help: "El elegido" },
];

function setup(value = "large-v3-turbo", disabled = false) {
  const onChange = vi.fn();
  render(
    <Dropdown
      label="Modelo"
      value={value}
      options={OPTIONS}
      disabled={disabled}
      onChange={onChange}
    />,
  );
  return { onChange, button: screen.getByRole("combobox", { name: "Modelo" }) };
}

describe("Dropdown", () => {
  it("muestra la etiqueta elegida y abre la lista con su ayuda al hacer clic", () => {
    const { onChange, button } = setup();
    expect(button).toHaveTextContent("turbo");
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(screen.getByRole("option", { name: /turbo/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("El más rápido")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: /small/ }));
    expect(onChange).toHaveBeenCalledWith("small");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("con el teclado: flechas, Enter elige y Esc cierra sin elegir", () => {
    const { onChange, button } = setup("small");
    fireEvent.keyDown(button, { key: "ArrowDown" });
    fireEvent.keyDown(button, { key: "ArrowDown" });
    expect(button).toHaveAttribute("aria-activedescendant", expect.stringMatching(/-1$/));
    fireEvent.keyDown(button, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("medium");
    fireEvent.keyDown(button, { key: "ArrowDown" });
    fireEvent.keyDown(button, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onChange).toHaveBeenCalledOnce();
  });

  it("elegir la misma opcion no avisa; desactivado no abre; un clic afuera cierra", () => {
    const { onChange, button } = setup();
    fireEvent.click(button);
    fireEvent.click(screen.getByRole("option", { name: /turbo/ }));
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(button);
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("desactivado no abre", () => {
    const { button } = setup("small", true);
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
