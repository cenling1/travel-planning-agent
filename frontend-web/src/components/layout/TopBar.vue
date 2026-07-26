<script setup lang="ts">
// ============================================================
// Layer 6: Component — TopBar
// App title, health indicator, user menu, logout
// ============================================================
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSystemStore } from '@/stores/system'
import { Sunny, User, Setting, SwitchButton, Guide } from '@element-plus/icons-vue'

defineProps<{
  sidebarCollapsed: boolean
}>()

const emit = defineEmits<{
  toggleSidebar: []
  toggleMobile: []
  logout: []
}>()

const router = useRouter()
const authStore = useAuthStore()
const systemStore = useSystemStore()

const healthStatus = computed(() => {
  if (!systemStore.health) return 'unknown'
  return systemStore.health.status === 'ok' ? 'ok' : 'error'
})

function goTo(path: string) {
  router.push(path)
}
</script>

<template>
  <header class="topbar">
    <div class="topbar__left">
      <el-button
        class="toggle-btn"
        :icon="Guide"
        text
        @click="emit('toggleSidebar')"
        title="切换侧边栏"
      />
      <el-button
        class="toggle-btn mobile-only"
        :icon="Guide"
        text
        @click="emit('toggleMobile')"
        title="菜单"
      />
      <span class="topbar__title" @click="goTo('/chat')">
        <Sunny class="title-icon" />
        <span class="title-text">智能旅行规划</span>
      </span>
    </div>

    <div class="topbar__right">
      <!-- Health indicator -->
      <el-tooltip
        :content="healthStatus === 'ok' ? '服务正常' : healthStatus === 'error' ? '服务异常' : '检查中…'"
        placement="bottom"
      >
        <span class="health-dot" :class="`health-dot--${healthStatus}`" />
      </el-tooltip>

      <!-- Admin menu -->
      <el-dropdown v-if="authStore.isAdmin" trigger="click">
        <el-button text size="small" type="warning">
          <el-icon><Setting /></el-icon>
          管理
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="goTo('/admin/users')">用户管理</el-dropdown-item>
            <el-dropdown-item @click="goTo('/admin/system')">系统状态</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- User menu -->
      <el-dropdown trigger="click">
        <span class="user-info">
          <el-icon><User /></el-icon>
          <span class="username">{{ authStore.user?.username || '用户' }}</span>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="goTo('/profile')">
              <el-icon><Setting /></el-icon>
              账号设置
            </el-dropdown-item>
            <el-dropdown-item divided @click="emit('logout')">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 16px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
  flex-shrink: 0;
}

.topbar__left {
  display: flex;
  align-items: center;
  gap: 4px;
}

.toggle-btn.mobile-only {
  display: none;
}

@media (max-width: 768px) {
  .toggle-btn:not(.mobile-only) {
    display: none;
  }
  .toggle-btn.mobile-only {
    display: inline-flex;
  }
}

.topbar__title {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 15px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  flex-shrink: 0;
}

.title-icon {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  color: var(--el-color-warning);
}

.topbar__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.health-dot--ok { background: var(--el-color-success); }
.health-dot--error { background: var(--el-color-danger); }
.health-dot--unknown { background: var(--el-color-info); animation: pulse 1.5s infinite; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.username {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
