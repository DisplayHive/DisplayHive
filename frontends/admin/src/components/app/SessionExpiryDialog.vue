<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useAuthStore } from '../../stores/auth'
import DialogTitle from '../ui/DialogTitle.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'

// Shown shortly before the session ends (the store raises `expiryWarning`): an admin in the middle of
// a form gets the chance to extend it instead of being logged out without notice. Extending is always
// the person's own click; nothing renews a session by itself.
const authStore = useAuthStore()

const now = ref(Date.now())
const extending = ref(false)
const error = ref<string | null>(null)
let tick: ReturnType<typeof setInterval> | null = null

const remaining = computed(() => Math.max(0, (authStore.expiresAt ?? now.value) - now.value))
const countdown = computed(() => {
  const seconds = Math.ceil(remaining.value / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
})

const stopTick = () => {
  if (tick !== null) {
    clearInterval(tick)
    tick = null
  }
}

watch(
  () => authStore.expiryWarning,
  (warn) => {
    stopTick()
    error.value = null
    if (!warn) return
    now.value = Date.now()
    tick = setInterval(() => (now.value = Date.now()), 1000)
  },
  { immediate: true },
)
onBeforeUnmount(stopTick)

const extend = async () => {
  extending.value = true
  try {
    error.value = await authStore.extendSession()
  } finally {
    extending.value = false
  }
}
</script>

<template>
  <Dialog :visible="authStore.expiryWarning" modal :closable="false" :style="{ width: '420px' }" data-testid="session-expiry-dialog">
    <template #header>
      <DialogTitle icon="pi-clock" title="Your session is ending" />
    </template>
    <p>
      You will be signed out in <strong data-testid="session-expiry-countdown">{{ countdown }}</strong>.
      Save what you are working on<template v-if="!authStore.isImpersonating">, or extend the session.</template>
      <template v-else>. An impersonated session cannot be extended.</template>
    </p>
    <p v-if="error" class="session-expiry-error">{{ error }}</p>
    <template #footer>
      <Button v-if="!authStore.isImpersonating" label="Extend session" icon="pi pi-refresh" :loading="extending" data-testid="session-extend" @click="extend" />
      <Button label="Sign out now" severity="secondary" text @click="authStore.logout()" />
    </template>
  </Dialog>
</template>

<style scoped>
.session-expiry-error {
  color: var(--p-red-500);
}
</style>
