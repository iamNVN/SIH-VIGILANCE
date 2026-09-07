import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    watch: {
      // public/ holds video assets that get edited/re-exported outside
      // this app (an external cutter tool, a video editor) -- while one
      // of those files is momentarily locked mid-write, Vite's fs watcher
      // throws an *uncaught* EBUSY and kills the entire dev server, not
      // just that one file's HMR (verified live, twice, restarting the
      // whole server both times). Static assets under public/ don't need
      // watching for HMR anyway -- a <video src> tag just re-requests the
      // file on next load, no live-reload wiring involved -- so excluding
      // them removes the crash risk entirely instead of restarting after
      // every external edit.
      ignored: ["**/public/**"],
    },
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
