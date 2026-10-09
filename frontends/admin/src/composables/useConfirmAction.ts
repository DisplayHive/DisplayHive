import { useConfirm } from 'primevue/useconfirm'
import type { ConfirmationOptions } from 'primevue/confirmationoptions'

/**
 * The confirmation every destructive action asks for: warning icon, red accept button and
 * the header "Confirm Delete" unless you give another (e.g. "Unlink SSO login").
 *
 *     const { confirmDanger } = useConfirmAction()
 *     confirmDanger({ message: `Delete "${x.name}"?`, accept: () => remove(x) })
 *
 * Anything PrimeVue's `confirm.require` accepts can be passed on (labels, reject, …).
 */
export function useConfirmAction() {
  const confirm = useConfirm()

  const confirmDanger = (options: ConfirmationOptions) =>
    confirm.require({
      header: 'Confirm Delete',
      icon: 'pi pi-exclamation-triangle',
      acceptClass: 'p-button-danger',
      ...options,
    })

  return { confirmDanger }
}
