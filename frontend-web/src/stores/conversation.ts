// ============================================================
// Layer 4: Store — Conversation
// Manages conversation list, current selection, search
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Conversation, ConversationDetail } from '@/types/conversation'
import { conversationsApi } from '@/api/conversations'
import { extractErrorMessage } from '@/utils/error'

export const useConversationStore = defineStore('conversation', () => {
  // ---- State ----
  const conversations = ref<Conversation[]>([])
  const currentId = ref<string | null>(null)
  const currentDetail = ref<ConversationDetail | null>(null)
  const searchKeyword = ref('')
  const isLoading = ref(false)
  const isLoadingDetail = ref(false)
  const error = ref<string | null>(null)

  // ---- Getters ----
  const filteredConversations = computed(() => {
    if (!searchKeyword.value) return conversations.value
    const kw = searchKeyword.value.toLowerCase()
    return conversations.value.filter(
      (c) =>
        c.title.toLowerCase().includes(kw) ||
        c.summary.toLowerCase().includes(kw),
    )
  })

  const currentConversation = computed(() =>
    conversations.value.find((c) => c.id === currentId.value) || null,
  )

  // ---- Actions ----
  async function fetchList(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      conversations.value = await conversationsApi.list()
    } catch (err) {
      error.value = extractErrorMessage(err, '加载会话列表失败')
    } finally {
      isLoading.value = false
    }
  }

  async function fetchDetail(id: string): Promise<void> {
    isLoadingDetail.value = true
    error.value = null
    try {
      currentId.value = id
      currentDetail.value = await conversationsApi.get(id)
    } catch (err) {
      error.value = extractErrorMessage(err, '加载会话详情失败')
      currentDetail.value = null
    } finally {
      isLoadingDetail.value = false
    }
  }

  async function create(title?: string): Promise<Conversation | null> {
    error.value = null
    try {
      const conversation = await conversationsApi.create(title)
      conversations.value.unshift(conversation)
      currentId.value = conversation.id
      currentDetail.value = {
        ...conversation,
        messages: [],
      }
      return conversation
    } catch (err) {
      error.value = extractErrorMessage(err, '创建会话失败')
      return null
    }
  }

  async function remove(id: string): Promise<boolean> {
    error.value = null
    try {
      await conversationsApi.delete(id)
      conversations.value = conversations.value.filter((c) => c.id !== id)
      if (currentId.value === id) {
        currentId.value = null
        currentDetail.value = null
      }
      return true
    } catch (err) {
      error.value = extractErrorMessage(err, '删除会话失败')
      return false
    }
  }

  function setCurrent(id: string | null) {
    currentId.value = id
    if (!id) {
      currentDetail.value = null
    }
  }

  function setSearchKeyword(kw: string) {
    searchKeyword.value = kw
  }

  return {
    // State
    conversations,
    currentId,
    currentDetail,
    searchKeyword,
    isLoading,
    isLoadingDetail,
    error,
    // Getters
    filteredConversations,
    currentConversation,
    // Actions
    fetchList,
    fetchDetail,
    create,
    remove,
    setCurrent,
    setSearchKeyword,
  }
})
