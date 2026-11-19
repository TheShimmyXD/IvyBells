// Monta la aplicacion; nada mas (web_frontend.md, seccion 1).
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("Falta el elemento #root en index.html");
}
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
