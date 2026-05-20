import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 5000,
    rollupOptions: {
      output: {
        manualChunks: {
          codemirror: ["@uiw/react-codemirror", "@codemirror/lang-yaml", "codemirror"],
          plotly: ["plotly.js-dist-min"],
          react: ["react", "react-dom", "react-router-dom"],
          three: ["three", "@react-three/fiber", "@react-three/drei", "three-stdlib"]
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/files": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true
      }
    }
  }
});
