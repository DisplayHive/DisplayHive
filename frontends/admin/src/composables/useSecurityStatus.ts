import { computed, ref } from 'vue'
import { useSocket } from './useSocket'

export type SecurityStatus = {
  secret_key_is_default?: boolean
  cors_wildcard?: boolean
  sqlite_in_use?: boolean
  debug_enabled?: boolean
  // What the server runs (application/version.py).
  version?: string
  revision?: string
  // Only sent to holders of settings.page (application/admin/devices/connection.py).
  legacy_data_paths?: { kind: string; path: string }[]
  data_dir?: string | null
  deployment?: string
}

export type SecurityIssue = { title: string; detail: string }

/**
 * What the server says about itself after connecting (`security_status`): its version and
 * revision, and the configuration problems the banners at the top of the page show.
 */
export function useSecurityStatus() {
  const { on } = useSocket()
  const status = ref<SecurityStatus>({})

  on('displayhive:system:stc:security_status', (data: SecurityStatus) => {
    status.value = data || {}
  })

  // The server's version, once it has told us; the build-time commit until then.
  const version = computed(() => status.value.version ?? '…')
  const revision = computed(() => status.value.revision ?? __GIT_COMMIT__)

  // Insecure defaults (SECRET_KEY, CORS, SQLite, debugger) are the norm in
  // local dev and would otherwise show on every load — only surface these
  // banners in a built/production bundle (import.meta.env.DEV is false there).
  // The two that actually weaken security are shown as a prominent block of their
  // own (SECRET_KEY, CORS); the rest stay slim one-line banners below it.
  const criticalIssues = computed<SecurityIssue[]>(() => {
    const issues: SecurityIssue[] = []
    if (import.meta.env.DEV) return issues
    if (status.value.secret_key_is_default) {
      issues.push({
        title: 'SECRET_KEY is the insecure default.',
        detail:
          'Admin login tokens are signed with this key, so anyone who knows the default can forge a token and sign in as any admin. Set the SECRET_KEY environment variable to a long random value and restart.',
      })
    }
    if (status.value.cors_wildcard) {
      issues.push({
        title: 'CORS allows any origin ("*").',
        detail:
          'Any website may then make cross-origin requests to the API. Set PUBLIC_URL to the address of this instance, for example https://signage.example.com, and restart. (CORS_ALLOWED_ORIGINS overrides it if you need several origins.)',
      })
    }
    return issues
  })

  const warnings = computed(() => {
    const list: string[] = []
    if (import.meta.env.DEV) return list
    if (status.value.sqlite_in_use) {
      list.push(
        'DATABASE_URL is unset — the server is running on a local SQLite file. Set DATABASE_URL to a PostgreSQL connection string before deploying to production.',
      )
    }
    if (status.value.debug_enabled) {
      list.push(
        'The Werkzeug debugger is enabled (FLASK_DEBUG). This allows arbitrary code execution if exposed to the network — disable it (FLASK_DEBUG=0) before deploying to production.',
      )
    }
    return list
  })

  return { status, version, revision, criticalIssues, warnings }
}
