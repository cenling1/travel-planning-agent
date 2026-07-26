<script setup lang="ts">
// ============================================================
// Layer 6: Component — ChatInput
// Textarea with send button, character count, stop button
// ============================================================
import { ref, watch, nextTick, computed } from 'vue'
import { Promotion, Close } from '@element-plus/icons-vue'

const props = defineProps<{
  isGenerating: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [query: string]
  stop: []
}>()

const input = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const MAX_LENGTH = 4000
const MIN_LENGTH = 1

const canSend = computed(() => {
  return input.value.trim().length >= MIN_LENGTH && input.value.length <= MAX_LENGTH && !props.isGenerating
})

const charCount = computed(() => input.value.length)

function handleSend() {
  const query = input.value.trim()
  if (!canSend.value) return
  emit('send', query)
  input.value = ''
  nextTick(() => {
    textareaRef.value?.focus()
  })
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

// Expose focus method
defineExpose({ focus: () => textareaRef.value?.focus() })
</script>

<template>
  <div class="chat-input">
    <div class="chat-input__wrapper">
      <el-input
        ref="textareaRef"
        v-model="input"
        type="textarea"
        :rows="2"
        :maxlength="MAX_LENGTH"
        :disabled="disabled"
        placeholder="输入旅行需求，例如：帮我规划一个北京三日游"
        resize="none"
        @keydown="handleKeydown"
      />
      <div class="chat-input__actions">
        <span class="char-count" :class="{ 'char-count--warn': charCount > MAX_LENGTH * 0.9 }">
          {{ charCount }} / {{ MAX_LENGTH }}
        </span>
        <el-button
          v-if="!isGenerating"
          type="primary"
          :icon="Promotion"
          :disabled="!canSend"
          @click="handleSend"
        >
          发送
        </el-button>
        <el-button
          v-else
          type="danger"
          :icon="Close"
          @click="$emit('stop')"
        >
          停止生成
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  padding: 12px 16px;
  border-top: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}

.chat-input__wrapper {
  max-width: 900px;
  margin: 0 auto;
}

.chat-input :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.6;
}

.chat-input__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.char-count {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.char-count--warn {
  color: var(--el-color-warning);
}
</style>
