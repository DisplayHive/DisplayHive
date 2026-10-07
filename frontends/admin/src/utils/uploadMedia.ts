/**
 * Upload one media file to POST /admin/api/media/upload (multipart, streamed
 * to disk server-side — see application/admin/media/routes.py).
 *
 * XMLHttpRequest rather than fetch(): it's the only browser API that reports
 * upload progress.
 */

/** Must match MAX_FILE_SIZE in application/admin/media/storage.py. */
export const MAX_MEDIA_UPLOAD_BYTES = 50 * 1024 * 1024

export type MediaUploadFields = { folder?: string; title?: string; tags?: string }

export type MediaUploadResult = { success: true; id: number; filename: string } | { success: false; error: string }

export const uploadMedia = (
  file: File,
  fields: MediaUploadFields,
  authHeader: Record<string, string>,
  onProgress?: (loaded: number, total: number) => void,
): Promise<MediaUploadResult> => {
  if (file.size > MAX_MEDIA_UPLOAD_BYTES) {
    // Don't send 50+ MB just to be told so.
    return Promise.resolve({ success: false, error: `File too large (max ${MAX_MEDIA_UPLOAD_BYTES / 1024 / 1024} MB)` })
  }

  const body = new FormData()
  body.append('file', file, file.name)
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined) body.append(key, value)
  }

  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/admin/api/media/upload')
    for (const [key, value] of Object.entries(authHeader)) xhr.setRequestHeader(key, value)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded, e.total)
    }
    xhr.onload = () => {
      let result: Partial<MediaUploadResult> & { error?: string } = {}
      try {
        result = JSON.parse(xhr.responseText)
      } catch {
        // e.g. a reverse proxy's own HTML error page
      }
      if (xhr.status >= 200 && xhr.status < 300 && result.success) {
        resolve(result as MediaUploadResult)
      } else if (xhr.status === 413) {
        resolve({ success: false, error: result.error || 'File too large for the server (check the reverse proxy limit)' })
      } else if (xhr.status === 401) {
        resolve({ success: false, error: result.error || 'Not allowed — session expired or missing upload right' })
      } else {
        resolve({ success: false, error: result.error || `Upload failed (HTTP ${xhr.status})` })
      }
    }
    xhr.onerror = () => resolve({ success: false, error: 'Network error during upload' })
    xhr.send(body)
  })
}
