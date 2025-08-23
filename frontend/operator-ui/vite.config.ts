import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// If you want to proxy to backend at localhost:8000 during dev, uncomment below:
// proxy: { "/orchestrator": "http://localhost:8000", "/a2a": "http://localhost:8000" }
export default defineConfig({
  plugins: [react()],
  server: {
    strictPort: true,
    proxy: {
      "/orchestrator": "http://localhost:8000",
      "/a2a": "http://localhost:8000",
      "/ask": "http://localhost:8000"
    }
  }
});
