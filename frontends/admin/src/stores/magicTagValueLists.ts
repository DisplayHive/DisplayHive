import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'
import type { MagicTagValueList } from '../types/models'

export const useMagicTagValueListsStore = defineStore('magicTagValueLists', () => {
  const { on, emit } = useSocket()

  const valueLists = ref<MagicTagValueList[]>([])
  const loading = ref(false)

  const handleList = (data: { data?: MagicTagValueList[] }) => {
    valueLists.value = data?.data || []
    loading.value = false
  }

  on('displayhive:admin:stc:upd_magic_tag_value_lists', handleList)

  const fetch = () => {
    loading.value = true
    emit('displayhive:admin:cts:get_magic_tag_value_lists')
  }

  return { valueLists, loading, fetch }
})
