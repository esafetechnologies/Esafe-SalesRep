// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "Esafe-SalesRep" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Build straight into the Frappe app's public folder with fixed filenames so
// esafe_salesrep/www/pos.html can reference /assets/esafe_salesrep/pos/pos.js and pos.css.
export default defineConfig({
  plugins: [vue()],
  base: '/assets/esafe_salesrep/pos/',
  build: {
    outDir: '../esafe_salesrep/public/pos',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'pos.js',
        // A language file (locales/<code>.js) is its own chunk. The hash gives
        // it a new name whenever its text changes, so neither the browser's
        // cache of /assets nor the service worker keeps an old translation.
        chunkFileNames: 'chunk-[name]-[hash].js',
        assetFileNames: (assetInfo) =>
          assetInfo.name && assetInfo.name.endsWith('.css') ? 'pos.css' : 'asset-[name][extname]',
      },
    },
  },
  server: {
    port: 8080,
    proxy: {
      '^/(api|assets|files)': {
        target: 'http://localhost:8000', // local bench during development
        changeOrigin: true,
      },
    },
  },
})
