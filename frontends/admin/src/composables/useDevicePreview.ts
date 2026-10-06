// Allow overriding screen URL via Vite env `VITE_SCREEN_URL`. Otherwise:
// - In dev (`npm run dev`), the admin SPA is served by its own Vite dev
//   server (e.g. :5173), which is NOT where Flask renders the screen/
//   handles the devicekey socket auth — default to the Flask backend URL
//   instead (same fallback used for the socket connection).
// - In production, admin + screen are both served by Flask on the same
//   origin, so `window.location.origin` is correct.
export const getScreenBaseUrl = (): string => {
  const env = import.meta.env || {}
  return (
    (env.VITE_SCREEN_URL as string) ||
    (env.DEV ? (env.VITE_BACKEND_URL as string) || (env.VITE_SOCKET_URL as string) || 'http://localhost:5000' : window.location.origin)
  )
}

/**
 * Opens a new tab with a read-only, impersonated live view of whatever the
 * given device key is currently showing — the same connection the device
 * itself uses, just flagged `impersonate=true` so the backend skips
 * presence/online-state tracking for it (see
 * application/admin/devices/connection.py).
 */
export const openDevicePreview = (devicekey: string) => {
  const base = getScreenBaseUrl()
  const separator = base.includes('?') ? '&' : '?'
  const url = `${base}${separator}impersonate=true&devicekey=${encodeURIComponent(devicekey)}`
  window.open(url, '_blank', 'noopener')
}
