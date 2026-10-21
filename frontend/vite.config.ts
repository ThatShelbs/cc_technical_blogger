/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const API = process.env.PROSEFERNO_API ?? 'http://127.0.0.1:8732'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { '/api': { target: API, changeOrigin: true } },
  },
  // Served locally from disk, so one larger bundle is fine.
  build: { chunkSizeWarningLimit: 1200 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
})
