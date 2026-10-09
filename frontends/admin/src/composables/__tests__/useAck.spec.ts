import { beforeEach, describe, expect, it, vi } from 'vitest'

const toastAdd = vi.fn()
const emitWithAck = vi.fn()

vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: toastAdd }) }))
vi.mock('../useSocket', () => ({ useSocket: () => ({ emitWithAck }) }))

import { useAck } from '../useAck'

beforeEach(() => {
  toastAdd.mockReset()
  emitWithAck.mockReset()
})

describe('useAck().request', () => {
  it('returns the answer and shows the success text', async () => {
    emitWithAck.mockResolvedValue({ success: true, id: 7 })
    const ack = await useAck().request<{ success: boolean; id: number }>('ev', { a: 1 }, { success: 'Saved' })
    expect(ack?.id).toBe(7)
    expect(emitWithAck).toHaveBeenCalledWith('ev', { a: 1 })
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success', detail: 'Saved' }))
  })

  it('shows no toast on success without a text', async () => {
    emitWithAck.mockResolvedValue({ success: true })
    expect(await useAck().request('ev')).toEqual({ success: true })
    expect(toastAdd).not.toHaveBeenCalled()
  })

  it('builds the success text from the answer', async () => {
    emitWithAck.mockResolvedValue({ success: true, total: 3 })
    await useAck().request<{ success: boolean; total: number }>('ev', undefined, { success: (a) => `${a.total} done` })
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ detail: '3 done' }))
  })

  it("returns null and shows the server's reason on failure", async () => {
    emitWithAck.mockResolvedValue({ success: false, error: 'Group not found' })
    expect(await useAck().request('ev')).toBeNull()
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', detail: 'Group not found' }))
  })

  it('falls back to the given text, then to a generic one', async () => {
    emitWithAck.mockResolvedValue({ success: false })
    await useAck().request('ev', undefined, { error: 'Could not delete' })
    expect(toastAdd).toHaveBeenLastCalledWith(expect.objectContaining({ detail: 'Could not delete' }))
    emitWithAck.mockResolvedValue(undefined)
    await useAck().request('ev')
    expect(toastAdd).toHaveBeenLastCalledWith(expect.objectContaining({ detail: 'Request failed' }))
  })

  it('treats a disconnected socket as a failure', async () => {
    emitWithAck.mockRejectedValue(new Error('Socket not connected'))
    expect(await useAck().request('ev')).toBeNull()
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
  })

  it('hands the message to onError instead of showing a toast', async () => {
    emitWithAck.mockResolvedValue({ success: false, error: 'No token configured' })
    const onError = vi.fn()
    expect(await useAck().request('ev', undefined, { onError })).toBeNull()
    expect(onError).toHaveBeenCalledWith('No token configured')
    expect(toastAdd).not.toHaveBeenCalled()
  })
})
