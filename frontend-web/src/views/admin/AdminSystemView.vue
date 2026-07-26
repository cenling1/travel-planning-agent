<script setup lang="ts">
// ============================================================
// Layer 8: View — Admin: System Status
// ============================================================
import { ref, onMounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import { healthApi } from '@/api/health'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import { Refresh } from '@element-plus/icons-vue'

const systemStore = useSystemStore()
const toolHealth = ref<Record<string, boolean> | null>(null)
const isLoadingTools = ref(false)

async function fetchToolHealth() {
  isLoadingTools.value = true
  try {
    const result = await healthApi.checkTools()
    toolHealth.value = result.configured
  } catch {
    toolHealth.value = null
  } finally {
    isLoadingTools.value = false
  }
}

onMounted(() => {
  systemStore.checkHealth()
  fetchToolHealth()
})
</script>

<template>
  <div class="admin-system">
    <div class="page-header">
      <h2>系统状态</h2>
      <el-button :icon="Refresh" :loading="systemStore.isCheckingHealth" @click="systemStore.checkHealth(); fetchToolHealth()">
        刷新
      </el-button>
    </div>

    <el-row :gutter="16">
      <!-- Overall -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <template #header>服务状态</template>
          <div class="status-value">
            <el-tag
              :type="systemStore.health?.status === 'ok' ? 'success' : 'danger'"
              size="large"
            >
              {{ systemStore.health?.status === 'ok' ? '正常' : systemStore.health?.status || '未知' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>

      <!-- Database -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <template #header>数据库</template>
          <div class="status-value">
            <span class="mono">{{ systemStore.health?.database || '—' }}</span>
          </div>
        </el-card>
      </el-col>

      <!-- Auth -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <template #header>认证系统</template>
          <div class="status-detail">
            <p>认证: <el-tag :type="systemStore.health?.auth_enabled ? 'success' : 'info'" size="small">{{ systemStore.health?.auth_enabled ? '已启用' : '未启用' }}</el-tag></p>
            <p>注册: <el-tag :type="systemStore.health?.registration_enabled ? 'warning' : 'info'" size="small">{{ systemStore.health?.registration_enabled ? '开放' : '关闭' }}</el-tag></p>
          </div>
        </el-card>
      </el-col>

      <!-- Embedding -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover">
          <template #header>向量服务</template>
          <div class="status-value">
            <span>{{ systemStore.health?.embedding_provider || '—' }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tool health -->
    <el-card class="tools-card" shadow="hover">
      <template #header>MCP 工具状态</template>
      <div v-if="isLoadingTools" class="tools-loading">
        <el-icon class="is-loading"><Refresh /></el-icon> 加载中…
      </div>
      <div v-else-if="!toolHealth || Object.keys(toolHealth).length === 0" class="tools-empty">
        暂无工具配置信息
      </div>
      <div v-else class="tools-grid">
        <div v-for="(available, name) in toolHealth" :key="name" class="tool-item">
          <el-tag :type="available ? 'success' : 'danger'" size="small">{{ name }}</el-tag>
          <span class="tool-status">{{ available ? '可用' : '不可用' }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.admin-system {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-header h2 { margin: 0; font-size: 18px; }

.status-value {
  font-size: 18px;
  font-weight: 600;
}

.mono {
  font-family: monospace;
  font-size: 14px;
}

.status-detail p {
  margin: 4px 0;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tools-card {
  margin-top: 20px;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.tool-status {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.tools-loading,
.tools-empty {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 16px;
}
</style>
