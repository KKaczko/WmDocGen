import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { StaticJsonRepository } from "./data/repository";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("The page has no #root element.");
}
createRoot(root).render(
  <StrictMode>
    <App repository={new StaticJsonRepository()} />
  </StrictMode>,
);
