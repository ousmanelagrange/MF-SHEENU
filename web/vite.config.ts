import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          antd: ["antd", "@ant-design/icons"],
          refine: ["@refinedev/core", "@refinedev/antd", "@refinedev/react-router"],
          react: ["react", "react-dom", "react-router"],
        },
      },
    },
  },
});
