import { defineConfig } from 'vite';
import handlebars from 'vite-plugin-handlebars';
import { resolve } from 'path';

export default defineConfig({
  root: './',
  publicDir: 'public',  // Copies public/* to dist/* (preserving structure)
  plugins: [
    handlebars({
      partialDirectory: [
        resolve(__dirname, 'partials'),
        resolve(__dirname, 'partials/tabs')
      ],
    }),
  ],
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
