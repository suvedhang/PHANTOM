import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// PHANTOM web app. The API base URL is injected at build time via
// VITE_API_BASE_URL (see .env.example). No secrets are ever placed in the
// frontend bundle.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  preview: {
    port: 4173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
