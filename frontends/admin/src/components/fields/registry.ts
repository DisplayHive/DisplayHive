import type { Component } from 'vue'
import TextField from './TextField.vue'
import { fieldHandlerDef } from '../../plugins/registry'

interface FieldEditorEntry {
  component: Component
  /** Props that make one component serve several handlers. */
  props?: Record<string, unknown>
}

const FALLBACK: FieldEditorEntry = { component: TextField }

/**
 * The editor of a field handler: the one its plugin registered (see plugins/registry.ts). A handler
 * nobody provides (its plugin is off, or not loaded yet) gets the one-line text editor, so the value
 * stays visible and is not lost.
 */
export const fieldEditorFor = (handler: string): FieldEditorEntry => {
  const def = fieldHandlerDef(handler)
  return def ? { component: def.editor, props: def.editorProps } : FALLBACK
}
