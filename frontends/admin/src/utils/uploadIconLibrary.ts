/**
 * Upload an icon library (a ZIP or TAR file of SVG icons) to POST /admin/api/icons/upload — see
 * application/admin/icons/routes.py. Same approach as uploadMedia.ts (XMLHttpRequest, for the progress).
 */

/** Must match MAX_DOWNLOAD_BYTES in application/icon_libraries.py. */
export const MAX_ICON_LIBRARY_UPLOAD_BYTES = 250 * 1024 * 1024

export type IconLibraryUploadResult = { success: true } | { success: false; error: string }

export const uploadIconLibrary = (
  file: File,
  fields: { id: string; label: string; license: string },
  authHeader: Record<string, string>,
  onProgress?: (loaded: number, total: number) => void,
): Promise<IconLibraryUploadResult> => {
  if (file.size > MAX_ICON_LIBRARY_UPLOAD_BYTES) {
    return Promise.resolve({ success: false, error: `File too large (max ${MAX_ICON_LIBRARY_UPLOAD_BYTES / 1024 / 1024} MB)` })
  }
  const body = new FormData()
  body.append('file', file, file.name)
  for (const [key, value] of Object.entries(fields)) body.append(key, value)

  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/admin/api/icons/upload')
    for (const [key, value] of Object.entries(authHeader)) xhr.setRequestHeader(key, value)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded, e.total)
    }
    xhr.onload = () => {
      let result: { success?: boolean; error?: string } = {}
      try {
        result = JSON.parse(xhr.responseText)
      } catch {
        // e.g. a reverse proxy's own error page
      }
      if (xhr.status >= 200 && xhr.status < 300 && result.success) resolve({ success: true })
      else if (xhr.status === 413) resolve({ success: false, error: result.error || 'File too large for the server (check the reverse proxy limit)' })
      else resolve({ success: false, error: result.error || `Upload failed (HTTP ${xhr.status})` })
    }
    xhr.onerror = () => resolve({ success: false, error: 'Network error during upload' })
    xhr.send(body)
  })
}
