import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1000, // Aumenta limite a 1MB (default 500KB)
    rollupOptions: {
      output: {
        manualChunks: {
          // Separa le librerie grandi in chunks dedicati
          vendor: ['react', 'react-dom'],
          charts: ['recharts']
        }
      }
    }
  }
})
