# Admin Panel Styleguide

The visual language of `frontends/admin` — colors, type scale, spacing, card
patterns, and icon usage — extracted from the Dashboard
(`src/views/DashboardView.vue`), which is the most visually complete page in
the app. New views should reuse these rather than inventing new values.

A companion rendered reference (live swatches, both themes side by side) is
linked from the PR that introduced this page — regenerate it with the same
values below if the palette changes.

## Color

### Status colors

Used consistently for "is this thing okay" signaling — stat card top
borders, detail-line text, warning icons.

| Role | Token | Fallback |
|---|---|---|
| OK / positive | `--p-green-500` | `#22c55e` |
| Warning | `--p-amber-400` (icons/detail text) / `--p-amber-500` (larger icons) | `#f59e0b` |
| Primary accent (stat values) | `--p-primary-color` | `#667eea` |

### Text

Always use the semantic pair below, never a hardcoded gray — see
[Dark mode](#dark-mode) for why.

| Role | Token | Light fallback |
|---|---|---|
| Body text | `--p-text-color` | `#111827` |
| Muted / secondary text | `--p-text-muted-color` | `#6b7280` (also seen as `#9ca3af` for lighter-weight muted text) |

### Link-card accent colors

Each `link-card--<name>` variant pairs a left-border color with a matching
icon color (see `.link-card--web`, `.link-card--github`, etc. in
`DashboardView.vue`). Pick a new, distinct hue for a new card rather than
reusing one — there are currently 16 in use spanning cyan, slate, blue,
purple, red, amber, yellow, green, teal, orange, and indigo. Keep border and
icon color identical for a given variant.

## Typography scale

| Size | Used for |
|---|---|
| `0.75rem` | Stat detail sub-line, link-card arrow icon |
| `0.8rem` | Community section heading, demo-hint footer description |
| `0.85rem` | Stat label (uppercase, `letter-spacing: 0.04em`), welcome text, support intro (italic) |
| `0.9rem` | Link-card title (`font-weight: 600`), welcome headline body |
| `1rem` | Card icon size baseline |
| `1.15rem` | Welcome headline (`font-weight: 600`) |
| `1.4rem` | Link-card icon, demo-hint icon (`1.4rem` / `1.4rem`) |
| `1.75rem` | Page `<h1>` (set globally in `App.vue`) |
| `2.75rem` | Stat card big number (`font-weight: 700`) |

Uppercase + letter-spacing (`text-transform: uppercase; letter-spacing:
0.04–0.08em`) marks a section label (`.stat-label`, `.community-heading`) —
don't apply it to anything else.

## Spacing scale

Gaps and padding are drawn from a small set: `0.25rem, 0.4rem, 0.5rem,
0.75rem, 1rem, 1.25rem, 1.5rem`. The page-level container
(`.dashboard`) uses `gap: 1.5rem` between major sections; cards use
`gap: 0.75rem–1rem` internally.

## Border radius

| Radius | Used for |
|---|---|
| `0.65rem` | Link cards |
| `0.75rem` | Stat cards |
| `8px` | Smaller inline elements (e.g. tag clouds elsewhere in the app) |

## Utility classes

A small set of reusable spacing/layout utilities in `assets/views.css`,
named after their rem value (quarters of `1rem`) rather than a full
utility-CSS framework:

| Class | Value |
|---|---|
| `.w-full` | `width: 100%` |
| `.flex-1` | `flex: 1` |
| `.d-block` | `display: block` |
| `.mt-1` / `.mt-2` / `.mt-4` | `margin-top: 0.25rem / 0.5rem / 1rem` |
| `.mb-4` | `margin-bottom: 1rem` |
| `.ml-1` / `.ml-2` | `margin-left: 0.25rem / 0.5rem` |
| `.mr-1` | `margin-right: 0.25rem` |
| `.thin-progress` | `height: 6px` (a compact `<ProgressBar>`) |
| `.empty-state--compact` | `1.5rem` icon on an `.empty-state`, for a smaller nested placeholder (e.g. a `<DataTable>`'s own "no rows" message) next to a page-level `.empty-state` that still wants the full `3rem` icon |

**Never reach for an inline `style="..."` for a value one of these already
covers.** Note `.ml-2`/`flex`/`align-items-center`/`gap-2`-style bare class
names appear in a couple of older templates (`DesignsView.vue`,
`SettingsView.vue`) as leftover PrimeFlex-convention class names — this app
does **not** ship PrimeFlex, so `flex`/`align-items-center`/`gap-2` are
still no-ops today (`.ml-2` now works, since it's one of the utilities
above). Don't assume a bare utility-looking class name actually does
anything — check it's defined in `views.css` first, the same way you'd
check a CSS variable is a real PrimeVue token before trusting it.

Genuinely one-off styling (used exactly once, unlikely to recur) still
gets a real named class in the component's own `<style>` block — not
`style="..."` — so it can inherit `--p-*` tokens and dark-mode overrides
the way every other class in this document does. `<Column style="width:
...">` is the one standing exception: PrimeVue's `Column` has no dedicated
width prop, so `style` is its documented, idiomatic way to size a column,
same as the handful of `display: none` hidden `<input type="file">`
elements that follow a universal web convention.

## Card patterns

Two patterns, both built on PrimeVue's `<Card>`:

1. **Plain Card** (welcome card, stat cards) — no custom `background`, so it
   inherits PrimeVue's own theme-aware surface. This is what makes
   `.dark-mode` work automatically for `background`/text — see below for why
   it still needed an explicit override.
2. **Custom link card** (`.link-card`, plain `<a>`/`<div>`, not a `<Card>`) —
   icon + title/subtitle + trailing arrow, `border-left: 4px` in the
   variant's accent color, `box-shadow` + `translateY(-2px)` on hover.
   `.link-card--static` variants (no href) suppress the hover effect
   entirely (`cursor: default`, no shadow/transform).

`:deep(.p-card-body)` is the standard way to override a `<Card>`'s internal
padding from a scoped `<style>` block (see `.stat-card :deep(.p-card-body)`,
`.welcome-card :deep(.p-card-body)`).

### Card headline structure

A `<Card>`'s `#title` slot follows one of two shapes, both using global
classes from `assets/views.css`:

```html
<!-- Title text + icon, no actions -->
<template #title>
  <div class="card-header">
    <i class="pi pi-send card-header-icon" />
    <span>Telegram</span>
  </div>
</template>

<!-- Title text + icon, with actions -->
<template #title>
  <div class="card-header">
    <div class="card-header-title">
      <i class="pi pi-tags card-header-icon" />
      <span>Magic Tags</span>
    </div>
    <div class="header-actions">
      <Button ... />
    </div>
  </div>
</template>

<!-- Actions only, no title text -->
<template #title>
  <div class="card-header">
    <div class="header-actions">
      <Button ... />
    </div>
  </div>
</template>
```

- **Every headline that has an icon uses `.card-header-icon`** (DH yellow,
  `#facc15` — the same fixed brand accent as `App.vue`'s page-header icon,
  not a semantic token, since it's a brand mark meant to look identical in
  both themes). Never color a headline icon any other way.
- Icon + title text together need the `.card-header-title` wrapper *only*
  when `.header-actions` sits in the same row — `.card-header`'s
  `justify-content: space-between` needs exactly two flex children (title
  group, actions group) or the icon and title end up pulled to opposite
  ends of the row. With no actions, icon and `<span>` can sit directly in
  `.card-header` as-is.
- When a card's title is actions-only (no headline text at all — most list
  pages' "New X" / refresh buttons), add a scoped
  `.card-header { justify-content: flex-end; }` override — otherwise the
  single remaining child collapses to the start instead of staying
  right-aligned.

## Tables

### Filter placement

A `<DataTable>`'s search/status filters go in its own `#header` slot,
wrapped in `.dt-header`/`.dt-left`/`.dt-right` (global classes, also in
`assets/views.css`) — never as a standalone `<div>` placed before the
`<DataTable>` in the Card's `#content`. The table's own `#header` slot
renders inside PrimeVue's `.p-datatable-header`, which carries a themed
panel background; a filter row placed outside it has no such background and
looks visually disconnected from the table (and, before the
`.dark-mode .p-card` fix above existed, could look outright blank against
the page).

```html
<DataTable ...>
  <template #header>
    <div class="dt-header">
      <div class="dt-left">
        <InputText v-model="filterText" placeholder="Filter…" class="filter-input" />
      </div>
      <div class="dt-right">
        <!-- status filter Tags, if any -->
      </div>
    </div>
  </template>
  <Column ... />
</DataTable>
```

A grid of custom cards (not a `<DataTable>` at all — e.g. `MediaView.vue`'s
media grid) has no equivalent slot; its filter row sits directly in the
Card's `#content` and relies on the Card's own background instead.

When `.dt-right` holds more than one filter group (e.g. `ScreensView.vue`'s
Windowed/Fullscreen and Online/Offline `Tag` pairs), lay the groups out
horizontally with a wider gap between groups than within one
(`.dt-right { gap: 1.5rem }`, each `.filter-row` keeping its own `gap:
0.5rem`) — don't stack them vertically with `flex-direction: column`, and
put the more specific/situational filter group (Windowed/Fullscreen) to the
left of the more general one (Online/Offline).

A raw hand-built `<table>` (not a PrimeVue `<DataTable>` — e.g.
`MatrixView.vue`'s screen/screengroup assignment grid) still has to source
every color from the same semantic tokens as everywhere else: header row
background, cell borders, hover state, and body text all need
`--p-content-*`/`--p-text-*` (plus a `.dark-mode` override on the header
row's `--p-surface-100`, same shape as the Alerting/Pretalx matrix tables)
— it doesn't get a pass just because it isn't a `<DataTable>`.

### Striped-row background

PrimeVue's `stripedRows` alternate-row background is a fixed ramp token
(`--p-surface-950` in dark mode) with no relation at all to whatever
background the surrounding `<Card>` actually uses — so once the Card got
its own explicit `--p-surface-800` (see [Card-vs-page
contrast](#card-vs-page-contrast) below), the striped rows stopped
matching it. Pinned globally in `App.vue`:

```css
.dark-mode .p-datatable {
  --p-datatable-row-striped-background: var(--p-surface-800, #1e293b);
}
```

If the Card background override above ever changes, update this value to
match — the two are meant to always be identical.

### Standard props

The dominant convention, followed by most list pages (`ContentTypesView`,
`DesignsView`, `DevicesView`, `LayoutsView`, `MagicTagsView`, `ScreenGroupsView`,
`ScreensView`, `PretalxView`, `AlertingView`):

```html
<DataTable
  :value="filteredItems"
  :loading="store.loading"
  sortField="name"
  :sortOrder="1"
  stripedRows
  size="small"
  :paginator="filteredItems.length > 10"
  :rows="10"
>
```

- **Always** `stripedRows` and `size="small"` — a table without either reads
  as a different, heavier component next to every other list page.
- Paginate only past 10 rows (`:paginator="items.length > 10"`, `:rows="10"`)
  — a short list doesn't need pager UI taking up space.
- `sortField`/`:sortOrder="1"` on the natural default column (usually
  `name`) when the data supports sorting.

A pre-ordered hierarchical tree (e.g. `UsersView.vue`'s groups table,
indented by `depth`) is the one legitimate exception to pagination/sorting:
adding `sortField`/`:paginator` would re-sort it alphabetically or split
parent/child rows across pages. It still gets `stripedRows`/`size="small"`
for visual consistency, just not the data-ordering props.

## Modals

Every modal is a PrimeVue `<Dialog>` with `modal` and a `#header` slot —
never the plain `header="..."` string prop. Width is the object-binding
`px` form:

```html
<Dialog v-model:visible="showX" modal :style="{ width: '400px' }">
  <template #header>
    <div class="dialog-title">
      <span class="dialog-title-icon-badge"><i class="pi pi-pencil dialog-title-icon"></i></span>
      <span class="p-dialog-title">Do Thing</span>
    </div>
  </template>
  ...
</Dialog>
```

- **Every Dialog headline carries an icon**, styled with the
  `.dialog-title`/`.dialog-title-icon-badge`/`.dialog-title-icon` global
  classes (`assets/views.css`) — a small circular black badge holding a
  DH-yellow icon, the same treatment as the page-level `<h1>` headline
  (`App.vue`'s `.page-title-icon-badge`/`.page-title-icon`), just sized
  down for a dialog header bar. Keep the `<span class="p-dialog-title">`
  wrapper around the text — that's PrimeVue's own title class, so it still
  gets the theme's font-size/weight even though the plain `header` prop is
  gone.
- Pick an icon that matches the dialog's subject, reusing a page's own icon
  where one already exists (e.g. Pretalx dialogs use `pi-link`/`pi-database`
  even though the page card uses `pi-calendar` — close enough association,
  distinct enough to not be confusing) rather than inventing a new one for
  every single dialog.
- Never a plain `style="width: ...rem"` string or `min()` CSS function, and
  never `:modal="true"` in place of the bare `modal` shorthand. Rough width
  bands in current use: **~400–420px** for a single confirm/copy field or
  compact form, **~480–600px** for a form with a handful of fields,
  **~600px+** only for something genuinely wide (gradient management, icon
  license list, rights matrices).

### Close button

PrimeVue's Dialog close button is an unstyled default `<Button>` — no
`text` variant applied — so on its own it renders with full button chrome
(a visible border/background circle) unlike every other icon-only button in
the app, which is `text`/`outlined` and borderless until hovered. The
chrome isn't a plain `border` — plain `border: none` alone didn't remove
it, since PrimeVue renders it as a `box-shadow`/`outline` combination — so
the override needs `!important` on all three to reliably win regardless of
layer/specificity. Fixed globally in `App.vue` rather than per-dialog, with
a subtle `box-shadow` kept on `:focus-visible` only, for keyboard
accessibility:

```css
.p-dialog-close-button {
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
  background: transparent !important;
}
.p-dialog-close-button:hover {
  background: var(--p-content-hover-background, rgba(0, 0, 0, 0.06)) !important;
}
.p-dialog-close-button:focus-visible {
  box-shadow: 0 0 0 2px var(--p-content-hover-background, rgba(0, 0, 0, 0.1)) !important;
}
```

## Icon usage

PrimeIcons (`pi pi-*`) only. **Verify the icon name exists** —
`pi-bug` was used on this page and silently rendered nothing because it
isn't a real PrimeIcons name; there's no automated check for this, so a
typo'd or invented icon name fails silently instead of erroring. Check
`node_modules/primeicons/primeicons.css` for the canonical list before using
a name you haven't used elsewhere in the app.

## Dark mode

Dark mode is a user preference (`AdminUser.preferences.theme`,
`light`/`dark`/`system`), applied as a `.dark-mode` class on `<html>` by
`composables/useTheme.ts`, which activates PrimeVue's aura preset dark
palette (`darkModeSelector: '.dark-mode'` in `main.ts`).

### Semantic tokens vs. the fixed ramp

This is the rule that matters most and the one behind nearly every
dark-mode contrast bug found in this app:

- **Semantic tokens** — `--p-text-color`, `--p-text-muted-color`,
  `--p-content-background`, `--p-content-border-color`,
  `--p-content-hover-background`, `--p-primary-color`, etc. — are redefined
  by the aura preset when `.dark-mode` is active. Safe to use anywhere;
  they adapt.
- **Ramp tokens** — `--p-surface-0` through `--p-surface-950`,
  `--p-amber-50` through `--p-amber-900` (and the equivalent for every other
  hue) — are a **fixed** palette. `--p-surface-0` is always white,
  `--p-amber-50` is always pale amber, in both themes. They do not adapt.
- **Legacy PrimeVue v3 tokens** — `--surface-b`, `--surface-d`,
  `--surface-border`, `--text-color`, `--text-color-secondary`, and any
  other unprefixed (no `p-`) theming variable — **don't exist at all** in
  the v4 aura preset this app uses. `var(--text-color-secondary)` with no
  fallback doesn't just fail to adapt, it resolves to nothing, so the
  property computes to its initial value. Always use the `--p-*` name; if
  you're not sure of the mapping, `--text-color` → `--p-text-color`,
  `--text-color-secondary` → `--p-text-muted-color`, `--surface-border` /
  `--surface-d` → `--p-content-border-color`, `--surface-b` →
  `--p-content-background`.
- **`--p-surface-border` is the same trap wearing a `p-` prefix** — it
  looks exactly like a real v4 token (matches the naming convention, was
  used 16 times across 5 files with plausible-looking fallbacks) but was
  never a real PrimeVue variable, so it always silently fell through to its
  fallback color and never adapted. The bright white borders/dividers on
  the Edit Content page and elsewhere were this, not the numbered ramp
  tokens. Use `--p-content-border-color` instead — it's the real one.

**Never use a ramp token as a literal `background` (or anything else meant
to flip with the theme) without an explicit `.dark-mode` override next to
it.** The bug pattern seen repeatedly on this page: a card's `background`
was pinned to `var(--p-surface-0, #fff)` while its text used a semantic
token that *did* go light in dark mode — light text on a background that
never changed, i.e. unreadable. Fix is always the same shape:

```css
.dark-mode .some-card {
  background: var(--p-surface-800, #1e293b);
  border-color: var(--p-surface-700, #334155);
}
```

Ramp tokens are still the right tool *inside* a `.dark-mode` block — using
`--p-surface-800`/`-700` there gives you PrimeVue's own dark-appropriate
grays instead of inventing new hex values.

### Card-vs-page contrast

A plain `<Card>` with no custom background can still end up nearly invisible
against the page: PrimeVue's dark card background and the page's own dark
background (`body { background-color: #14181c }` in `App.vue`'s
`.dark-mode` block) land very close to each other. This isn't a per-page
quirk — every page in the app uses `<Card>` — so it's fixed **once,
globally**, in `App.vue`'s unscoped `<style>` block:

```css
.dark-mode .p-card {
  background: var(--p-surface-800, #1e293b);
  border: 1px solid var(--p-surface-700, #334155);
}
```

Don't re-add a per-page `.dark-mode .some-card { background: ... }` rule
just to fix plain-card invisibility — the global rule already covers it. A
page-specific override is still correct when the card needs something the
global rule doesn't give it (e.g. `DashboardView.vue`'s `.stat-card` uses a
`box-shadow` ring instead of a `border` to avoid clobbering its colored
`border-top` status indicator — see below); scoped styles' higher
specificity lets it win over the global rule automatically.

When adding a border to a `.dark-mode` override, check whether the element
already owns a meaningful `border-*` shorthand (e.g. `.stat-card`'s colored
`border-top` status indicator). A plain `border` in the override needs
higher specificity than the sub-class that sets the status color
(`.stat-card--ok`/`--warn`) and will silently wipe it out. Use
`box-shadow: inset 0 0 0 1px ...` instead when you need a defining edge
without touching an existing border side.

### Form control borders

Not every "too bright" border is a broken token — PrimeVue's own dark
colorScheme sets `formField.borderColor` to `surface.600` (a medium-light
gray), which is a legitimate default but noticeably lighter than the
`surface-700`/`-800` borders used everywhere else in this app (Card,
buttons, dialogs). Rather than a `.dark-mode` mismatch bug, this is a
deliberate override to keep the whole app's border weight consistent, done
once globally in `App.vue` across every form control's rendered border
(not a CSS variable rename, since the exact intermediate variable name
isn't guaranteed to exist per-component — a direct `border-color` on each
component's real root class is more reliable):

```css
.dark-mode .p-inputtext,
.dark-mode .p-select,
.dark-mode .p-textarea,
.dark-mode .p-inputnumber-input,
.dark-mode .p-checkbox-box,
.dark-mode .p-datepicker-input,
.dark-mode .p-password-input,
.dark-mode .p-multiselect,
.dark-mode .p-togglebutton {
  border-color: var(--p-surface-700, #334155);
}
```

Note `Password`/`DatePicker`/`InputNumber` don't have their own bordered
input class — they wrap an inner `InputText`, exposed as
`p-password-input`/`p-datepicker-input`/`p-inputnumber-input`
respectively (confirmed from each component's `style/index.mjs`, not
guessed — this codebase already has one scare from a plausible-looking but
nonexistent class/variable name).

### Field labels

The global `.field label` rule (`assets/views.css`) had no `color` at all,
so it inherited the ambient (bright, near-white in dark mode) text color —
while five files (`AlertingView`, `UsersView`, `PretalxView`,
`LayoutCanvasEditor`, `SettingsView`) had their own local override to
`--p-text-muted-color` that made their labels correctly dim. Since most
pages rely on the global rule rather than a local override, most of the
app's field labels were the brighter, un-muted version — the global rule
now matches what those five files already did. The same gap (bold label
selector, no `color`) recurred in half a dozen other one-off classes
(`.icon-picker-label`, `.mode-label`, `.preset-panel-label`, etc.) — when
adding a new label-like class, always pair `font-weight: 600` with
`color: var(--p-text-muted-color, ...)`; a bold label with no explicit
color is the same gap.

### Exhaustive sweep

The individual bug reports above were all found by targeted greps for
specific token names, which is why they surfaced one file at a time over
several rounds instead of all at once. The reliable way to check a file
(or the whole app) in one pass is to grep for *any* hardcoded hex used in a
border/background, not just the ones already known to be wrong:

```
grep -rnE "(border(-color|-top|-bottom|-left|-right)?|background(-color)?)\s*:\s*[^;]*#[0-9a-fA-F]{3,6}\b" src/ --include="*.vue" | grep -vE "var\(--p-"
```

Triage each hit against [What to leave alone](#what-to-leave-alone) below
— most real apps have a mix of both, and the goal isn't zero hits, it's
zero *unpaired* ones. Concretely fixed in this pass: `ScreensView.vue`'s
`.screengroup-checkboxes` border, `LoginView.vue`'s page background (no
`.dark-mode` pairing existed at all — `useTheme()` runs before login, so
the login screen needs one same as every other page), `ScreenGroupsView.vue`'s
section title/divider/list-item/pagination colors, `MediaView.vue`'s
upload drop-zone border and card action-row divider, `ContentEditView.vue`'s
two remaining `border-top: 1px solid #ddd` dividers plus a whole
pale-amber warning banner whose text colors needed inverting (not just
swapping the background) for dark-mode contrast, and `MediaPickerDialog.vue`
duplicating the same unfixed image-picker pattern already fixed in
`FieldValueEditor.vue` — the same widget copy-pasted into two files needs
the same fix applied twice.

### What to leave alone

Not every fixed color is a bug. Examples of intentionally fixed colors:
status colors (`.validity-icon.valid/.invalid`, `--p-green-500`/
`--p-amber-400`), the canvas editor's rectangle/handle colors in
`LayoutCanvasEditor.vue` (an overlay UI drawn on top of an arbitrary
design, like the Dashboard's link-card accents), a label badge
`background: rgba(255,255,255,0.7)` in the same file (deliberately always-
light so it stays readable over any rect color), hover-only accent tints
that already follow the app's `--p-primary-50`-style convention,
`PretalxView.vue`'s `.cache-json` block and `LoggerView.vue`'s
`.log-container` (both intentionally always-dark terminal/code panels, not
app chrome — the log-level left-border colors inside it are a fixed status
palette, same idea as the validity icons), `DesignsView.vue`'s `.var-chip`
(a code-style variable-tag badge with its own fixed dark-navy background +
light-blue text, meant to look like a code chip regardless of theme), and
`ContentTable.vue`/`DesignsView.vue`'s always-black screen/effect preview
boxes (simulating a physical screen, not a themed surface). None of these
pair a color that swaps with the theme against a background that doesn't —
the actual bug condition — so none needs a change.

When adding new UI, run the [exhaustive sweep](#exhaustive-sweep) above
before shipping, or at minimum:
```
grep -n "var(--p-surface-[0-9]\|var(--p-amber-[0-9]" your-file.vue
```
Any hit used as a `background`/`border` with no matching `.dark-mode`
override nearby is the same bug.

---

*This styleguide was generated with the assistance of Claude AI.*
