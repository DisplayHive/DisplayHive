import { driver, type Driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import { useRouter, useRoute } from 'vue-router'
import type { TourDefinition } from './types'

// How long to wait for a step's target element to appear after navigating
// (route change + component mount + any async data load it triggers) before
// giving up on that step and skipping to the next one — keeps a tour from
// hanging forever if a future UI change removes/renames a target element.
const ELEMENT_WAIT_MS = 4000

function waitForElement(selector: string, timeoutMs = ELEMENT_WAIT_MS): Promise<Element | null> {
  const existing = document.querySelector(selector)
  if (existing) return Promise.resolve(existing)

  return new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      const el = document.querySelector(selector)
      if (el) {
        observer.disconnect()
        clearTimeout(timer)
        resolve(el)
      }
    })
    observer.observe(document.body, { childList: true, subtree: true })
    const timer = setTimeout(() => {
      observer.disconnect()
      resolve(document.querySelector(selector))
    }, timeoutMs)
  })
}

export function useTourRunner() {
  const router = useRouter()
  const route = useRoute()

  let driverObj: Driver | null = null
  let activeTour: TourDefinition | null = null

  const stop = () => {
    driverObj?.destroy()
    driverObj = null
    activeTour = null
  }

  const goToStep = async (index: number, direction: 1 | -1 = 1) => {
    const tour = activeTour
    if (!tour) return
    const step = tour.steps[index]
    if (!step) {
      // Ran off the end going forward: finish normally. Ran off the start
      // going backward (every earlier step unresolvable, vanishingly
      // unlikely): there's nothing earlier to fall back to, so just leave
      // the current highlight as-is rather than wrongly ending the tour.
      if (direction === 1) stop()
      return
    }

    if (step.route && route.path !== step.route) {
      await router.push(step.route)
    }
    if (step.before) await step.before()

    const el = await waitForElement(step.selector)
    if (!el) {
      // Target vanished (renamed class, moved element, ...), or — for a
      // step whose element only exists inside a dialog — the dialog isn't
      // open from this direction (e.g. going back after a later step's
      // own `before()` already closed it). Either way, skip past it in
      // whichever direction we were already travelling, rather than
      // hardcoding "forward": skipping forward while the person clicked
      // "Previous" would silently undo their click and leave Back/Next
      // looking broken.
      await goToStep(index + direction, direction)
      return
    }

    const isFirst = index === 0
    const isLast = index === tour.steps.length - 1
    // 'next' must always be included, even on the last step — it's the
    // button showing "Exit Tour" there. Excluding it (as this used to do,
    // matching its unused nextBtnText value against nothing) left the last
    // step with no bottom-row way to finish at all, only the small × icon.
    const buttons: Array<'next' | 'previous' | 'close'> = [
      ...(isFirst ? [] : (['previous'] as const)),
      'next',
      'close',
    ]

    const exitToTourPage = () => {
      stop()
      router.push('/tour')
    }

    driverObj!.highlight({
      element: step.selector,
      advanceOnClick: step.advanceOnClick,
      popover: {
        title: step.title,
        description: step.description,
        side: step.side,
        showButtons: buttons,
        showProgress: true,
        // driver.js only expands the {{current}}/{{total}} placeholders
        // when steps are driven through its own `steps` config + drive();
        // .highlight() (used here, since steps are driven manually to allow
        // route changes between them) passes progressText straight through
        // unmodified, so the numbers are interpolated here instead.
        progressText: `Step ${index + 1} of ${tour.steps.length}`,
        nextBtnText: isLast ? 'Exit Tour' : 'Next',
        onNextClick: isLast ? exitToTourPage : () => goToStep(index + 1, 1),
        onPrevClick: () => goToStep(index - 1, -1),
        onCloseClick: () => stop(),
      },
    })
  }

  const start = (tour: TourDefinition) => {
    stop()
    activeTour = tour
    driverObj = driver({
      allowClose: true,
      stagePadding: 6,
      smoothScroll: true,
      onDestroyed: () => {
        activeTour = null
      },
    })
    goToStep(0)
  }

  return { start, stop }
}
