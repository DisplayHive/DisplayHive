import type { TreeNode } from 'primevue/treenode'

// The checkbox tree the Im-/Export page builds from a manifest (the server's list
// of exportable / importable items, grouped by entity type).

// Entity types, in the same order/keys as application/admin/importexport/registry.py.
export const ENTITY_TYPE_LABELS: Record<string, string> = {
  screens: 'Screens',
  screengroups: 'Screen Groups',
  gradients: 'Gradients',
  contentcontainers: 'Content Containers',
  designs: 'Designs',
  layouts: 'Layouts',
  contenttypes: 'Content Types',
  content_elements: 'Content Elements',
  media: 'Media',
  devices: 'Devices',
}
export const ENTITY_TYPE_ORDER = Object.keys(ENTITY_TYPE_LABELS)

export type ManifestItem = { uuid: string; id: number; label: string; conflict?: boolean }
export type Manifest = Record<string, ManifestItem[]>
export type SelectionKeys = Record<string, { checked: boolean; partialChecked: boolean }>

export function buildTree(manifest: Manifest, itemKeyPrefix = ''): TreeNode[] {
  return ENTITY_TYPE_ORDER.filter((key) => (manifest[key] || []).length > 0).map((key) => ({
    key: `${itemKeyPrefix}type:${key}`,
    label: `${ENTITY_TYPE_LABELS[key]} (${(manifest[key] || []).length})`,
    selectable: true,
    children: (manifest[key] || []).map((item) => ({
      key: `${itemKeyPrefix}item:${key}:${item.uuid}`,
      label: item.label,
      selectable: true,
      data: { typeKey: key, uuid: item.uuid, conflict: !!item.conflict },
    })),
  }))
}

export function allCheckedKeys(tree: TreeNode[]): SelectionKeys {
  const keys: SelectionKeys = {}
  for (const node of tree) {
    keys[node.key as string] = { checked: true, partialChecked: false }
    for (const child of node.children || []) {
      keys[child.key as string] = { checked: true, partialChecked: false }
    }
  }
  return keys
}

/** Collect {typeKey: [uuid, ...]} for every leaf item currently checked. */
export function selectionFromKeys(tree: TreeNode[], keys: SelectionKeys): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const node of tree) {
    for (const child of node.children || []) {
      const typeKey = (child.data as { typeKey: string })?.typeKey
      if (!typeKey) continue
      if (!out[typeKey]) out[typeKey] = []
      if (keys[child.key as string]?.checked) {
        out[typeKey].push((child.data as { uuid: string }).uuid)
      }
    }
  }
  return out
}
