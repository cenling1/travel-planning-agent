<script setup lang="ts">
// ============================================================
// Layer 7: Layout — Admin sub-layout with tab navigation
// ============================================================
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const tabs = [
  { path: '/admin/users', label: '用户管理' },
  { path: '/admin/system', label: '系统状态' },
]

function isActive(path: string) {
  return route.path === path
}

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="admin-layout">
    <div class="admin-tabs">
      <el-button
        v-for="tab in tabs"
        :key="tab.path"
        :type="isActive(tab.path) ? 'primary' : 'default'"
        size="small"
        text
        @click="navigate(tab.path)"
      >
        {{ tab.label }}
      </el-button>
    </div>
    <div class="admin-content">
      <router-view />
    </div>
  </div>
</template>

<style scoped>
.admin-layout {
  padding: 16px 24px;
}

.admin-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--el-border-color-light);
  padding-bottom: 12px;
}

.admin-content {
  max-width: 1200px;
}
</style>
