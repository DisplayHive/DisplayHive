/**
 * Playwright global setup — Option B: per-worker Flask process with isolated DB file.
 *
 * Spawns WORKER_COUNT Flask processes, each on its own port (BASE_PORT + workerIndex)
 * and pointed at its own fresh SQLite file (/tmp/displayhive_test_<N>.db).
 *
 * Writes a JSON port-map to PORT_MAP_PATH so fixtures can look up the correct
 * backend URL for each Playwright worker index.
 *
 * Environment variables (all optional):
 *   PW_WORKER_COUNT   — number of parallel workers (default: 1 — tests run serially)
 *   PW_BASE_PORT      — first backend port (default: 5001)
 */

import { spawn, ChildProcess } from 'node:child_process'
import * as fs from 'node:fs'
import * as path from 'node:path'
import * as https from 'node:https'
import * as http from 'node:http'
import { TEST_ADMIN_USERNAME, TEST_ADMIN_PASSWORD } from './testAdminCredentials.js'

export const PORT_MAP_PATH = '/tmp/displayhive-test-portmap.json'

const WORKER_COUNT = parseInt(process.env.PW_WORKER_COUNT || '1', 10)
const BASE_PORT = parseInt(process.env.PW_BASE_PORT || '5001', 10)
// Repo root is two levels above testing/e2e/
const REPO_ROOT = path.resolve(import.meta.dirname, '..', '..')
// Python executable — can be overridden if nix-shell provides a specific path
const PYTHON = process.env.TEST_PYTHON || 'python'

/** Poll a URL until it responds or the timeout expires. */
function waitForUrl(url: string, timeoutMs = 30_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs
    const proto = url.startsWith('https') ? https : http
    const attempt = () => {
      proto
        .get(url, { rejectUnauthorized: false }, (res) => {
          // Any HTTP response means the server is up (even 4xx/5xx)
          res.resume()
          resolve()
        })
        .on('error', () => {
          if (Date.now() >= deadline) {
            reject(new Error(`Timed out waiting for ${url}`))
          } else {
            setTimeout(attempt, 500)
          }
        })
    }
    attempt()
  })
}

/**
 * If a previous run was killed without reaching global-teardown (Ctrl-C, CI
 * timeout, ...), its Flask worker(s) keep running and squat the ports this
 * run wants to bind. The next global-setup's waitForUrl() only checks that
 * *something* answers on the port, so it would happily accept the stale
 * process — which then has its DB file deleted out from under it below,
 * turning every request into a 500. Proactively kill anything left over
 * from a prior interrupted run before spawning fresh workers.
 */
function killLeftoverWorkersFromPreviousRun() {
  if (!fs.existsSync(PORT_MAP_PATH)) return
  try {
    const raw = fs.readFileSync(PORT_MAP_PATH, 'utf-8')
    const { pids } = JSON.parse(raw) as { pids: (number | null)[] }
    for (const pid of pids) {
      if (!pid) continue
      try {
        process.kill(pid, 'SIGKILL')
        console.log(`[global-setup] Killed leftover worker PID ${pid} from a previous run`)
      } catch (err: any) {
        if (err?.code !== 'ESRCH') {
          console.warn(`[global-setup] Could not kill leftover PID ${pid}:`, err.message)
        }
      }
    }
  } catch (err: any) {
    console.warn('[global-setup] Failed to parse stale port map, ignoring:', err.message)
  } finally {
    fs.unlinkSync(PORT_MAP_PATH)
  }
}

export default async function globalSetup() {
  const portMap: Record<number, number> = {}
  const processes: ChildProcess[] = []

  killLeftoverWorkersFromPreviousRun()

  console.log(
    `[global-setup] Starting ${WORKER_COUNT} Flask workers (ports ${BASE_PORT}–${BASE_PORT + WORKER_COUNT - 1})`,
  )

  for (let i = 0; i < WORKER_COUNT; i++) {
    const port = BASE_PORT + i
    const dbPath = `/tmp/displayhive_test_${i}.db`
    // Per-worker DATA_DIR (media, previews, import staging — see
    // application/paths.py), so test uploads never land in the checkout.
    const dataDir = `/tmp/displayhive_test_${i}_data`

    // Remove stale DB / data from a previous run so every test starts clean
    if (fs.existsSync(dbPath)) {
      fs.unlinkSync(dbPath)
      console.log(`[global-setup] Removed stale DB ${dbPath}`)
    }
    fs.rmSync(dataDir, { recursive: true, force: true })

    const env: NodeJS.ProcessEnv = {
      ...process.env,
      TEST_DB_PATH: dbPath,
      DATA_DIR: dataDir,
      FLASK_PORT: String(port),
      // Pin the first-run bootstrap admin account so fixtures.ts can log in
      // with known credentials against this worker's isolated database.
      ADMIN_BOOTSTRAP_USERNAME: TEST_ADMIN_USERNAME,
      ADMIN_BOOTSTRAP_PASSWORD: TEST_ADMIN_PASSWORD,
    }

    const proc = spawn(PYTHON, ['app.py'], {
      cwd: REPO_ROOT,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      // Detach so the process survives if the Playwright runner is interrupted;
      // global-teardown is responsible for killing it cleanly.
      detached: false,
    })

    proc.stdout?.on('data', (d: Buffer) => {
      process.stdout.write(`[flask-worker-${i}] ${d}`)
    })
    proc.stderr?.on('data', (d: Buffer) => {
      process.stderr.write(`[flask-worker-${i}] ${d}`)
    })
    proc.on('error', (err) => {
      console.error(`[global-setup] Worker ${i} failed to start:`, err.message)
    })

    portMap[i] = port
    processes.push(proc)
  }

  // Persist the port map so global-teardown can kill the right PIDs and
  // fixtures can resolve the correct backend URL.
  const mapData = {
    portMap,
    pids: processes.map((p) => p.pid),
    workerCount: WORKER_COUNT,
    basePort: BASE_PORT,
  }
  fs.writeFileSync(PORT_MAP_PATH, JSON.stringify(mapData, null, 2))
  console.log(`[global-setup] Port map written to ${PORT_MAP_PATH}`)

  // Wait for all workers to be reachable before handing control back to Playwright
  await Promise.all(
    processes.map((_, i) => {
      const port = BASE_PORT + i
      const url = `http://localhost:${port}/`
      console.log(`[global-setup] Waiting for worker ${i} at ${url}`)
      return waitForUrl(url, 30_000).then(() =>
        console.log(`[global-setup] Worker ${i} is up on port ${port}`),
      )
    }),
  )

  console.log('[global-setup] All Flask workers ready.')
}
