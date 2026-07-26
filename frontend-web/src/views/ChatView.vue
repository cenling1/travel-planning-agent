<script setup lang="ts">
// ============================================================
// Layer 8: View — Chat (Travel Planning Workspace)
// ============================================================
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useConversationStore } from '@/stores/conversation'
import { useChatStore } from '@/stores/chat'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import TripSummary from '@/components/chat/TripSummary.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import { ChatDotRound } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const convStore = useConversationStore()
const chatStore = useChatStore()

const chatInputRef = ref<InstanceType<typeof ChatInput> | null>(null)
const messageListRef = ref<HTMLElement | null>(null)

// Current conversation ID from route
const conversationId = computed(() => route.params.conversationId as string | undefined)

// Get chat session state
const session = computed(() => chatStore.sessionFor(conversationId.value || null))
const hasTripSummary = computed(() => {
  const summary = session.value.response?.trip_summary
  return !!summary && Object.values(summary).some((value) =>
    Array.isArray(value) ? value.length > 0 : value !== null && value !== '',
  )
})

// Messages: from detail (persisted) + streaming content (in-progress)
const messages = computed(() => {
  const msgs = convStore.currentDetail?.messages || []
  return msgs.map((msg, index) => ({
    ...msg,
    _isStreaming: false,
    _citations: index === msgs.length - 1 && msg.role === 'assistant' && msg.content === session.value.response?.answer
      ? session.value.response.citations
      : undefined,
    _tools: index === msgs.length - 1 && msg.role === 'assistant' && msg.content === session.value.response?.answer
      ? session.value.response.tools
      : undefined,
  }))
})

const showPendingUser = computed(() => {
  if (!session.value.pendingUserQuery) return false
  const persistedMatches = messages.value.filter(
    (message) => message.role === 'user' && message.content === session.value.pendingUserQuery,
  ).length
  return persistedMatches <= session.value.matchingUserCountAtStart
})

const showAssistantOverlay = computed(() => {
  if (!session.value.streamingContent) return false
  const last = messages.value[messages.value.length - 1]
  return !(last?.role === 'assistant' && last.content === session.value.response?.answer)
})

// Load conversation detail when ID changes
watch(
  () => conversationId.value,
  async (id) => {
    chatStore.initSession(id || null)
    if (id) {
      await convStore.fetchDetail(id)
    } else {
      convStore.setCurrent(null)
    }
    await nextTick()
    scrollToBottom()
  },
  { immediate: true },
)

// Auto-scroll when streaming
watch(
  () => session.value.streamingContent,
  () => {
    nextTick(() => scrollToBottom())
  },
)

function scrollToBottom() {
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

async function handleSend(query: string) {
  // If no conversation, create one first
  if (!conversationId.value) {
    const conv = await convStore.create()
    if (!conv) return
    await router.push(`/chat/${conv.id}`)
    await chatStore.sendMessage(query, conv.id)
    return
  }

  await chatStore.sendMessage(query, conversationId.value || null)
  await nextTick()
  scrollToBottom()
}

function handleStop() {
  chatStore.stopGeneration(conversationId.value || null)
}

function handleRetry() {
  // Re-send last user message
  const msgs = convStore.currentDetail?.messages
  if (!msgs) return
  const lastUserMsg = [...msgs].reverse().find((m) => m.role === 'user')
  if (lastUserMsg) {
    handleSend(lastUserMsg.content)
  }
}

onUnmounted(() => {
  chatStore.cleanupSession(conversationId.value || null)
})
</script>

<template>
  <div class="chat-view" :class="{ 'chat-view--with-summary': hasTripSummary }">
    <!-- Message area -->
    <div ref="messageListRef" class="chat-messages">
      <!-- Empty state -->
      <EmptyState
        v-if="!convStore.isLoadingDetail && messages.length === 0 && !session.isGenerating && !session.pendingUserQuery"
        icon="ChatDotRound"
        title="开始旅行规划"
        description="在下方输入旅行需求，AI 将结合知识库和实时工具为你生成旅行方案"
      />

      <!-- Loading detail -->
      <div v-if="convStore.isLoadingDetail" class="chat-loading">
        <el-icon class="is-loading" :size="24"><ChatDotRound /></el-icon>
        <span>加载会话…</span>
      </div>

      <!-- Error -->
      <ErrorAlert
        v-if="convStore.error"
        :error="convStore.error"
        :show-retry="true"
        @retry="conversationId ? convStore.fetchDetail(conversationId) : undefined"
      />

      <!-- Persisted messages -->
      <MessageBubble
        v-for="msg in messages"
        :key="msg.id"
        :role="msg.role"
        :content="msg.content"
        :timestamp="msg.created_at"
        :citations="msg._citations"
        :tools="msg._tools"
      />

      <MessageBubble
        v-if="showPendingUser"
        role="user"
        :content="session.pendingUserQuery"
      />

      <!-- Functional journey progress rail -->
      <div v-if="session.isGenerating && session.progress" class="stream-progress" aria-live="polite">
        <span class="progress-pulse" />
        <span>{{ session.progress }}</span>
      </div>

      <!-- Streaming content -->
      <div v-if="showAssistantOverlay" class="stream-message">
        <MessageBubble
          role="assistant"
          :content="session.response?.answer || session.streamingContent"
          :citations="session.response?.citations"
          :tools="session.response?.tools"
          :is-streaming="session.isGenerating"
          :is-stopped="session.stopped"
        />
      </div>

      <!-- Error -->
      <div v-if="session.error" class="stream-error">
        <ErrorAlert :error="session.error" :show-retry="true" @retry="handleRetry" />
      </div>
    </div>

    <!-- Trip summary sidebar -->
    <TripSummary :response="session.response" />

    <!-- Input -->
    <div class="chat-input-area">
      <ChatInput
        ref="chatInputRef"
        :is-generating="session.isGenerating"
        :disabled="convStore.isLoadingDetail"
        @send="handleSend"
        @stop="handleStop"
      />
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) auto;
  flex: 1;
  height: 100%;
  overflow: hidden;
}

.chat-view--with-summary { grid-template-columns: minmax(0, 1fr) 240px; }

.chat-messages {
  grid-column: 1;
  grid-row: 1;
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  min-width: 0;
}

.chat-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 0;
  color: var(--el-text-color-secondary);
}

.stream-progress {
  display: flex;
  align-items: center;
  gap: 9px;
  width: fit-content;
  margin: 8px 44px;
  padding: 7px 10px;
  border-left: 2px solid var(--el-color-warning);
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.progress-pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-warning);
  animation: progress-pulse 1.2s ease-in-out infinite;
}

@keyframes progress-pulse { 50% { opacity: .35; transform: scale(.75); } }

.stream-error {
  margin: 12px 0;
}

.chat-input-area {
  grid-column: 1;
  grid-row: 2;
  background: var(--el-bg-color);
}

.chat-view :deep(.trip-summary) {
  grid-column: 2;
  grid-row: 1 / 3;
}

@media (max-width: 1024px) {
  .chat-view,
  .chat-view--with-summary { grid-template-columns: minmax(0, 1fr); }
}

@media (max-width: 768px) {
  .chat-messages {
    padding: 12px;
  }
  .stream-progress { margin-left: 0; }
}
</style>
