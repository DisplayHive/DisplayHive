/**
 * Playwright global teardown — Option B cleanup.
 *
 * Reads the port-map written by global-setup.ts, kills all spawned Flask
 * worker processes, and removes the per-worker SQLite DB files.
 */

import * as fs from 'node:fs'
import { PORT_MAP_PATH } from './global-setup.js'

export default async function globalTeardown() {
  if (!fs.existsSync(PORT_MAP_PATH)) {
    console.log('[global-teardown] No port map found — nothing to clean up.')
    return
  }

  const raw = fs.readFileSync(PORT_MAP_PATH, 'utf-8')
  const { pids, workerCount } = JSON.parse(raw) as {
    pids: (number | null)[]
    workerCount: number
  }

  // Kill each Flask worker process
  for (const pid of pids) {
    if (!pid) continue
    try {
      process.kill(pid, 'SIGTERM')
      console.log(`[global-teardown] Sent SIGTERM to PID ${pid}`)
    } catch (err: any) {
      // ESRCH = process already dead; ignore silently
      if (err?.code !== 'ESRCH') {
        console.warn(`[global-teardown] Could not kill PID ${pid}:`, err.message)
      }
    }
  }

  // Remove per-worker DB files
  for (let i = 0; i < workerCount; i++) {
    const dbPath = `/tmp/displayhive_test_${i}.db`
    if (fs.existsSync(dbPath)) {
      fs.unlinkSync(dbPath)
      console.log(`[global-teardown] Removed ${dbPath}`)
    }
  }

  // Remove the port map itself
  fs.unlinkSync(PORT_MAP_PATH)
  console.log('[global-teardown] Cleaned up.')
}
