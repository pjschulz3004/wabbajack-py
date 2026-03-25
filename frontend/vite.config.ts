import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:6969',
      '/ws': { target: 'ws://localhost:6969', ws: true },
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
