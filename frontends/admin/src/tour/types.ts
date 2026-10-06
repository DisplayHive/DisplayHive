export interface TourStep {
  /** Router path to navigate to before this step, if different from the current route. */
  route?: string
  /** CSS selector for the element driver.js should highlight. */
  selector: string
  title: string
  description: string
  side?: 'top' | 'right' | 'bottom' | 'left'
  /** Runs after navigation, before the element is looked up — e.g. to open a dialog or set a filter. */
  before?: () => void | Promise<void>
  /**
   * driver.js's built-in option: clicking the highlighted element itself
   * triggers the same advance as clicking the tour's own "Next" button.
   * Set this on any step whose element performs real navigation (a route
   * change, or something that replaces what's on screen) — otherwise the
   * person clicking the actual button/link/card they were just shown (the
   * natural thing to do) leaves the tour's popover stuck pointing at
   * wherever that element used to be, out of sync with the page. Leave
   * unset for purely observational steps (a preview panel, a field to
   * read) where clicking the target isn't the point of the step.
   */
  advanceOnClick?: boolean
}

export interface TourDefinition {
  id: string
  title: string
  description: string
  icon: string
  category: 'user' | 'admin'
  steps: TourStep[]
}
