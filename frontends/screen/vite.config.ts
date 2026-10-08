import { defineConfig } from "vite";
import path from "path";
import { execSync } from "node:child_process";

// The Docker build has no .git: the revision comes in as an environment variable.
const gitCommit = (() => {
  if (process.env.DISPLAYHIVE_REVISION) return process.env.DISPLAYHIVE_REVISION.trim().slice(0, 7);
  try {
    return execSync("git rev-parse --short HEAD", { encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
})();

export default defineConfig({
  // Set the base URL so generated chunks are referenced under /dist/screen/
  base: "/dist/screen/",
  root: ".",
  define: {
    __GIT_COMMIT__: JSON.stringify(gitCommit),
  },
  server: {
    // Pinned to a port distinct from admin's (5173, see
    // frontends/admin/vite.config.ts) so the two dev servers can never
    // collide — Playwright's webServer config specifically expects admin
    // on 5173 and would otherwise silently reuse whichever one got there first.
    port: 5174,
    strictPort: true,
  },
  build: {
    outDir: "../../dist/screen",
    // Clear the output directory on build to avoid stale artifacts
    // (previously `false` which left old bundles like `screenleg.js`).
    emptyOutDir: true,
    rollupOptions: {
      input: {
        // `screen` bundle is built from `ts/screen` + `ts/common`
        screen: path.resolve(__dirname, "ts/screen.ts"),
      },
      output: {
        // Keep entry filenames stable so templates can reference entry bundles.
        // Restore hashing for chunks and assets for proper cache-busting.
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
