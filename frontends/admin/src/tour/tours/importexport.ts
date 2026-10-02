import type { TourDefinition } from '../types'

export const importExportTour: TourDefinition = {
  id: 'importexport',
  title: 'Import / Export',
  description: 'Back up your configuration before risky changes, and restore it (or part of it) later.',
  icon: 'pi pi-database',
  category: 'admin',
  steps: [
    {
      route: '/importexport',
      selector: '[data-tour="importexport-page"]',
      title: 'Import / Export',
      description:
        'Not a full system backup — it covers display content (screens, designs, layouts, content, media, devices) and general app settings. Admin accounts, API keys, and log files are never included.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="importexport-export-tree"]',
      title: 'Pick what to export',
      description: 'By type, or individual items within a type — dependencies (e.g. a Content Type\'s Layout) are pulled in automatically.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="importexport-download-button"]',
      title: 'Download',
      description: 'Downloads a ZIP containing db.json and a media/ folder — keep this somewhere safe before a risky change.',
      side: 'top',
    },
    {
      selector: '[data-tour="importexport-file-picker"]',
      title: 'Select a file to import',
      description: 'A previously exported ZIP or JSON file — legacy exports from older versions are also accepted.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="importexport-import-tree"]',
      title: 'What\'s in the file',
      description:
        'Choose what to bring in, item by item. An "exists" tag marks something that would conflict with what\'s already here.',
      side: 'bottom',
    },
    {
      selector: '[data-tour="importexport-mode-row"]',
      title: 'Import mode',
      description: 'Merge adds the selection alongside existing data; Reset wipes the database and media folder first, then imports.',
      side: 'top',
    },
    {
      selector: '[data-tour="importexport-conflict-row"]',
      title: 'Conflicting items',
      description:
        'Set a default (Overwrite or Skip) for everything that already exists locally, then fine-tune individual items with the dropdown next to each conflicting row above.',
      side: 'top',
    },
    {
      selector: '[data-tour="importexport-import-actions"]',
      title: 'Import',
      description: 'In Reset mode this permanently overwrites the entire database and media folder — there\'s no undo, so export a backup first.',
      side: 'top',
    },
    {
      // The four steps above only appear once a real file has actually
      // been picked and previewed (something a tour can't fake without
      // popping a real OS file dialog) — they're skipped otherwise. This
      // closing step targets the page itself rather than anything
      // file-dependent, so the tour always has a real last step to reach
      // regardless of whether a file was selected along the way.
      selector: '[data-tour="importexport-page"]',
      title: 'That\'s the whole picture',
      description:
        'Export before any risky change — especially before a Reset-mode import, which can\'t be undone.',
      side: 'bottom',
    },
  ],
}
