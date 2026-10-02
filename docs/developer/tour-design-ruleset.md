# Guided Tour design ruleset

A checklist for writing a new mini-tour under `frontends/admin/src/tour/`.
It restates and expands on the "Adding a new mini-tour" section of the root
[`CLAUDE.md`](../../CLAUDE.md) — read that first for the full mechanics
(file layout, `TourDefinition`, the content package). This page is the
rule-by-rule checklist to apply while writing one, with real examples
pulled from the existing tours (`contentTypes.ts`, `createEditContent.ts`,
`layoutUsage.ts`).

## 1. Placement

- **Category is about who, not what page.** `category: 'user'` = everyday
  content/screen work a daily editor does. `category: 'admin'` = setup
  tasks — layouts, content types, designs. If a tour mixes both (e.g. it
  starts on an admin page but teaches a content-editor workflow), classify
  by the audience the tour is *for*, not the first route it visits.
- One `TourDefinition` per file in `tours/`, registered in `tours/index.ts`'s
  `TOURS` array. Don't bundle unrelated workflows into one tour just to
  avoid a new file — a tour should teach one coherent task end to end.

## 2. Targeting elements

- **Default to a dedicated `data-tour="..."` attribute**, added directly on
  the element in its view/component. Never target an existing CSS class or
  DOM structure on the assumption it'll stay put — a redesign or refactor
  changing it breaks the tour silently (no compile error, just a step that
  times out and skips itself at runtime).
- The only exception is a class that is already a deliberate, load-bearing
  structural hook rather than incidental styling — e.g.
  `.content-edit-preview`, `.tag-fields-section`, `.action-buttons`. Use
  judgement, but when in doubt, add the attribute instead.
- Name `data-tour` values predictably: static UI chrome gets a flat name
  (`content-new`, `layouts-table`, `contenttypes-filter`); anything
  row/card-level still carries its row's id (`` `contenttype-card-${ct.id}` ``)
  for debugging/uniqueness, but a tour step must never match it by that
  specific id — see §3.
- If a step's `before()` hook needs to flip a class or open a
  `<details>` for the *duration of that step only* (not its neighbors),
  undo it on the way out rather than leaving it set — see
  `createEditContent.ts`'s `setPreviewElevated`, which is toggled off in
  the neighboring steps' own `before()` rather than left on.

## 3. No dependency on specific database rows

- **Never hardcode a specific row's ID or name** in a step's `route` or
  `selector` (a particular content type, a particular content element).
  A tour must work against whatever's actually in the database, including
  one that's completely empty — there is no bundled tour-content package
  to rely on having been imported first.
- Where a step needs to show *some* real example of a repeated kind (a
  content type card, a table row), target it **generically** rather than
  by identity:
  - A prefix-matched attribute selector picks whichever element matches
    first in the DOM — e.g. `[data-tour^="contenttype-card-"]` instead of
    `` [data-tour="contenttype-card-${specificId}"] ``. See
    `createEditContentTour`'s "Pick a content type" step.
  - A plain, repeated `data-tour` on a per-row element (e.g. a table row's
    action buttons) already behaves this way for free —
    `document.querySelector` returns the first match regardless of which
    row it belongs to.
- **Follow the real in-app navigation instead of forcing a step's own
  `route`.** Once a step's `advanceOnClick` has taken the person to
  wherever the real click actually leads (a newly-created item's own ID,
  whatever row they picked), later steps should just keep targeting
  elements on that page rather than specifying `route` again. A `route` on
  a step that follows a real navigating click is usually a sign the step
  is compensating for a specific row it's assuming exists —
  `createEditContentTour` demonstrates the alternative: after picking any
  content type card, every remaining step omits `route` entirely.
- If no row of the needed kind exists, the step's selector simply won't
  resolve and the existing `waitForElement` timeout-and-skip behavior
  (`runner.ts`) skips it — a thinner database just means a few steps don't
  show, not a broken tour. This is the intended, graceful degradation path;
  don't special-case it.

## 4. Writing steps

- **One idea per step.** A step's `title` is a short label; `description`
  is one or two sentences explaining what the thing does or why it
  matters — not a restatement of the title, not a paragraph.
- Prefer **showing the real consequence of an action** over describing it
  abstractly — e.g. "Save writes immediately... every screen this content
  is currently assigned to updates right away" rather than just "Save your
  changes."
- Pick `side` based on where the popover will actually have room to render
  (table views commonly use `top` for a table and `bottom` for a header
  action; a right-hand preview panel uses `left`). Check it against the
  real page, not just a guess.
