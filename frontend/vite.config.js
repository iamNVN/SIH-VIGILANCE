import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // 8001, not 8000: an orphaned backend process from an earlier
        // session is stuck listening on 8000 and can't be killed through
        // any normal channel on this machine (Get-Process/taskkill/
        // Stop-Process all report "no such process" for the PID that
        // Get-NetTCPConnection says owns the socket) -- routing around it
        // rather than fighting it further.
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
