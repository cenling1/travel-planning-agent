<script setup lang="ts">
// ============================================================
// Layer 6: Component — Sidebar
// New chat button, search, conversation list, nav links
// ============================================================
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useConversationStore } from '@/stores/conversation'
import { useAuthStore } from '@/stores/auth'
import { formatDate, truncate } from '@/utils/format'
import { Plus, Search, ChatDotRound, Document, Reading, Close } from '@element-plus/icons-vue'

defineProps<{
  collapsed: boolean
}>()

const emit = defineEmits<{
  newChat: []
  selectConversation: [id: string]
  closeMobile: []
}>()

const router = useRouter()
const route = useRoute()
const convStore = useConversationStore()
const authStore = useAuthStore()

const searchInput = ref('')

onMounted(() => {
  convStore.fetchList()
})

// Debounced search
let searchTimer: ReturnType<typeof setTimeout> | null = null
function onSearchInput(val: string) {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    convStore.setSearchKeyword(val)
  }, 200)
}

function isActive(id: string): boolean {
  return route.params.conversationId === id
}

async function handleDelete(id: string, event: Event) {
  event.stopPropagation()
  try {
    await ElMessageBox.confirm('确定要删除这个会话吗？删除后不可恢复。', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const ok = await convStore.remove(id)
    if (ok && route.params.conversationId === id) {
      router.push('/chat')
    }
  } catch {
    // User cancelled
  }
}

// Need to import ElMessageBox
import { ElMessageBox } from 'element-plus'
</script>

<template>
  <div class="sidebar-inner">
    <div class="sidebar__header">
      <el-button
        type="primary"
        :icon="Plus"
        size="default"
        class="new-chat-btn"
        @click="emit('newChat')"
      >
        新建旅行规划
      </el-button>
      <el-button
        text
        :icon="Close"
        class="close-mobile-btn"
        @click="emit('closeMobile')"
      />
    </div>

    <!-- Search -->
    <div class="sidebar__search">
      <el-input
        v-model="searchInput"
        :prefix-icon="Search"
        placeholder="搜索会话…"
        size="small"
        clearable
        @input="onSearchInput"
      />
    </div>

    <!-- Conversation list -->
    <nav class="sidebar__nav">
      <div
        v-if="convStore.isLoading"
        class="sidebar__loading"
      >
        <el-icon class="is-loading"><ChatDotRound /></el-icon>
        加载中…
      </div>

      <div
        v-else-if="convStore.filteredConversations.length === 0"
        class="sidebar__empty"
      >
        <p v-if="searchInput">无匹配的会话</p>
        <p v-else>暂无历史会话<br/>点击上方按钮开始规划</p>
      </div>

      <div
        v-for="conv in convStore.filteredConversations"
        :key="conv.id"
        class="conv-item"
        :class="{ 'conv-item--active': isActive(conv.id) }"
        @click="emit('selectConversation', conv.id)"
      >
        <div class="conv-item__content">
          <span class="conv-item__title">{{ truncate(conv.title, 28) }}</span>
          <span class="conv-item__summary">{{ truncate(conv.summary || '暂无摘要', 40) }}</span>
          <span class="conv-item__time">{{ formatDate(conv.updated_at, 'relative') }}</span>
        </div>
        <el-button
          class="conv-item__delete"
          :icon="Close"
          text
          size="small"
          @click="handleDelete(conv.id, $event)"
          title="删除会话"
        />
      </div>
    </nav>

    <!-- Bottom links -->
    <div class="sidebar__footer">
      <div
        class="sidebar__link"
        :class="{ 'sidebar__link--active': route.path === '/documents' }"
        @click="router.push('/documents')"
      >
        <el-icon><Document /></el-icon>
        知识文档
      </div>
      <div
        class="sidebar__link"
        :class="{ 'sidebar__link--active': route.path === '/memories' }"
        @click="router.push('/memories')"
      >
        <el-icon><Reading /></el-icon>
        长期记忆
      </div>
    </div>
  </div>
</template>

<style scoped>
.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 280px;
}

.sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
}

.new-chat-btn {
  flex: 1;
}

.close-mobile-btn {
  display: none;
}

@media (max-width: 768px) {
  .close-mobile-btn {
    display: inline-flex;
  }
}

.sidebar__search {
  padding: 0 12px 8px;
}

.sidebar__nav {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.sidebar__loading,
.sidebar__empty {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  padding: 24px 0;
}

.conv-item {
  display: flex;
  align-items: flex-start;
  padding: 10px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
}

.conv-item:hover {
  background: var(--el-fill-color-light);
}

.conv-item--active {
  background: var(--el-color-primary-light-9);
}

.conv-item__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item__title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.conv-item__summary {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-item__time {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.conv-item__delete {
  opacity: 0;
  transition: opacity 0.15s;
}

.conv-item:hover .conv-item__delete {
  opacity: 1;
}

.sidebar__footer {
  border-top: 1px solid var(--el-border-color-light);
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar__link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--el-text-color-regular);
  transition: background 0.15s;
}

.sidebar__link:hover {
  background: var(--el-fill-color-light);
}

.sidebar__link--active {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
</style>
