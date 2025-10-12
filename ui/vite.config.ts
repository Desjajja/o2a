import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/admin": "http://localhost:8082",
      "/v1": "http://localhost:8082",
      "/health": "http://localhost:8082"
    }
  }
});
