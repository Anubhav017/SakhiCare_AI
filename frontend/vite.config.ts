import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const { BACKEND_URL } = loadEnv(mode, ".", "BACKEND_");
  return {
    server: {
      proxy: {
        "/backend-api": {
          target: BACKEND_URL || "http://127.0.0.1:8000",
          changeOrigin: true,
          rewrite: path => path.replace(/^\/backend-api(?=\/|$)/, ""),
        },
      },
    },
  };
});
