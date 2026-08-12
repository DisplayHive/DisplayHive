import { fileURLToPath, URL } from 'node:url'
import { execSync } from 'node:child_process'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

const gitCommit = (() => {
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim()
  } catch {
    return 'unknown'
  }
})()

// Backend URL: used both for the dev-server proxy and as the socket URL injected
// into the client bundle when VITE_SOCKET_URL is not already set.
// Override with: VITE_BACKEND_URL=http://myserver:5000 npm run dev
const backendUrl =
  process.env.VITE_BACKEND_URL || process.env.VITE_SOCKET_URL || 'http://localhost:5000'

// https://vite.dev/config/
export default defineConfig({
  base: '/admin/',
  define: {
    __GIT_COMMIT__: JSON.stringify(gitCommit),
  },
  build: {
    outDir: '../../dist/admin',
    emptyOutDir: true,
  },
  plugins: [
    vue(),
    vueDevTools(),
    {
      name: 'redirect-admin-trailing-slash',
      configureServer(server: any) {
        server.middlewares.use((req: any, res: any, next: any) => {
          try {
            if (
              req.method === 'GET' &&
              req.url &&
              (req.url === '/admin' || req.url.startsWith('/admin?'))
            ) {
              res.statusCode = 301
              res.setHeader('Location', '/admin/')
              res.end()
              return
            }
          } catch (e) {
            // ignore errors and continue
          }
          next()
        })
      },
    },
  ],
  server: {
    // Pinned so Playwright's `reuseExistingServer` (testing/playwright.config.ts)
    // always finds *this* dev server on 5173, not the screen frontend's (which
    // must use a different port — see frontends/screen/vite.config.ts).
    port: 5173,
    strictPort: true,
    proxy: {
      // Forward Socket.IO requests to the Flask backend.
      // This allows the Vite dev server (used by Playwright) to act as a
      // transparent proxy so the SPA can reach the real Socket.IO endpoint
      // without needing CORS or a separate origin in tests.
      '/socket.io': {
        target: backendUrl,
        changeOrigin: true,
        ws: true, // also proxy WebSocket upgrade requests
      },
      // Forward the DB export/import REST endpoints to the Flask backend.
      // These match by prefix, so they must be the exact literal endpoint
      // paths — NOT a shorter prefix like `/admin/import`, which would also
      // match (and hijack) the `/admin/importexport` SPA page route.
      '/admin/export/tree': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/admin/export/download': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/admin/import/preview': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/admin/import/confirm': {
        target: backendUrl,
        changeOrigin: true,
      },
      // Forward the demo-content REST endpoints, same rationale as above —
      // must not be a shorter prefix like `/admin/demo`, which would also
      // match (and hijack) a future `/admin/demo...` SPA page route.
      '/admin/demo/list': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/admin/demo/import': {
        target: backendUrl,
        changeOrigin: true,
      },
      // Forward the admin auth REST endpoints (login/session-check) to the
      // Flask backend, same rationale as export/download and import/upload above.
      '/admin/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      // Forward Flask's static file route (uploaded media, media previews,
      // logos) to the backend. Unlike the /admin/* entries above this is a
      // safe prefix match — no SPA route starts with /static, so there's no
      // risk of shadowing a page route.
      '/static': {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
