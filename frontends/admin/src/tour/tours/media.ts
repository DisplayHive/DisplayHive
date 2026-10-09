import type { TourDefinition } from '../types'

// If the person clicked "Next" instead of Cancel/Upload, the Upload Media
// dialog is still open — but the grid underneath (the next step's target)
// is already mounted regardless of the dialog, so waitForElement would
// find it immediately and highlight it *behind* the still-open dialog
// instead of skipping. Clicking Cancel here closes it exactly like a real
// dismissal would. No-op if the dialog's already closed.
const closeUploadDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="media-upload-cancel"]')?.click()
}

// Same reasoning, for the per-item Edit dialog.
const closeEditDialogIfStillOpen = () => {
  document.querySelector<HTMLElement>('[data-tour="media-edit-cancel"]')?.click()
}

export const mediaTour: TourDefinition = {
  id: 'media',
  title: 'Media',
  description: 'Upload, tag, and reuse images and videos across your content.',
  icon: 'pi pi-images',
  category: 'user',
  steps: [
    {
      route: '/media',
      selector: '[data-tour="media-page"]',
      title: 'Media',
      description: 'Every image and video you can use in content lives here, in one shared library.',
      side: 'bottom',
    },
    {
      route: '/media',
      selector: '[data-tour="media-upload"]',
      title: 'Upload',
      description: 'Click "Upload" to add new images or videos to the library.',
      side: 'bottom',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="media-upload-dropzone"]',
      title: 'Drag & drop',
      description: 'Drag files in, or click to browse — JPEG and PNG only, up to 50 MB each.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="media-upload-cancel"]',
      title: 'Upload',
      description: 'Once your files are queued below, click "Upload" to add them to the library.',
      side: 'top',
    },
    {
      selector: '[data-tour="media-grid"]',
      title: 'Your media library',
      description: 'Every uploaded file shows up here as a card, with its preview, filename, and tags.',
      side: 'top',
      before: closeUploadDialogIfStillOpen,
    },
    {
      selector: '[data-tour="media-search-field"]',
      title: 'Search',
      description: 'Filter the library by title or filename here.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="media-tag-cloud"]',
      title: 'Filter by tag',
      description: 'Click any tag to narrow the library to files carrying it — click again, or "Clear tag selection", to remove the filter.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="media-item-url-copy"]',
      title: 'Copy its URL',
      description: 'Copies this file\'s direct URL — handy for pasting into a rich-text field or anywhere outside DisplayHive\'s own content types.',
      side: 'top',
    },
    {
      selector: '[data-tour="media-item-edit"]',
      title: 'Edit',
      description: 'Open a file to rename it or change its tags.',
      side: 'top',
      advanceOnClick: true,
    },
    {
      selector: '[data-tour="media-edit-title-field"]',
      title: 'Title',
      description: 'A display name for this file — shown in the library and in field pickers, not necessarily its original filename.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="media-edit-tags"]',
      title: 'Tags',
      description: 'Click an available tag on the right to assign it, or an assigned tag on the left to remove it — type a new one below and press Enter to create it on the fly.',
      side: 'top',
    },
    {
      selector: '[data-tour="media-item-delete"]',
      title: 'Delete',
      description: 'Permanently removes this file from the library — anything already using it keeps showing it until replaced.',
      side: 'top',
      before: closeEditDialogIfStillOpen,
    },
    {
      selector: '[data-tour="page-more-actions"]',
      title: 'More actions',
      description:
        'Sync Previews compares every file against its generated preview and regenerates any that are missing — useful after a bulk import or a storage hiccup. Refresh re-reads the library.',
      side: 'bottom',
    },
  ],
}
