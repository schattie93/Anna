import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Im Entwicklungsmodus leitet Vite /api an das lokale FastAPI-Backend weiter.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: { "/api": "http://localhost:8000" },
  },
});
