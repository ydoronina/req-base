import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    manifest: true,
    outDir: 'static/assets',
    rollupOptions: { input: 'web/app.js' }
  }
})
