<script setup lang="ts">
// ============================================================
// Layer 8: View — Documents (Knowledge Base Management)
// ============================================================
import { ref, onMounted, computed } from 'vue'
import { documentsApi } from '@/api/documents'
import { useSystemStore } from '@/stores/system'
import type { Document, SearchResponse } from '@/types/document'
import { formatDate, formatFileSize, documentStatusLabel, documentStatusType } from '@/utils/format'
import { extractErrorMessage } from '@/utils/error'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import { Upload, Search, Refresh, Document as DocIcon, Close } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const documents = ref<Document[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)
const isUploading = ref(false)
const searchQuery = ref('')
const searchResult = ref<SearchResponse | null>(null)
const isSearching = ref(false)
const uploadRef = ref<HTMLInputElement | null>(null)
const selectedFiles = ref<File[]>([])
const isDragging = ref(false)
const systemStore = useSystemStore()
const maxFileSize = computed(() => systemStore.health?.max_upload_bytes || 20 * 1024 * 1024)

async function fetchDocuments() {
  isLoading.value = true
  error.value = null
  try {
    documents.value = await documentsApi.list()
  } catch (err) {
    error.value = extractErrorMessage(err, '加载文档列表失败')
  } finally {
    isLoading.value = false
  }
}

function selectFiles(files: File[]) {
  if (files.length === 0) return
  for (const file of files) {
    if (file.size > maxFileSize.value) {
      ElMessage.error(`文件 ${file.name} 超过大小限制 (${formatFileSize(maxFileSize.value)})`)
      return
    }
  }
  selectedFiles.value = files
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectFiles(Array.from(input.files || []))
  input.value = ''
}

function handleDrop(event: DragEvent) {
  isDragging.value = false
  selectFiles(Array.from(event.dataTransfer?.files || []))
}

async function uploadSelected() {
  if (!selectedFiles.value.length) return

  isUploading.value = true
  error.value = null
  try {
    const result = await documentsApi.upload(selectedFiles.value)
    documents.value = [...result.documents, ...documents.value]
    ElMessage.success(`成功上传 ${result.documents.length} 个文件`)
    selectedFiles.value = []
  } catch (err) {
    error.value = extractErrorMessage(err, '上传失败')
  } finally {
    isUploading.value = false
  }
}

async function handleReindex(documentId: string) {
  try {
    const updated = await documentsApi.reindex(documentId)
    const idx = documents.value.findIndex((d) => d.id === documentId)
    if (idx !== -1) documents.value[idx] = updated
    ElMessage.success('重新索引已开始')
  } catch (err) {
    ElMessage.error(extractErrorMessage(err, '重新索引失败'))
  }
}

async function handleDelete(documentId: string, filename: string) {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${filename}" 吗？删除后将无法恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    await documentsApi.delete(documentId)
    documents.value = documents.value.filter((d) => d.id !== documentId)
    ElMessage.success('文档已删除')
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') {
      ElMessage.error(extractErrorMessage(err, '删除文档失败'))
    }
  }
}

async function handleSearch() {
  if (!searchQuery.value.trim()) return
  isSearching.value = true
  try {
    searchResult.value = await documentsApi.search(searchQuery.value.trim())
  } catch (err) {
    ElMessage.error(extractErrorMessage(err, '检索失败'))
  } finally {
    isSearching.value = false
  }
}

onMounted(() => {
  fetchDocuments()
  if (!systemStore.health) systemStore.checkHealth()
})
</script>

