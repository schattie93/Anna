import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import { init as initOffline } from "./offline/core";
import { UnlockDialog } from "./offline/OfflineUI";
import "./styles.css";

void initOffline();

// Service Worker: lädt die Oberfläche auch ohne Server (nur statische Programmdateien, keine Patientendaten)
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => void navigator.serviceWorker.register("/sw.js").catch(() => undefined));
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <UnlockDialog />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
