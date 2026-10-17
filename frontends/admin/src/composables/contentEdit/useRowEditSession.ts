import { shallowReactive, type Ref } from 'vue'

/**
 * One row of the content list is edited in several places — the fields (in its preview) and the
 * delivery settings — but saved with one button. Each place registers here for its row; the row's
 * Save / Discard (components/content/RowSaveBar.vue) save and discard all of them together.
 */
export interface RowEditPart {
  dirty: Readonly<Ref<boolean>>
  saving: Readonly<Ref<boolean>>
  /** Write the changes; `true` when they are saved. Says nothing to the person on success: the bar does. */
  save: () => Promise<boolean>
  discard: () => void
}

// Shallow: the parts hold refs that must stay refs.
const sessions = shallowReactive(new Map<number, RowEditPart[]>())

/** Register a part of the row's editing; the returned function takes it back (call it when the part goes away). */
export function registerRowEdit(rowId: number, part: RowEditPart): () => void {
  const parts = sessions.get(rowId) ?? []
  parts.push(part)
  sessions.set(rowId, parts)
  return () => {
    const rest = (sessions.get(rowId) ?? []).filter((p) => p !== part)
    if (rest.length) sessions.set(rowId, rest)
    else sessions.delete(rowId)
  }
}

export function useRowEditState(rowId: number) {
  const parts = () => sessions.get(rowId) ?? []
  return {
    dirty: () => parts().some((p) => p.dirty.value),
    saving: () => parts().some((p) => p.saving.value),
    /** Saves every part that has changes; `false` if one failed (the others are still saved). */
    save: async () => {
      let ok = true
      for (const part of parts().filter((p) => p.dirty.value)) ok = (await part.save()) && ok
      return ok
    },
    discard: () => parts().forEach((p) => p.discard()),
  }
}

// A page showing the rows wants to read them again after a save. The component that saved can be gone by
// then (the page may rebuild the row while the save is under way), so this does not go through its events.
const savedListeners = new Set<() => void>()

/** Call `callback` whenever a row was saved (also partly); returns the function that stops it. */
export function onRowSaved(callback: () => void): () => void {
  savedListeners.add(callback)
  return () => savedListeners.delete(callback)
}

export function notifyRowSaved(): void {
  savedListeners.forEach((callback) => callback())
}
