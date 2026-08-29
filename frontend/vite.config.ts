import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker the API is another service ("api"); locally it's on the host.
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // The backend is same-origin through this proxy, so the frontend never
    // needs to know the API host or deal with CORS.
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
