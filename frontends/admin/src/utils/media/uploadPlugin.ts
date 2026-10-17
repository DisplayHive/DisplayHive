/**
 * Upload a plugin (a ZIP file) to POST /admin/api/plugins/upload — see application/admin/plugins/routes.py.
 * Same approach as uploadIconLibrary.ts (XMLHttpRequest, for the progress).
 */

/** Must match MAX_DOWNLOAD_BYTES in application/plugins/installer.py. */
export const MAX_PLUGIN_UPLOAD_BYTES = 64 * 1024 * 1024

export type PluginUploadResult = { success: true; id: string; version: string } | { success: false; error: string }

export const uploadPlugin = (
  file: File,
  sha256: string,
  authHeader: Record<string, string>,
  onProgress?: (loaded: number, total: number) => void,
): Promise<PluginUploadResult> => {
  if (file.size > MAX_PLUGIN_UPLOAD_BYTES) {
    return Promise.resolve({ success: false, error: `File too large (max ${MAX_PLUGIN_UPLOAD_BYTES / 1024 / 1024} MB)` })
  }
  const body = new FormData()
  body.append('file', file, file.name)
  if (sha256) body.append('sha256', sha256)

  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/admin/api/plugins/upload')
    for (const [key, value] of Object.entries(authHeader)) xhr.setRequestHeader(key, value)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded, e.total)
    }
    xhr.onload = () => {
      let result: { success?: boolean; error?: string; id?: string; version?: string } = {}
      try {
        result = JSON.parse(xhr.responseText)
      } catch {
        // e.g. a reverse proxy's own error page
      }
      if (xhr.status >= 200 && xhr.status < 300 && result.success) resolve({ success: true, id: result.id ?? '', version: result.version ?? '' })
      else if (xhr.status === 413) resolve({ success: false, error: result.error || 'File too large for the server (check the reverse proxy limit)' })
      else resolve({ success: false, error: result.error || `Upload failed (HTTP ${xhr.status})` })
    }
    xhr.onerror = () => resolve({ success: false, error: 'Network error during upload' })
    xhr.send(body)
  })
}
