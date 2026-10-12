import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from './useSocket'
import { useAck, type Ack } from './useAck'

export interface BotUser { id: number; title: string }
export interface SavedUser { id: number; name: string; chat_id: string }
export interface AlertType { key: string; label: string }

/**
 * State and actions of the Alerting page: the Telegram bot token, the users
 * found by the bot and the saved ones, the alert types and the
 * user × alert-type subscription matrix. Registers its socket handlers for
 * the lifetime of the calling component.
 */
export function useAlerting() {
  const { on, off, emit } = useSocket()
  const { request } = useAck()

  // ── Settings ─────────────────────────────────────────────────────────────────
  const loading = ref(true)
  const hasToken = ref(false)
  const tokenInput = ref('')
  const savingToken = ref(false)

  // ── Bot user discovery ────────────────────────────────────────────────────────
  const loadingBotUsers = ref(false)
  const botUsersLoaded = ref(false)
  const botUsersError = ref('')

  const botUsers = ref<BotUser[]>([])

  // ── Saved alert users ─────────────────────────────────────────────────────────
  const savedUsers = ref<SavedUser[]>([])
  const testingId = ref<number | null>(null)
  const removingId = ref<number | null>(null)
  const addingChatId = ref<string | null>(null)

  // ── Alert types & subscriptions ───────────────────────────────────────────────
  const alertTypes = ref<AlertType[]>([])

  // Set of "userId:alertType" strings for O(1) lookup
  const subscriptionSet = ref<Set<string>>(new Set())
  const togglingKey = ref<string | null>(null)

  const isSubscribed = (userId: number, alertKey: string): boolean =>
    subscriptionSet.value.has(`${userId}:${alertKey}`)

  const showMatrix = computed(() =>
    hasToken.value && savedUsers.value.length > 0 && alertTypes.value.length > 0
  )

  // ── Socket handlers ───────────────────────────────────────────────────────────
  const handleSettings = (data: { has_telegram_token?: boolean }) => {
    loading.value = false
    hasToken.value = !!data?.has_telegram_token
    if (hasToken.value) {
      fetchBotUsers()
      fetchSavedUsers()
      fetchAlertSubscriptions()
    }
  }

  const handleSavedUsers = (data: { users?: SavedUser[] }) => {
    savedUsers.value = data?.users || []
  }

  const handleAlertTypes = (data: { alert_types?: AlertType[] }) => {
    alertTypes.value = data?.alert_types || []
  }

  const handleAlertSubscriptions = (data: { subscriptions?: Array<{ user_id: number; alert_type: string }> }) => {
    const subs = data?.subscriptions || []
    subscriptionSet.value = new Set(subs.map(s => `${s.user_id}:${s.alert_type}`))
  }

  // ── Actions ───────────────────────────────────────────────────────────────────
  const saveToken = async () => {
    savingToken.value = true
    try {
      const ack = await request('displayhive:admin:alerting:cts:save_telegram_token', { token: tokenInput.value }, { success: 'Telegram token saved', error: 'Save failed' })
      if (ack) {
        tokenInput.value = ''
        if (hasToken.value) {
          fetchBotUsers()
          fetchSavedUsers()
          fetchAlertSubscriptions()
        }
      }
    } finally {
      savingToken.value = false
    }
  }

  const fetchBotUsers = async () => {
    loadingBotUsers.value = true
    botUsersError.value = ''
    try {
      // The reason is shown inside the card (botUsersError), not as a toast.
      const ack = await request<Ack & { users?: BotUser[] }>('displayhive:admin:alerting:cts:get_telegram_users_from_bot', undefined, {
        onError: (message) => { botUsersError.value = message },
      })
      botUsersLoaded.value = true
      botUsers.value = ack?.users || []
    } finally {
      loadingBotUsers.value = false
    }
  }

  const fetchSavedUsers = () => emit('displayhive:admin:alerting:cts:get_telegram_users')
  const fetchAlertSubscriptions = () => emit('displayhive:admin:alerting:cts:get_alert_subscriptions')

  const addUser = async (user: BotUser) => {
    addingChatId.value = String(user.id)
    try {
      await request('displayhive:admin:alerting:cts:add_telegram_user', {
        name: user.title,
        chat_id: String(user.id),
      }, { success: `${user.title} added`, error: 'Failed to add user' })
    } finally {
      addingChatId.value = null
    }
  }

  const removeUser = async (user: SavedUser) => {
    removingId.value = user.id
    try {
      await request('displayhive:admin:alerting:cts:remove_telegram_user', { id: user.id }, { error: 'Failed to remove' })
    } finally {
      removingId.value = null
    }
  }

  const sendTest = async (user: SavedUser) => {
    testingId.value = user.id
    try {
      await request('displayhive:admin:alerting:cts:send_telegram_test', { chat_id: user.chat_id }, { success: `Test message sent to ${user.name}`, error: 'Failed to send' })
    } finally {
      testingId.value = null
    }
  }

  const toggleSubscription = async (userId: number, alertKey: string) => {
    const key = `${userId}:${alertKey}`
    if (togglingKey.value === key) return
    togglingKey.value = key

    const enabled = !isSubscribed(userId, alertKey)
    // Optimistic update
    const next = new Set(subscriptionSet.value)
    if (enabled) next.add(key); else next.delete(key)
    subscriptionSet.value = next

    try {
      const ack = await request('displayhive:admin:alerting:cts:toggle_alert_subscription', {
        user_id: userId,
        alert_type: alertKey,
        enabled,
      }, { error: 'Failed to save' })
      if (!ack) {
        // Revert on failure
        const reverted = new Set(subscriptionSet.value)
        if (enabled) reverted.delete(key); else reverted.add(key)
        subscriptionSet.value = reverted
      }
    } finally {
      togglingKey.value = null
    }
  }

  onMounted(() => {
    on('displayhive:admin:alerting:stc:settings', handleSettings)
    on('displayhive:admin:alerting:stc:telegram_users', handleSavedUsers)
    on('displayhive:admin:alerting:stc:alert_types', handleAlertTypes)
    on('displayhive:admin:alerting:stc:alert_subscriptions', handleAlertSubscriptions)
    emit('displayhive:admin:alerting:cts:get_settings')
    emit('displayhive:admin:alerting:cts:get_alert_types')
  })

  onUnmounted(() => {
    off('displayhive:admin:alerting:stc:settings', handleSettings)
    off('displayhive:admin:alerting:stc:telegram_users', handleSavedUsers)
    off('displayhive:admin:alerting:stc:alert_types', handleAlertTypes)
    off('displayhive:admin:alerting:stc:alert_subscriptions', handleAlertSubscriptions)
  })

  return {
    loading, hasToken, tokenInput, savingToken,
    loadingBotUsers, botUsersLoaded, botUsersError, botUsers,
    savedUsers, testingId, removingId, addingChatId,
    alertTypes, togglingKey, showMatrix,
    isSubscribed, saveToken, fetchBotUsers, addUser, removeUser, sendTest, toggleSubscription,
  }
}
