import "@fontsource-variable/schibsted-grotesk";
import "@fontsource-variable/source-serif-4/opsz.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
