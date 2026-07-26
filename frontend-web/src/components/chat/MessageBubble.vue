<script setup lang="ts">
// ============================================================
// Layer 6: Component — MessageBubble
// Renders a single message with Markdown, citations, and tool results
// ============================================================
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import { formatDate } from '@/utils/format'
import type { Citation, ToolResult } from '@/types/chat'
import { CopyDocument } from '@element-plus/icons-vue'

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  citations?: Citation[]
  tools?: ToolResult[]
  isStreaming?: boolean
  isStopped?: boolean
}>()

const emit = defineEmits<{
  copy: []
  retry: []
}>()

const renderedHtml = computed(() => renderMarkdown(props.content))

function copyText() {
  navigator.clipboard.writeText(props.content)
  emit('copy')
  ElMessage.success('已复制到剪贴板')
}

import { ElMessage } from 'element-plus'
</script>

<template>
  <div class="message" :class="`message--${role}`">
    <div class="message__avatar">
      <el-avatar :size="32" :style="{ background: role === 'assistant' ? 'var(--el-color-primary)' : 'var(--el-color-success)' }">
        {{ role === 'assistant' ? 'AI' : '我' }}
      </el-avatar>
    </div>

    <div class="message__body">
      <div class="message__meta">
        <span class="message__role">{{ role === 'assistant' ? '旅行助手' : '我' }}</span>
        <span v-if="timestamp" class="message__time">{{ formatDate(timestamp) }}</span>
        <span v-if="isStreaming" class="message__generating">生成中…</span>
        <span v-if="isStopped" class="message__stopped">已停止</span>
      </div>

      <div
        class="message__content markdown-body"
        :class="{ 'message__content--streaming': isStreaming }"
        v-html="renderedHtml"
      />

      <!-- Citations -->
      <div v-if="citations && citations.length > 0" class="message__citations">
        <el-collapse>
          <el-collapse-item :title="`引用来源 (${citations.length})`">
            <div v-for="citation in citations" :key="citation.index" class="citation-item">
              <span class="citation-index">[{{ citation.index }}]</span>
              <span class="citation-source">{{ citation.source }}</span>
              <span v-if="citation.page" class="citation-page">第 {{ citation.page }} 页</span>
              <p class="citation-excerpt">{{ citation.excerpt }}</p>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- Tool results -->
      <div v-if="tools && tools.length > 0" class="message__tools">
        <div v-for="tool in tools" :key="tool.name" class="tool-badge" :class="tool.success ? 'tool-badge--ok' : 'tool-badge--fail'">
          <span class="tool-name">{{ tool.name }}</span>
          <span class="tool-status">{{ tool.success ? '✓' : '✗' }}</span>
          <span v-if="tool.latency_ms" class="tool-latency">{{ tool.latency_ms }}ms</span>
        </div>
      </div>

      <!-- Actions -->
      <div v-if="!isStreaming" class="message__actions">
        <el-button text size="small" :icon="CopyDocument" @click="copyText">复制</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  padding: 16px 0;
}

.message--user {
  flex-direction: row-reverse;
}

.message__body {
  max-width: 80%;
  min-width: 200px;
}

.message--user .message__body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}

.message__role {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.message__time {
  color: var(--el-text-color-placeholder);
}

.message__generating {
  color: var(--el-color-primary);
  animation: blink 1s infinite;
}

.message__stopped {
  color: var(--el-color-warning);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.message__content {
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.message--user .message__content {
  background: var(--el-color-primary-light-9);
  padding: 10px 14px;
  border-radius: 12px;
}

.message__content--streaming::after {
  content: '▊';
  animation: blink 0.8s infinite;
  color: var(--el-color-primary);
}

/* Markdown body overrides */
.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3) {
  margin-top: 16px;
  margin-bottom: 8px;
}
.markdown-body :deep(p) { margin: 4px 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; }
.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--el-border-color);
  padding-left: 12px;
  color: var(--el-text-color-secondary);
  margin: 8px 0;
}
.markdown-body :deep(code) {
  background: var(--el-fill-color-light);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 13px;
}
.markdown-body :deep(pre) {
  background: var(--el-fill-color);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; }
.markdown-body :deep(th), .markdown-body :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 6px 10px;
  text-align: left;
}
.markdown-body :deep(th) { background: var(--el-fill-color-light); }

.message__citations {
  margin-top: 12px;
}

.citation-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.citation-index {
  font-weight: 600;
  color: var(--el-color-primary);
  margin-right: 8px;
}

.citation-source {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.citation-page {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-left: 8px;
}

.citation-excerpt {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.message__tools {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.tool-badge--ok {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}

.tool-badge--fail {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

.tool-name { font-weight: 500; }
.tool-latency { color: var(--el-text-color-placeholder); }

.message__actions {
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.15s;
}

.message:hover .message__actions {
  opacity: 1;
}
</style>
