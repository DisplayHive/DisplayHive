import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRightsStore } from '../stores/rights'

type Can = (right: string) => boolean

interface NavLeaf {
  label: string
  icon: string
  path: string
  /** Who sees the entry. */
  allowed: (can: Can) => boolean
}

interface NavGroup {
  label: string
  icon: string
  items: NavLeaf[]
}

const page = (right: string) => (can: Can) => can(right)

const CONTENT: NavLeaf[] = [
  { label: 'Content', icon: 'pi pi-box', path: '/content', allowed: page('content.page') },
  { label: 'Screens', icon: 'pi pi-window-maximize', path: '/screens', allowed: page('screens.page') },
  { label: 'Screen Groups', icon: 'pi pi-clone', path: '/screengroups', allowed: page('screengroups.page') },
  { label: 'Media', icon: 'pi pi-images', path: '/media', allowed: page('media.page') },
]

const ADMIN_GROUPS: NavGroup[] = [
  {
    label: 'Devices',
    icon: 'pi pi-desktop',
    items: [
      { label: 'Devices', icon: 'pi pi-desktop', path: '/devices', allowed: page('device.page') },
      { label: 'Matrix', icon: 'pi pi-th-large', path: '/matrix', allowed: (can) => can('screens.page') && can('screengroups.page') },
    ],
  },
  {
    label: 'Content Structure',
    icon: 'pi pi-sitemap',
    items: [
      { label: 'Content Types', icon: 'pi pi-file', path: '/contenttypes', allowed: page('contenttypes.page') },
      { label: 'Designs', icon: 'pi pi-palette', path: '/designs', allowed: page('designs.page') },
      { label: 'Layouts', icon: 'pi pi-th-large', path: '/layouts', allowed: page('layouts.page') },
    ],
  },
  {
    label: 'Integrations',
    icon: 'pi pi-share-alt',
    items: [{ label: 'Pretalx', icon: 'pi pi-calendar', path: '/pretalx', allowed: page('pretalx.page') }],
  },
  {
    label: 'System',
    icon: 'pi pi-server',
    items: [
      { label: 'Im-/Export', icon: 'pi pi-database', path: '/importexport', allowed: page('importexport.page') },
      { label: 'Settings', icon: 'pi pi-cog', path: '/settings', allowed: page('settings.page') },
      { label: 'Alerting', icon: 'pi pi-bell', path: '/alerting', allowed: page('alerting.page') },
      { label: 'Logger', icon: 'pi pi-list', path: '/logger', allowed: page('logger.page') },
    ],
  },
]

/** Shown in the Admin menu next to the groups, not inside one. */
const USERS: NavLeaf = {
  label: 'Users & Rights',
  icon: 'pi pi-users',
  path: '/users',
  allowed: (can) => can('users.page') || can('rights.page'),
}

/** Title and icon of the page header, by route name. */
const PAGES: Record<string, { title: string; icon: string }> = {
  home: { title: 'Dashboard', icon: 'pi pi-home' },
  demo: { title: 'Demo Mode', icon: 'pi pi-sparkles' },
  tour: { title: 'Guided Tour', icon: 'pi pi-compass' },
  devices: { title: 'Adopted Devices', icon: 'pi pi-desktop' },
  screens: { title: 'Screens', icon: 'pi pi-window-maximize' },
  screengroups: { title: 'Screen Groups', icon: 'pi pi-clone' },
  content: { title: 'Content', icon: 'pi pi-box' },
  'content-new': { title: 'Create Content', icon: 'pi pi-plus' },
  'content-edit': { title: 'Edit Content', icon: 'pi pi-pencil' },
  'content-copy': { title: 'Copy Content', icon: 'pi pi-copy' },
  contenttypes: { title: 'Content Types', icon: 'pi pi-file' },
  designs: { title: 'Designs', icon: 'pi pi-palette' },
  layouts: { title: 'Layouts', icon: 'pi pi-th-large' },
  'layout-new': { title: 'New Layout', icon: 'pi pi-plus' },
  'layout-edit': { title: 'Edit Layout', icon: 'pi pi-pencil' },
  settings: { title: 'Settings', icon: 'pi pi-cog' },
  logger: { title: 'Logger', icon: 'pi pi-list' },
  media: { title: 'Media', icon: 'pi pi-images' },
  matrix: { title: 'Matrix', icon: 'pi pi-th-large' },
  importexport: { title: 'Im-/Export', icon: 'pi pi-database' },
  alerting: { title: 'Alerting', icon: 'pi pi-bell' },
  pretalx: { title: 'Pretalx', icon: 'pi pi-calendar' },
  users: { title: 'Users & Rights', icon: 'pi pi-users' },
}

/**
 * The top menu (a PrimeVue Menubar model, filtered by the person's rights) and the title and
 * icon of the current page. Add a page: one line in CONTENT/ADMIN_GROUPS and one in PAGES.
 */
export function useAdminNavigation() {
  const router = useRouter()
  const route = useRoute()
  const rights = useRightsStore()

  const visible = (leaves: NavLeaf[]) =>
    leaves
      .filter((leaf) => leaf.allowed(rights.can))
      .map((leaf) => ({ label: leaf.label, icon: leaf.icon, command: () => router.push(leaf.path) }))

  const menuItems = computed(() => {
    const content = visible(CONTENT)
    const groups = ADMIN_GROUPS.map((group) => ({ ...group, items: visible(group.items) }))
      .filter((group) => group.items.length)
      .map(({ label, icon, items }) => ({ label, icon, items }))
    const admin = [...groups, ...visible([USERS])]
    return [
      { label: 'Dashboard', icon: 'pi pi-home', command: () => router.push('/') },
      ...(content.length ? [{ label: 'Content', icon: 'pi pi-folder', items: content }] : []),
      ...(admin.length ? [{ label: 'Admin', icon: 'pi pi-cog', items: admin }] : []),
    ]
  })

  /** Every page the person may open, flat — for the command palette. */
  const pages = computed(() => {
    const leaves = [...CONTENT, ...ADMIN_GROUPS.flatMap((g) => g.items), USERS]
    return [
      { label: 'Dashboard', icon: 'pi pi-home', path: '/' },
      ...leaves.filter((leaf) => leaf.allowed(rights.can)).map(({ label, icon, path }) => ({ label, icon, path })),
    ]
  })

  const pageTitle = computed(() => PAGES[route.name as string]?.title || 'DisplayHive Admin')
  const pageIcon = computed(() => PAGES[route.name as string]?.icon || '')

  return { menuItems, pages, pageTitle, pageIcon }
}
