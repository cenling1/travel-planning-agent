<script setup lang="ts">
// ============================================================
// Layer 8: View — Long-term Memories Management
// ============================================================
import { ref, onMounted } from 'vue'
import { memoriesApi } from '@/api/memories'
import type { Memory, MemoryCreate } from '@/types/memory'
import { formatDate, memoryTypeLabel, importancePercent } from '@/utils/format'
import { extractErrorMessage } from '@/utils/error'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import { Plus, Refresh, Delete, Reading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const memories = ref<Memory[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)
const dialogVisible = ref(false)
const isCreating = ref(false)

const formRef = ref<FormInstance>()
const form = ref<MemoryCreate>({
  memory_key: '',
  content: '',
  memory_type: 'preference',
  importance: 0.6,
})

const rules: FormRules = {
  memory_key: [
    { required: true, message: '请输入记忆标题', trigger: 'blur' },
    { max: 120, message: '标题不超过 120 个字符', trigger: 'blur' },
  ],
  content: [
    { required: true, message: '请输入记忆内容', trigger: 'blur' },
    { max: 1000, message: '内容不超过 1000 个字符', trigger: 'blur' },
  ],
}

const typeOptions = [
  { label: '偏好', value: 'preference' },
  { label: '事实', value: 'fact' },
  { label: '约束', value: 'constraint' },
]

async function fetchMemories() {
  isLoading.value = true
  error.value = null
  try {
    memories.value = await memoriesApi.list()
  } catch (err) {
    error.value = extractErrorMessage(err, '加载记忆列表失败')
  } finally {
    isLoading.value = false
  }
}

async function handleCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  isCreating.value = true
  try {
    const created = await memoriesApi.create(form.value)
    memories.value.unshift(created)
    dialogVisible.value = false
    ElMessage.success('记忆已创建')
    // Reset form
    form.value = { memory_key: '', content: '', memory_type: 'preference', importance: 0.6 }
  } catch (err) {
    ElMessage.error(extractErrorMessage(err, '创建失败'))
  } finally {
    isCreating.value = false
  }
}

async function handleDelete(id: string) {
  try {
    await memoriesApi.delete(id)
    memories.value = memories.value.filter((m) => m.id !== id)
    ElMessage.success('记忆已删除')
  } catch (err) {
    ElMessage.error(extractErrorMessage(err, '删除失败'))
  }
}

onMounted(fetchMemories)
</script>

<template>
  <div class="memories-page">
    <div class="page-header">
      <h2>长期记忆</h2>
      <div class="header-actions">
        <el-button :icon="Plus" type="primary" @click="dialogVisible = true">
          新增记忆
        </el-button>
        <el-button :icon="Refresh" :loading="isLoading" @click="fetchMemories">
          刷新
        </el-button>
      </div>
    </div>

    <ErrorAlert v-if="error" :error="error" :show-retry="true" @retry="fetchMemories" />

    <p class="page-desc">
      长期记忆帮助 AI 更好地了解你的偏好和需求。AI 会在旅行规划时自动参考这些信息。
    </p>

    <EmptyState
      v-if="!isLoading && memories.length === 0"
      icon="Reading"
      title="暂无长期记忆"
      description="添加你的旅行偏好、约束和重要信息"
      :action-label="'新增记忆'"
      @action="dialogVisible = true"
    />

    <div v-else class="memory-list">
      <el-card v-for="mem in memories" :key="mem.id" class="memory-card" shadow="hover">
        <div class="memory-header">
          <span class="memory-key">{{ mem.memory_key }}</span>
          <el-tag size="small" type="info">{{ memoryTypeLabel(mem.memory_type) }}</el-tag>
        </div>

        <p class="memory-content">{{ mem.content }}</p>

        <div class="memory-meta">
          <el-progress
            :percentage="importancePercent(mem.importance)"
            :stroke-width="4"
            style="width: 100px"
          />
          <span class="memory-time">{{ formatDate(mem.updated_at, 'relative') }}</span>
        </div>

        <el-popconfirm
          title="确定删除此记忆？"
          @confirm="handleDelete(mem.id)"
        >
          <template #reference>
            <el-button class="memory-delete" text size="small" type="danger" :icon="Delete" />
          </template>
        </el-popconfirm>
      </el-card>
    </div>

    <!-- Create dialog -->
    <el-dialog v-model="dialogVisible" title="新增记忆" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="标题" prop="memory_key">
          <el-input v-model="form.memory_key" placeholder="例如：喜欢的旅行方式" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="类型" prop="memory_type">
          <el-select v-model="form.memory_type" style="width: 100%">
            <el-option v-for="opt in typeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="3"
            placeholder="描述你的偏好或约束…"
            maxlength="1000"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="重要程度">
          <el-slider v-model="form.importance" :min="0" :max="1" :step="0.1" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="isCreating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.memories-page {
  max-width: 900px;
  padding: 16px 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.page-header h2 { margin: 0; font-size: 18px; }
.header-actions { display: flex; gap: 8px; }

.page-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 20px;
}

.memory-list {
  display: grid;
  gap: 12px;
}

.memory-card {
  position: relative;
}

.memory-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.memory-key {
  font-weight: 600;
}

.memory-content {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin: 0 0 12px;
}

.memory-meta {
  display: flex;
  align-items: center;
  gap: 16px;
}

.memory-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.memory-delete {
  position: absolute;
  top: 8px;
  right: 8px;
}
</style>