- Order steps the way a first-time user would actually move through the
  task: overview of the page first, then the primary action (e.g. "create
  new"), then supporting details.

## 5. Navigation and `advanceOnClick`

- **Set `advanceOnClick: true` on any step whose highlighted element
  performs real navigation** — a route change, or a click that swaps out
  what's on screen (e.g. closing a "pick one" dialog into a form). Without
  it, clicking the actual element (the natural thing to do instead of the
  tour's own "Next") leaves the popover stuck pointing at wherever that
  element used to be.
- Leave it unset for purely observational steps — a preview panel, a field
  to read, anything where clicking the target isn't the point.
- **Never set it on a tour's last step.** "Advance" there means "stop the
  tour and navigate to `/tour`" (see `runner.ts`'s `exitToTourPage`), which
  would yank the person away from the page their click just took them to —
  undoing the very thing they were shown. `layoutUsageTour`'s last step
  (an Edit button navigating to the layout editor) is deliberately left
  without `advanceOnClick` for exactly this reason.
  - If a navigating action genuinely belongs at the end of a tour, add a
    closing, non-navigating informational step after it instead of putting
    `advanceOnClick` on the last step.
- **An `advanceOnClick` step whose click only opens/closes a same-route
  dialog (not a route change) needs a defensive `before()` on the step
  after it**, re-running that same state change. If the person clicks
  "Next" instead of the real element, a route-based step's old page is
  genuinely gone, so the next step's target is missing and skips via the
  normal timeout — safe by construction. A dialog is different: the page
  underneath it is already mounted either way, so the following step's
  target already exists in the DOM and resolves immediately, highlighting
  it *behind the dialog that never opened/closed*. Fix it by clicking the
  real element again in a `before()` hook — it's a no-op once the dialog's
  already in the right state. See `ensureContentTypeSelected` in
  `createEditContent.ts` and `closeDialogIfStillOpen` in `contentTypes.ts`.
- `runner.ts` skips an unresolvable step in whichever direction the person
  was already travelling (Next vs. Previous), not always forward — this is
  what makes Previous work correctly back through dialog-dependent steps.
  You don't need to do anything for this yourself; it's automatic as long
  as you don't call `goToStep` directly from a tour file.

## 6. Scope and coherence

- **A tour needs one connecting topic.** Every step should serve the single
  task or concept named in the tour's `title`/`description` — if a step
  only makes sense as "also, while we're here," it belongs in a different
  tour (or doesn't belong at all).
- **Target 7–15 steps.** Fewer than 7 usually means the topic is too thin
  to be its own tour (fold it into a related one, or add the missing
  steps); more than 15 usually means it's actually two tours glued
  together — split it along the topic boundary instead of trimming
  description text to compensate.
- **Don't re-teach a concept a step already introduced.** If an earlier
  step (in this tour, or a prerequisite tour) already explained what
  something is (e.g. "Live Preview," "Scheduling"), a later step reusing
  it should use it, not re-explain it — repeating the same explanation
  reads as padding and signals the step doesn't have its own reason to
  exist.
- **Every step needs something for the person to do or verify**, not just
  read — click a button, fill a field, open a panel, compare what changed.
  A step that only narrates ("this section exists, it does X") without
  giving the person an action or a concrete thing to look at and confirm
  is a sign the step should be merged into a neighboring one rather than
  standing alone.

## 7. Verifying a new tour

Before registering it:

- Walk through the tour manually in the admin UI, including once against a
  genuinely empty database — not only your already-populated dev one — to
  confirm the steps that need a real example row degrade gracefully
  (skip) rather than hang or error.
- Confirm every step's element resolves within `ELEMENT_WAIT_MS` (4s) —
  if a step silently skips, its selector or hardcoded route/id is wrong.
- Click (don't just "Next") through every `advanceOnClick` step to confirm
  the popover follows correctly rather than desyncing.
- Confirm the last step is *not* `advanceOnClick`, and that "Exit Tour"
  lands back on `/tour`.
- **Click only "Next" from the first step to the last, never the real
  elements — confirm you reach "Exit Tour".** This is a hard rule, not
  optional: a tour that only *looks* fine because a dialog-gated step
  skips cleanly can still silently die off the end of the array if the
  skip cascades all the way past the last step (see §5's closing point
  and `CLAUDE.md` point 8) — `stop()` runs with no navigation back to
  `/tour`, and nothing in the UI tells you the tour ended early. A
  cleanly-skipping middle step and a tour that's about to die this way
  look identical until you actually reach the end, so this check can't
  be skipped on the assumption that skipping "looked graceful" earlier.
- **Then click "Previous" from that last step all the way back to the
  first, confirming each one lands on the step actually before it, not
  stuck or jumping forward.** This is also a hard rule — the direction-
  preserving skip in `runner.ts` (point 7) makes this correct by
  construction, but a new tour is still what exercises it, so verify it
  rather than assuming it.
- If the tour's styling needed any override in `main.css`, follow
  [Styleguide: Third-party widgets mounted outside the component
  tree](styleguide.md) and its dark-mode rules.
