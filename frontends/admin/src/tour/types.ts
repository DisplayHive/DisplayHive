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
}

export interface TourDefinition {
  id: string
  title: string
  description: string
  icon: string
  category: 'user' | 'admin'
  steps: TourStep[]
}
