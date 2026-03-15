import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",  
        changeOrigin: true,
        secure: false,
        ws: true,
        configure: (proxy) => {
          proxy.on("error", (err) => {
            console.log("proxy error", err)
          })
          proxy.on("proxyReq", (proxyReq, req) => {
            console.log("➡️  Proxy Request:", req.method, req.url)
          })
          proxy.on("proxyRes", (proxyRes, req) => {
            console.log("⬅️  Proxy Response:", proxyRes.statusCode, req.url)
          })
        }
      }
    }
  }
})