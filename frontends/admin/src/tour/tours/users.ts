import type { TourDefinition } from '../types'

// If the person clicked "Next" instead of Cancel/Save, the Add User
// dialog is still open — but the table underneath (the next step's
// target) is already mounted regardless of the dialog, so waitForElement
// would find it immediately and highlight it *behind* the still-open
// dialog instead of skipping. Clicking Cancel here closes it exactly
// like a real dismissal would. No-op if the dialog's already closed.
const closeAccountDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="users-account-cancel"]')?.click()
}

// The "Add Group" step needs the Groups tab active and any lingering
// per-user rights dialog out of the way first — both are idempotent
// (clicking an already-active tab, or an already-closed dialog's close
// button, is a safe no-op), so this always runs rather than only
// defending against a missed advanceOnClick.
const prepareGroupsTab = () => {
  document.querySelector<HTMLElement>('[data-tour="users-rights-dialog-close"]')?.click()
  document.querySelector<HTMLElement>('[data-tour="users-tab-groups"]')?.click()
}

// Same reasoning as closeAccountDialogIfStillOpen, for the Add/Rename
// Group dialog.
const closeGroupDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="users-group-cancel"]')?.click()
}

// If the person clicked "Next" instead of the real "Manage rights"
// button, the per-user rights dialog never opened, so this step's target
// (inside it) wouldn't exist. Clicking the button here opens it for real
// either way; re-opening an already-open dialog just reloads the same
// account's data, so this is safe to run unconditionally.
const ensureUserRightsDialogOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="users-row-manage-rights"]')?.click()
}

// Same reasoning as ensureUserRightsDialogOpen, for the group "Edit
// rights" button and its dialog — this also gates the tour's last step,
// so without this, clicking only "Next" the whole way through would
// silently end the tour instead of reaching "Exit Tour".
const ensureGroupRightsDialogOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="users-row-edit-rights"]')?.click()
}

export const usersTour: TourDefinition = {
  id: 'users',
  title: 'Users & Rights',
  description: 'Admin accounts, permission groups, and how group and per-user rights combine.',
  icon: 'pi pi-users',
  category: 'admin',
  steps: [
    {
      route: '/users',
      selector: '[data-tour="users-page"]',
      title: 'Users & Rights',
      description:
        'Accounts are the people who can log in; Groups define what they can do. An account\'s permissions come from the groups it belongs to, with optional per-account overrides.',
      side: 'bottom',
    },
    {
      route: '/users',
      selector: '[data-tour="users-add-user"]',
      title: 'Add a user',
      description: 'Create a new admin account here.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="users-account-fields"]',
      title: 'Username & password',
      description: 'A unique username and an initial password — the account can change its own password later.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="users-account-cancel"]',
      title: 'Save or Cancel',
      description: 'Save creates the account; Cancel discards without creating anything.',
      side: 'top',
    },
    {
      route: '/users',
      selector: '[data-tour="users-table"]',
      title: 'Your accounts',
      description:
        'Each row shows whether the account is active, which groups it belongs to, and when it last logged in — deactivating an account blocks login without deleting it.',
      side: 'top',
      before: closeAccountDialogIfStillOpen,
    },
    {
      selector: '[data-tour="users-row-manage-rights"]',
      title: 'Manage rights',
      description: 'Opens this specific account\'s group membership and any per-account overrides.',
      side: 'top',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="users-rights-group-membership"]',
      title: 'Group membership & overrides',
      description:
        'Pick which groups this account belongs to — its rights are the union of all of them. Below this (not shown here) you can also allow or deny individual rights per account; deny always wins, even over a group that grants it.',
      side: 'bottom',
      before: ensureUserRightsDialogOpen,
    },
    {
      selector: '[data-tour="users-add-group"]',
      title: 'Add a group',
      description:
        'Groups can be nested — a subgroup inherits everything its parent grants, on top of whatever it\'s given directly.',
      side: 'bottom',
      advanceOnClick: true,
      before: prepareGroupsTab,
    },
    {
      selector: '[data-tour="users-group-fields"]',
      title: 'Name & parent group',
      description: 'Optionally nest it under an existing group to inherit that group\'s rights automatically.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="users-group-cancel"]',
      title: 'Save or Cancel',
      description: 'Save creates the group; Cancel discards without creating anything.',
      side: 'top',
    },
    {
      route: '/users',
      selector: '[data-tour="users-groups-table"]',
      title: 'Your groups',
      description:
        'Indentation shows the nesting; "Superadmin" groups always hold every right and can\'t be edited here.',
      side: 'top',
      before: closeGroupDialogIfStillOpen,
    },
    {
      selector: '[data-tour="users-row-edit-rights"]',
      title: 'Edit rights',
      description: 'Opens this group\'s full rights matrix.',
      side: 'top',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="users-rights-matrix"]',
      title: 'The rights matrix',
      description:
        'Toggle individual rights, or use "All"/"None" per category — rights already granted by a parent group show as "inherited" and stay in effect even when left unchecked here.',
      side: 'bottom',
      before: ensureGroupRightsDialogOpen,
    },
    {
      selector: '[data-tour="users-rights-matrix-close"]',
      title: 'Close',
      description: 'Changes here apply immediately to every account in this group (and its subgroups) — no separate save step.',
      side: 'top',
    },
  ],
}
