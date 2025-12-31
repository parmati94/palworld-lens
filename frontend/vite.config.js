import { defineConfig } from 'vite';

export default defineConfig({
  root: './',
  publicDir: 'public',  // Copies public/* to dist/* (preserving structure)
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: './index.html',
        login: './login.html'
      }
    },
    minify: 'esbuild',
    sourcemap: false
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
});
