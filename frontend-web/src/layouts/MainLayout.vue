<script setup lang="ts">
// ============================================================
// Layer 7: Layout — Main application shell
// TopBar + Sidebar + Main Content Area
// ============================================================
import { ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSystemStore } from '@/stores/system'
import { useConversationStore } from '@/stores/conversation'
import TopBar from '@/components/layout/TopBar.vue'
import Sidebar from '@/components/layout/Sidebar.vue'

const router = useRouter()
const authStore = useAuthStore()
const systemStore = useSystemStore()
const convStore = useConversationStore()

const sidebarCollapsed = ref(false)
const mobileDrawerOpen = ref(false)

// Start health polling
systemStore.startHealthPolling()
onUnmounted(() => systemStore.stopHealthPolling())

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function toggleMobileDrawer() {
  mobileDrawerOpen.value = !mobileDrawerOpen.value
}

async function handleNewChat() {
  mobileDrawerOpen.value = false
  const conv = await convStore.create()
  if (conv) {
    router.push(`/chat/${conv.id}`)
  }
}

function handleSelectConversation(id: string) {
  mobileDrawerOpen.value = false
  router.push(`/chat/${id}`)
}

function handleLogout() {
  authStore.logout().then(() => router.push('/login'))
}
</script>

<template>
  <div class="main-layout">
    <!-- Mobile overlay -->
    <div
      v-if="mobileDrawerOpen"
      class="mobile-overlay"
      @click="toggleMobileDrawer"
    />

    <!-- Sidebar -->
    <aside
      class="sidebar"
      :class="{
        'sidebar--collapsed': sidebarCollapsed,
        'sidebar--mobile-open': mobileDrawerOpen,
      }"
    >
      <Sidebar
        :collapsed="sidebarCollapsed"
        @new-chat="handleNewChat"
        @select-conversation="handleSelectConversation"
        @close-mobile="toggleMobileDrawer"
      />
    </aside>

    <!-- Main area -->
    <div class="main-area">
      <TopBar
        :sidebar-collapsed="sidebarCollapsed"
        @toggle-sidebar="toggleSidebar"
        @toggle-mobile="toggleMobileDrawer"
        @logout="handleLogout"
      />

      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 280px;
  min-width: 280px;
  height: 100vh;
  border-right: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
  transition: width 0.2s, min-width 0.2s;
  overflow: hidden;
  z-index: 100;
}

.sidebar--collapsed {
  width: 0;
  min-width: 0;
  border-right: none;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

/* Mobile */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: -280px;
    transition: left 0.25s ease;
    box-shadow: none;
  }

  .sidebar--mobile-open {
    left: 0;
    box-shadow: 2px 0 12px rgba(0,0,0,0.15);
  }

  .mobile-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    z-index: 99;
  }
}
</style>
