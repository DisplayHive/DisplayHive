import { fieldHandlerDef, fieldHandlerOptions } from '../../plugins/registry'

/** Field handler options for a container's default content ("None" first: it is optional). */
export const DEFAULT_FIELD_HANDLER_OPTIONS = fieldHandlerOptions

/**
 * The starting value of `default_content` after switching a container's handler: handlers that
 * keep structured data (packed as JSON into default_content) get an empty one of their shape,
 * plain-text handlers an empty string. The handler's plugin says which (`blankDefault`).
 */
export const defaultContentFor = (handler: string): string => fieldHandlerDef(handler)?.blankDefault?.() ?? ''