<template>
  <div class="documents-page">
    <div class="page-header">
      <h2>知识文档</h2>
      <div class="header-actions">
        <el-button :icon="Refresh" :loading="isLoading" @click="fetchDocuments">
          刷新
        </el-button>
        <input
          ref="uploadRef"
          type="file"
          multiple
          accept=".pdf,.txt,.md,.csv,.docx,.pptx"
          hidden
          @change="handleFileChange"
        />
      </div>
    </div>

    <ErrorAlert v-if="error" :error="error" :show-retry="true" @retry="fetchDocuments" />

    <section
      class="upload-zone"
      :class="{ 'upload-zone--dragging': isDragging }"
      @click="uploadRef?.click()"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="handleDrop"
    >
      <el-icon :size="25"><Upload /></el-icon>
      <div>
        <strong>拖放文档到这里，或点击选择</strong>
        <p>单个文件不超过 {{ formatFileSize(maxFileSize) }}</p>
      </div>
    </section>

    <div v-if="selectedFiles.length" class="selected-files">
      <div v-for="file in selectedFiles" :key="`${file.name}-${file.size}`" class="selected-file">
        <el-icon><DocIcon /></el-icon>
        <span class="selected-file__name">{{ file.name }}</span>
        <span>{{ file.type || '未知类型' }}</span>
        <span>{{ formatFileSize(file.size) }}</span>
      </div>
      <div class="selected-actions">
        <el-button :icon="Close" @click="selectedFiles = []">清空</el-button>
        <el-button type="primary" :icon="Upload" :loading="isUploading" @click="uploadSelected">
          上传 {{ selectedFiles.length }} 个文件
        </el-button>
      </div>
    </div>

    <!-- Search -->
    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="输入问题检索知识库…"
        :prefix-icon="Search"
        clearable
        style="max-width: 480px"
        @keyup.enter="handleSearch"
      >
        <template #append>
          <el-button :icon="Search" :loading="isSearching" @click="handleSearch">检索</el-button>
        </template>
      </el-input>
    </div>

    <!-- Search results -->
    <div v-if="searchResult" class="search-results">
      <h4>检索结果 ({{ searchResult.citations.length }} 条)</h4>
      <div v-for="cite in searchResult.citations" :key="cite.index" class="search-item">
        <span class="search-source">[{{ cite.index }}] {{ cite.source }}</span>
        <p>{{ cite.excerpt }}</p>
      </div>
    </div>

    <!-- Document table -->
    <EmptyState
      v-if="!isLoading && documents.length === 0"
      icon="Document"
      title="暂无知识文档"
      description="上传 PDF、TXT、Markdown 等文件，系统会自动解析并建立索引"
    />

    <el-table
      v-else
      :data="documents"
      v-loading="isLoading"
      stripe
      style="width: 100%"
    >
      <el-table-column prop="filename" label="文件名" min-width="180">
        <template #default="{ row }">
          <div class="filename-cell">
            <el-icon><DocIcon /></el-icon>
            <span>{{ row.filename }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="file_type" label="类型" width="70" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="documentStatusType(row.status)" size="small">
            {{ documentStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="chunk_count" label="切片数" width="80" />
      <el-table-column prop="error_message" label="处理说明" min-width="180">
        <template #default="{ row }">
          <span :class="{ 'error-message': row.error_message }">{{ row.error_message || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" width="160">
        <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" type="primary" @click="handleReindex(row.id)">
            重新索引
          </el-button>
          <el-button text size="small" type="danger" @click="handleDelete(row.id, row.filename)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.documents-page {
  max-width: 1200px;
  padding: 16px 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 18px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.search-bar {
  margin-bottom: 16px;
}

.upload-zone {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
  padding: 18px;
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  background: var(--el-fill-color-extra-light);
  color: var(--el-text-color-secondary);
  cursor: pointer;
}
.upload-zone--dragging { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.upload-zone strong { display: block; color: var(--el-text-color-primary); }
.upload-zone p { margin: 3px 0 0; font-size: 12px; }
.selected-files { margin: -4px 0 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; }
.selected-file { display: grid; grid-template-columns: 20px minmax(120px, 1fr) 160px 90px; gap: 8px; padding: 9px 12px; border-bottom: 1px solid var(--el-border-color-lighter); font-size: 12px; color: var(--el-text-color-secondary); }
.selected-file__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--el-text-color-primary); }
.selected-actions { display: flex; justify-content: flex-end; gap: 8px; padding: 10px 12px; }
.error-message { color: var(--el-color-danger); }

.search-results {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.search-results h4 {
  margin: 0 0 12px;
}

.search-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.search-source {
  font-weight: 500;
  color: var(--el-color-primary);
}

.search-item p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.filename-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

@media (max-width: 640px) {
  .documents-page { padding: 14px; }
  .page-header { align-items: flex-start; }
  .selected-file { grid-template-columns: 20px minmax(0, 1fr); }
  .selected-file span:not(.selected-file__name) { display: none; }
  .selected-actions { flex-wrap: wrap; }
}
</style>
